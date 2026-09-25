"""Akce na pivo – nejlevnější pivo v akci ve vašem okolí (data z kupi.cz)."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)

from .const import (
    CONF_LOCATION_ENTITY,
    CONF_UPDATE_TIME,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
    OLD_DEFAULT_UPDATE_TIME,
    PLATFORMS,
    SERVICE_REFRESH,
    STARTUP_REFRESH_DELAY_MINUTES,
)
from .coordinator import CACHE_NONE, CACHE_STALE, BeerDealsCoordinator

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
    # Po restartu HA se použijí uložená data. Stahuje se jen, když se zmeškalo noční
    # stahování (a to s odstupem po startu), nebo když ještě žádná data nejsou.
    cache_state = coordinator.restore_cached()

    options = {**entry.data, **entry.options}

    # jediné stahování za den, výchozí v 1:00 v noci
    hour, minute, second = _parse_time(options.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME))

    async def _scheduled_refresh(_now) -> None:
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, _scheduled_refresh, hour=hour, minute=minute, second=second)
    )

    # při pohybu sledované osoby / telefonu přepočítat nejbližší obchody
    if entity_id := options.get(CONF_LOCATION_ENTITY):

        @callback
        def _location_changed(event: Event) -> None:
            hass.async_create_task(coordinator.async_relocate())

        entry.async_on_unload(async_track_state_change_event(hass, [entity_id], _location_changed))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    if cache_state == CACHE_NONE:
        # nová instalace / změna nastavení – data zatím nejsou, stáhnout hned (na pozadí)
        entry.async_create_background_task(
            hass, coordinator.async_background_first_refresh(), f"{DOMAIN}_first_refresh"
        )
    elif cache_state == CACHE_STALE:
        # zmeškané noční stahování: zobrazí se poslední data, stáhne se až po startu HA

        async def _delayed_refresh(_now) -> None:
            await coordinator.async_background_first_refresh()

        entry.async_on_unload(
            async_call_later(
                hass, timedelta(minutes=STARTUP_REFRESH_DELAY_MINUTES), _delayed_refresh
            )
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def _refresh_all(call: ServiceCall) -> None:
            for loaded in _loaded_entries(hass):
                await loaded.runtime_data.async_request_refresh()

        hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh_all)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verze 1 -> 2: stahování jen jednou denně, výchozí čas 1:00 místo 7:00."""
    if entry.version == 1:
        options = dict(entry.options)
        options.pop("update_interval_hours", None)
        if options.get(CONF_UPDATE_TIME) in (None, "", OLD_DEFAULT_UPDATE_TIME):
            options[CONF_UPDATE_TIME] = DEFAULT_UPDATE_TIME
        hass.config_entries.async_update_entry(entry, options=options, version=2)
        _LOGGER.info(
            "Akce na pivo: stahování přesunuto na %s (jednou denně)", options[CONF_UPDATE_TIME]
        )
    return True


async def _async_reload(hass: HomeAssistant, entry: BeerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BeerConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not [e for e in _loaded_entries(hass) if e.entry_id != entry.entry_id]:
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unloaded
