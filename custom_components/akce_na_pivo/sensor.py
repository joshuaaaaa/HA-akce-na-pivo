"""Senzory s nejlevnějšími akcemi na pivo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import BeerConfigEntry
from .const import ALL_BRANDS, SORT_PRICE
from .coordinator import BeerDealsCoordinator
from .entity import BeerEntity, offer_attributes


class CurrencyUnit:
    """Jednotka podle zvolené země – CZK nebo EUR."""

    coordinator: BeerDealsCoordinator

    @property
    def native_unit_of_measurement(self) -> str:
        return self.coordinator.currency


async def async_setup_entry(
    hass: HomeAssistant, entry: BeerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        CheapestBeerSensor(coordinator),
        CheapestHalfLiterSensor(coordinator),
        OfferCountSensor(coordinator),
    ]
    top_count = coordinator.data.get("top_count", 5) if coordinator.data else 5
    entities += [RankSensor(coordinator, rank) for rank in range(1, top_count + 1)]
    brands = [brand for brand in coordinator.brands if brand != ALL_BRANDS]
    entities += [BrandSensor(coordinator, brand) for brand in brands]
    # "Kam pro pivo" – název obchodu, kam jít (celkově nejlevnější + pro každou značku)
    entities.append(WhereToGoSensor(coordinator))
    entities += [WhereToGoSensor(coordinator, brand) for brand in brands]
    async_add_entities(entities)


class CheapestBeerSensor(CurrencyUnit, BeerEntity, SensorEntity):
    """Hlavní senzor – nejlevnější nabídka + seznam TOP N pro kartu."""

    _attr_icon = "mdi:beer"
    _attr_translation_key = "cheapest"
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = frozenset({"offers", "upcoming", "brands", "location"})

    def __init__(self, coordinator: BeerDealsCoordinator) -> None:
        super().__init__(coordinator, "cheapest")

    @property
    def _best(self) -> dict[str, Any] | None:
        top = (self.coordinator.data or {}).get("top") or []
        return top[0] if top else None

    @property
    def native_value(self) -> float | None:
        best = self._best
        if not best:
            return None
        if self.coordinator.data.get("sort_by") == SORT_PRICE:
            return best["price"]
        return best.get("price_per_half_liter") or best["price"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        attrs = offer_attributes(self._best)
        attrs.update(
            {
                "value_type": "cena za balení"
                if data.get("sort_by") == SORT_PRICE
                else "cena za 0,5 l",
                "sort_by": data.get("sort_by"),
                "offers": [offer_attributes(o) for o in data.get("top", [])],
                "upcoming": [offer_attributes(o) for o in data.get("upcoming", [])],
                "brands": {b: offer_attributes(o) for b, o in (data.get("brands") or {}).items()},
                "location": data.get("location"),
                "updated": data.get("updated"),
                "total_found": data.get("total_found"),
                "source_names": {
                    key: status.get("name") for key, status in (data.get("sources") or {}).items()
                },
                "by_source": data.get("by_source"),
                "country": data.get("country"),
                "currency": data.get("currency"),
                "currency_symbol": data.get("currency_symbol"),
            }
        )
        return attrs


class CheapestHalfLiterSensor(CurrencyUnit, BeerEntity, SensorEntity):
    """Nejnižší cena přepočtená na 0,5 l."""

    _attr_icon = "mdi:glass-mug-variant"
    _attr_translation_key = "per_half_liter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: BeerDealsCoordinator) -> None:
        super().__init__(coordinator, "per_half_liter")

    def _best(self) -> dict[str, Any] | None:
        offers = [
            o
            for o in (self.coordinator.data or {}).get("offers", [])
            if o.get("price_per_half_liter")
        ]
        return min(offers, key=lambda o: o["price_per_half_liter"]) if offers else None

    @property
    def native_value(self) -> float | None:
        best = self._best()
        return best["price_per_half_liter"] if best else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return offer_attributes(self._best())


class OfferCountSensor(BeerEntity, SensorEntity):
    """Počet nalezených akcí."""

    _attr_icon = "mdi:counter"
    _attr_translation_key = "count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "akcí"

    def __init__(self, coordinator: BeerDealsCoordinator) -> None:
        super().__init__(coordinator, "count")

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("offers", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "updated": data.get("updated"),
            "upcoming": len(data.get("upcoming", [])),
            "total_found": data.get("total_found"),
            "matching_by_source": data.get("by_source"),
            # stav jednotlivých zdrojů – pomůže, když některý web změní adresy
            "sources": data.get("sources"),
        }


class RankSensor(CurrencyUnit, BeerEntity, SensorEntity):
    """N-tá nejlevnější nabídka – má polohu obchodu, takže jde na mapu."""

    _attr_icon = "mdi:beer-outline"
    _attr_translation_key = "rank"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: BeerDealsCoordinator, rank: int) -> None:
        super().__init__(coordinator, f"rank_{rank}")
        self._rank = rank
        self._attr_translation_placeholders = {"rank": str(rank)}

    @property
    def _offer(self) -> dict[str, Any] | None:
        top = (self.coordinator.data or {}).get("top") or []
        return top[self._rank - 1] if len(top) >= self._rank else None

    @property
    def native_value(self) -> float | None:
        offer = self._offer
        return offer["price"] if offer else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = offer_attributes(self._offer)
        if self._offer:
            attrs["friendly_label"] = (
                f"#{self._rank} {self._offer['product']} – {self._offer['shop']}"
            )
        return attrs


class BrandSensor(CurrencyUnit, BeerEntity, SensorEntity):
    """Nejlevnější akce pro konkrétní značku."""

    _attr_icon = "mdi:tag-outline"
    _attr_translation_key = "brand"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: BeerDealsCoordinator, brand: str) -> None:
        super().__init__(coordinator, f"brand_{slugify(brand)}")
        self._brand = brand
        self._attr_translation_placeholders = {"brand": brand}

    @property
    def _offer(self) -> dict[str, Any] | None:
        return ((self.coordinator.data or {}).get("brands") or {}).get(self._brand)

    @property
    def native_value(self) -> float | None:
        offer = self._offer
        return offer["price"] if offer else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return offer_attributes(self._offer)


def _money(value: float | None, symbol: str) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + f" {symbol}"


class WhereToGoSensor(BeerEntity, SensorEntity):
    """Název obchodu, kam jít pro nejlevnější pivo (celkově, nebo vybranou značku)."""

    _attr_icon = "mdi:store-marker"

    def __init__(self, coordinator: BeerDealsCoordinator, brand: str | None = None) -> None:
        key = f"where_{slugify(brand)}" if brand else "where"
        super().__init__(coordinator, key)
        self._brand = brand
        if brand:
            self._attr_translation_key = "where_brand"
            self._attr_translation_placeholders = {"brand": brand}
        else:
            self._attr_translation_key = "where"

    @property
    def _offer(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        if self._brand:
            return (data.get("brands") or {}).get(self._brand)
        top = data.get("top") or []
        return top[0] if top else None

    @property
    def native_value(self) -> str | None:
        offer = self._offer
        if not offer:
            return None
        return (offer.get("store_name") or offer["shop"])[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        offer = self._offer
        attrs = offer_attributes(offer)
        if offer:
            symbol = self.coordinator.currency_symbol
            parts = [offer.get("store_name") or offer["shop"]]
            if offer.get("address"):
                parts.append(offer["address"])
            where = ", ".join(parts)
            if offer.get("distance_km") is not None:
                where += f" ({offer['distance_km']:.1f} km)".replace(".", ",")
            price = _money(offer["price"], symbol)
            if offer.get("price_per_half_liter"):
                price += f" – {_money(offer['price_per_half_liter'], symbol)}/0,5 l"
            attrs["summary"] = f"{where}: {offer['product']} za {price}"
            attrs["currency_symbol"] = symbol
            attrs["for_brand"] = self._brand
        return attrs
