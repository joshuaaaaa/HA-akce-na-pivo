"""Akce na pivo – nejlevnější pivo v akci ve vašem okolí (data z kupi.cz)."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)

from .const import (
    CONF_LOCATION_ENTITY,
    CONF_UPDATE_INTERVAL_HOURS,
    CONF_UPDATE_TIME,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
)
from .coordinator import BeerDealsCoordinator

_LOGGER = logging.getLogger(__name__)

type BeerConfigEntry = ConfigEntry[BeerDealsCoordinator]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _loaded_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    return [
        e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED
    ]


def _parse_time(value: str) -> tuple[int, int, int]:
    parts = [int(p) for p in str(value or DEFAULT_UPDATE_TIME).split(":")] + [0, 0]
    return parts[0], parts[1], parts[2]


async def async_setup_entry(hass: HomeAssistant, entry: BeerConfigEntry) -> bool:
    coordinator = BeerDealsCoordinator(hass, entry)
    await coordinator.async_load()
    entry.runtime_data = coordinator
    # Po restartu HA se použijí uložená data. Stahuje se jen, když od poslední plánované
    # aktualizace žádná neproběhla – a to na pozadí, aby se start HA nezdržoval.
    needs_refresh = not coordinator.restore_cached()

    options = {**entry.data, **entry.options}

    # denní aktualizace v zadaný čas
    hour, minute, second = _parse_time(options.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME))

    async def _scheduled_refresh(_now) -> None:
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, _scheduled_refresh, hour=hour, minute=minute, second=second)
    )

    # volitelně navíc každých N hodin
    interval = int(options.get(CONF_UPDATE_INTERVAL_HOURS) or DEFAULT_UPDATE_INTERVAL_HOURS)
    if interval > 0:
        entry.async_on_unload(
            async_track_time_interval(hass, _scheduled_refresh, timedelta(hours=interval))
        )

    # při pohybu sledované osoby / telefonu přepočítat nejbližší obchody
    if entity_id := options.get(CONF_LOCATION_ENTITY):

        @callback
        def _location_changed(event: Event) -> None:
            hass.async_create_task(coordinator.async_relocate())

        entry.async_on_unload(async_track_state_change_event(hass, [entity_id], _location_changed))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    if needs_refresh:
        entry.async_create_background_task(
            hass, coordinator.async_background_first_refresh(), f"{DOMAIN}_first_refresh"
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def _refresh_all(call: ServiceCall) -> None:
            for loaded in _loaded_entries(hass):
                await loaded.runtime_data.async_request_refresh()

        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh_all)

    return True


async def _async_reload(hass: HomeAssistant, entry: BeerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BeerConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not [e for e in _loaded_entries(hass) if e.entry_id != entry.entry_id]:
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unloaded
