"""Společný základ entit."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import BeerDealsCoordinator

OFFER_ATTRS = (
    "rank",
    "source",
    "sources",
    "brand",
    "product",
    "shop",
    "chain",
    "online",
    "price",
    "currency",
    "old_price",
    "discount_percent",
    "amount",
    "pieces",
    "volume_l",
    "price_per_piece",
    "price_per_liter",
    "price_per_half_liter",
    "validity",
    "valid_from",
    "valid_to",
    "loyalty",
    "nonalcoholic",
    "packaging",
    "degree",
    "upcoming",
    "flags",
    "flag_keys",
    "store_name",
    "address",
    "opening_hours",
    "latitude",
    "longitude",
    "distance_km",
    "nearby",
    "cheaper_than_avg",
    "history_min",
    "url",
    "image",
    "map_url",
    "navigate_url",
)


def offer_attributes(offer: dict[str, Any] | None) -> dict[str, Any]:
    if not offer:
        return {}
    return {key: offer.get(key) for key in OFFER_ATTRS}


class BeerEntity(CoordinatorEntity[BeerDealsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BeerDealsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="kupi.cz + OpenStreetMap",
            model=NAME,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.kupi.cz/slevy/pivo",
        )
