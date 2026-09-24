"""Binární senzor – je v akci pivo pod nastaveným limitem?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BeerConfigEntry
from .coordinator import BeerDealsCoordinator
from .entity import BeerEntity, offer_attributes


async def async_setup_entry(
    hass: HomeAssistant, entry: BeerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([CheapBeerBinarySensor(entry.runtime_data)])


class CheapBeerBinarySensor(BeerEntity, BinarySensorEntity):
    _attr_icon = "mdi:beer"
    _attr_translation_key = "cheap_beer"
    _unrecorded_attributes = frozenset({"offers"})

    def __init__(self, coordinator: BeerDealsCoordinator) -> None:
        super().__init__(coordinator, "cheap_beer")

    def _cheap(self) -> list[dict[str, Any]]:
        return [o for o in (self.coordinator.data or {}).get("offers", []) if o.get("below_alert")]

    @property
    def is_on(self) -> bool:
        return bool(self._cheap())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cheap = self._cheap()
        return {
            "limit_per_half_liter": self.coordinator.price_alert,
            "currency": self.coordinator.currency,
            "count": len(cheap),
            "offers": [offer_attributes(o) for o in cheap[:5]],
        }
