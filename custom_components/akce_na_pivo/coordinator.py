"""Koordinátor – stahuje akce, dohledává obchody a vyhodnocuje nejlevnější pivo."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ALL_BRANDS,
    CONF_BRANDS,
    CONF_COUNTRY,
    CONF_CUSTOM_URLS,
    CONF_EXCLUDE_LOYALTY,
    CONF_EXCLUDE_NONALCOHOLIC,
    CONF_INCLUDE_UPCOMING,
    CONF_LOCATION_ENTITY,
    CONF_MAX_DISTANCE_KM,
    CONF_MAX_PAGES,
    CONF_PRICE_ALERT,
    CONF_REQUIRE_NEARBY_STORE,
    CONF_SORT_BY,
    CONF_SOURCES,
    CONF_TOP_COUNT,
    COUNTRIES,
    DEFAULT_COUNTRY,
    DEFAULT_EXCLUDE_LOYALTY,
    DEFAULT_EXCLUDE_NONALCOHOLIC,
    DEFAULT_INCLUDE_UPCOMING,
    DEFAULT_MAX_DISTANCE_KM,
    DEFAULT_MAX_PAGES,
    DEFAULT_REQUIRE_NEARBY_STORE,
    DEFAULT_SORT_BY,
    DEFAULT_TOP_COUNT,
    DOMAIN,
    EVENT_CHEAP_BEER,
    HISTORY_DAYS,
    KNOWN_BRANDS,
    KUPI_PRODUCT_URL,
    KUPI_SEARCH_URL,
    RELOCATE_DISTANCE_KM,
    SORT_DISTANCE,
    SORT_PRICE,
    SOURCE_CUSTOM,
    SOURCE_KUPI,
    SOURCES,
    STORE_CACHE_DAYS,
    USER_AGENT,
    country_sources,
)
from .generic import dedupe, parse_generic
from .kupi import match_brand, normalize, parse_offers
from .stores import (
    fetch_stores,
    haversine_km,
    in_country,
    nearest_store,
    reverse_geocode,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_DELAY = 0.7
STORE_RETRY_MINUTES = 30
NOMINATIM_DELAY = 1.1  # limit Nominatimu 1 dotaz/s
DEAD_URL_DAYS = 7

HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def sort_key(sort_by: str):
    """Řadicí funkce podle zvoleného kritéria."""

    def unit(offer: dict[str, Any]) -> float:
        value = offer.get("price_per_half_liter")
        return value if value is not None else offer["price"]

    def key(offer: dict[str, Any]) -> tuple:
        distance = offer.get("distance_km")
        distance = distance if distance is not None else 9999
        if sort_by == SORT_PRICE:
            return (offer["price"], unit(offer), distance)
        if sort_by == SORT_DISTANCE:
            return (distance, unit(offer), offer["price"])
        return (unit(offer), offer["price"], distance)

    return key


class BeerDealsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Stahuje a vyhodnocuje akce na pivo."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}", update_interval=None)
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self._store = Store[dict[str, Any]](hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._cache: dict[str, Any] = {}
        self._raw_offers: list[dict[str, Any]] = []
        self._last_relocate: datetime | None = None
        self._lock = asyncio.Lock()
        self._status: dict[str, dict[str, Any]] = {}
        self._filter_stats: dict[str, Any] = {}
        self._store_retry_unsub: Any = None

    # ------------------------------------------------------------------ config
    @property
    def options(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def opt(self, key: str, default: Any) -> Any:
        value = self.options.get(key)
        return default if value is None or value == "" else value

    @property
    def country(self) -> str:
        country = self.options.get(CONF_COUNTRY) or DEFAULT_COUNTRY
        return country if country in COUNTRIES else DEFAULT_COUNTRY

    @property
    def country_info(self) -> dict[str, Any]:
        return COUNTRIES[self.country]

    @property
    def currency(self) -> str:
        return self.country_info["currency"]

    @property
    def currency_symbol(self) -> str:
        return self.country_info["symbol"]

    @property
    def price_alert(self) -> float:
        return float(self.opt(CONF_PRICE_ALERT, self.country_info["default_alert"]))

    @property
    def brands(self) -> list[str]:
        brands = self.opt(CONF_BRANDS, self.country_info["default_brands"])
        if isinstance(brands, str):
            brands = [b.strip() for b in brands.split(",") if b.strip()]
        return list(brands)

    @property
    def all_brands(self) -> bool:
        return not self.brands or ALL_BRANDS in self.brands

    def current_location(self) -> tuple[float, float, str]:
        entity_id = self.options.get(CONF_LOCATION_ENTITY)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is not None:
                lat = state.attributes.get("latitude")
                lon = state.attributes.get("longitude")
                if lat is not None and lon is not None:
                    if in_country(float(lat), float(lon), self.country):
                        return float(lat), float(lon), entity_id
                    # akce jsou jen ve zvolené zemi – mimo ni počítáme vzdálenost od domova
                    _LOGGER.debug("%s je mimo %s, používám domov", entity_id, self.country)
                    return (
                        self.hass.config.latitude,
                        self.hass.config.longitude,
                        f"zone.home (poloha mimo {self.country})",
                    )
            _LOGGER.debug("Entita %s nemá polohu, používám domov", entity_id)
        if not in_country(self.hass.config.latitude, self.hass.config.longitude, self.country):
            # např. domov v ČR a akce na Slovensku – hledají se pobočky v SK do zvolené vzdálenosti
            _LOGGER.debug("Domov leží mimo %s – obchody se hledají jen v %s", *[self.country] * 2)
        return self.hass.config.latitude, self.hass.config.longitude, "zone.home"

    # ---------------------------------------------------------------- storage
    async def async_load(self) -> None:
        self._cache = await self._store.async_load() or {}
        self._cache.setdefault("history", {})
        self._cache.setdefault("alerted", [])
        self._cache.setdefault("stores", {})

    async def _async_save(self) -> None:
        await self._store.async_save(self._cache)

    # ---------------------------------------------------------------- zdroje
    @property
    def sources(self) -> list[str]:
        allowed = country_sources(self.country)
        sources = self.opt(CONF_SOURCES, allowed)
        return [s for s in sources if s in allowed]

    @property
    def custom_urls(self) -> list[str]:
        raw = self.options.get(CONF_CUSTOM_URLS) or ""
        if isinstance(raw, list):
            raw = "\n".join(raw)
        return [u.strip() for u in re.split(r"[\n,; ]+", raw) if u.strip().startswith("http")]

    def _brand_queries(self) -> list[tuple[str, str, str]]:
        """(značka, text pro vyhledání, slug) pro vybrané značky."""
        result = []
        for brand in self.brands:
            if brand == ALL_BRANDS:
                continue
            query = brand.split("(")[0].strip()
            slug = slugify(query).replace("_", "-")
            result.append((brand, query, slug))
        return result

    def _is_dead(self, template: str) -> bool:
        dead = self._cache.setdefault("dead_urls", {})
        until = dead.get(template)
        return bool(until and until > dt_util.now().date().isoformat())

    def _mark_dead(self, template: str) -> None:
        until = dt_util.now().date() + timedelta(days=DEAD_URL_DAYS)
        self._cache.setdefault("dead_urls", {})[template] = until.isoformat()

    async def _fetch_html(self, url: str) -> tuple[int, str | None]:
        try:
            async with self.session.get(
                url, headers=HTTP_HEADERS, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status >= 400:
                    return resp.status, None
                return resp.status, await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Stažení %s selhalo: %s", url, err)
            return 0, None

    def _parse(self, source: str, html: str, url: str, today: date) -> list[dict[str, Any]]:
        if "kupi.cz" in url:
            offers = parse_offers(html, url, today)
            for offer in offers:
                offer["source"] = source
                offer["sources"] = [source]
            if not offers:
                return parse_generic(html, url, today, source, self.country)
            # vlastní parser kupi.cz + strukturovaná data stránky (co jeden nenajde, doplní druhý)
            structured = parse_generic(html, url, today, source, self.country, heuristics=False)
            return dedupe(offers + structured)
        return parse_generic(html, url, today, source, self.country)

    async def _fetch_listing(
        self, source: str, base_url: str, max_pages: int, today: date, template: str | None = None
    ) -> list[dict[str, Any]]:
        offers: list[dict[str, Any]] = []
        seen: set[str] = set()
        status = self._status[source]
        for page in range(1, max_pages + 1):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 1 else f"{base_url}{sep}page={page}"
            code, html = await self._fetch_html(url)
            status["requests"] += 1
            if not html:
                if page == 1:
                    status["errors"].append(f"{url}: HTTP {code or 'chyba spojení'}")
                    if code in (404, 410) and template and source != SOURCE_KUPI:
                        self._mark_dead(template)
                break
            page_offers = [o for o in self._parse(source, html, url, today) if o["id"] not in seen]
            if not page_offers:
                if page == 1:
                    lowered = html[:20000].lower()
                    hint = (
                        "ochrana proti robotům"
                        if any(w in lowered for w in ("captcha", "cf-challenge", "just a moment"))
                        else "parser na stránce nenašel žádnou akci"
                    )
                    status["errors"].append(f"{url}: HTTP {code}, {len(html)} znaků – {hint}")
                break
            seen.update(o["id"] for o in page_offers)
            offers.extend(page_offers)
            await asyncio.sleep(REQUEST_DELAY)
        if offers:
            status["working_urls"].append(base_url)
        return offers

    async def _first_working(
        self, source: str, templates: tuple[str, ...], today: date, pages: int = 1, **fmt: str
    ) -> list[dict[str, Any]]:
        """Zkouší šablony URL postupně, vrátí nabídky z první funkční."""
        for template in templates:
            if self._is_dead(template):
                continue
            url = template.format(**fmt) if fmt else template
            found = await self._fetch_listing(source, url, pages, today, template)
            if found:
                return found
        return []

    async def _fetch_source(self, source: str, today: date) -> list[dict[str, Any]]:
        spec = SOURCES[source]
        max_pages = int(self.opt(CONF_MAX_PAGES, DEFAULT_MAX_PAGES)) if spec["pages"] else 1
        offers = await self._first_working(source, spec["listing"], today, max_pages)
        if self.all_brands:
            return offers
        for brand, query, slug in self._brand_queries():
            if any(match_brand(o["product"], [brand]) for o in offers):
                continue
            templates = spec["brand"]
            if source == SOURCE_KUPI:
                kupi_slug = KNOWN_BRANDS.get(brand, ((), ""))[1]
                templates = ((KUPI_PRODUCT_URL,) if kupi_slug else ()) + (KUPI_SEARCH_URL,)
                slug = kupi_slug or slug
            offers += await self._first_working(
                source, templates, today, 1, query=quote_plus(query), slug=slug
            )
        return offers

    async def _fetch_custom(self, today: date) -> list[dict[str, Any]]:
        offers: list[dict[str, Any]] = []
        for template in self.custom_urls:
            if "{query}" in template or "{slug}" in template:
                queries = self._brand_queries() or [("", "pivo", "pivo")]
                for _brand, query, slug in queries:
                    url = template.replace("{query}", quote_plus(query)).replace("{slug}", slug)
                    offers += await self._fetch_listing(SOURCE_CUSTOM, url, 1, today)
            else:
                offers += await self._fetch_listing(SOURCE_CUSTOM, template, 1, today)
        return offers

    async def _fetch_offers(self, today: date) -> list[dict[str, Any]]:
        self._status = {
            key: {
                "name": SOURCES[key]["name"] if key in SOURCES else "Vlastní URL",
                "offers": 0,
                "requests": 0,
                "working_urls": [],
                "errors": [],
            }
            for key in [*self.sources, *([SOURCE_CUSTOM] if self.custom_urls else [])]
        }
        offers: list[dict[str, Any]] = []
        for source in self.sources:
            try:
                found = await self._fetch_source(source, today)
            except Exception as err:  # noqa: BLE001 - chyba jednoho zdroje nesmí shodit ostatní
                _LOGGER.warning("Zdroj %s selhal: %s", source, err)
                self._status[source]["errors"].append(str(err))
                found = []
            self._status[source]["offers"] = len(found)
            offers += found
        if self.custom_urls:
            found = await self._fetch_custom(today)
            self._status[SOURCE_CUSTOM]["offers"] = len(found)
            offers += found
        for key, status in self._status.items():
            status["errors"] = status["errors"][:5]
            if not status["offers"]:
                _LOGGER.info("Zdroj %s nevrátil žádné akce: %s", key, status["errors"])
        return dedupe(offers)

    # ---------------------------------------------------------------- stores
    async def _stores_for(self, lat: float, lon: float) -> list[dict[str, Any]]:
        radius = float(self.opt(CONF_MAX_DISTANCE_KM, DEFAULT_MAX_DISTANCE_KM))
        radius = min(max(radius, 3.0), 50.0)
        cache = self._cache.get("stores") or {}
        fresh = False
        if cache.get("fetched"):
            age = dt_util.utcnow() - dt_util.parse_datetime(cache["fetched"])
            moved = haversine_km(lat, lon, cache.get("lat", 0), cache.get("lon", 0))
            fresh = (
                age < timedelta(days=STORE_CACHE_DAYS)
                and moved < RELOCATE_DISTANCE_KM
                and cache.get("radius") == radius
                and cache.get("country") == self.country
            )
        if fresh:
            return cache.get("items", [])
        try:
            items = await fetch_stores(self.session, lat, lon, radius, self.country)
        except RuntimeError as err:
            cached = cache.get("items", [])
            _LOGGER.warning(
                "%s – %s, nový pokus za %d min",
                err,
                "používám uložené pobočky" if cached else "adresy obchodů zatím nejsou k dispozici",
                STORE_RETRY_MINUTES,
            )
            self._schedule_store_retry()
            return cached
        if not items:
            _LOGGER.warning("V okolí %.4f, %.4f se nenašla žádná pobočka známých řetězců", lat, lon)
            return cache.get("items", [])
        self._cache["stores"] = {
            "fetched": dt_util.utcnow().isoformat(),
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "country": self.country,
            "items": items,
            "geocoded": cache.get("geocoded", {}) if cache else {},
        }
        return items

    async def _attach_stores(self, offers: list[dict[str, Any]], lat: float, lon: float) -> None:
        stores = await self._stores_for(lat, lon)
        for offer in offers:
            offer.update(
                store_name=None,
                address=None,
                latitude=None,
                longitude=None,
                distance_km=None,
                opening_hours=None,
                map_url=None,
                navigate_url=None,
            )
            if offer["online"]:
                continue
            store = nearest_store(stores, offer["chain"], lat, lon)
            if not store:
                continue
            offer.update(
                store_name=store["name"],
                address=store["address"],
                latitude=store["latitude"],
                longitude=store["longitude"],
                distance_km=store["distance_km"],
                opening_hours=store["opening_hours"],
                osm_id=store["osm_id"],
                map_url=(
                    f"https://mapy.com/fnc/v1/showmap?mapset=basic&center={store['longitude']},"
                    f"{store['latitude']}&zoom=17&marker=true"
                ),
                navigate_url=(
                    "https://www.google.com/maps/dir/?api=1&destination="
                    f"{store['latitude']},{store['longitude']}"
                ),
            )

    async def _fill_addresses(self, offers: list[dict[str, Any]]) -> None:
        geocoded: dict[str, str] = self._cache.setdefault("stores", {}).setdefault("geocoded", {})
        for offer in offers:
            if offer.get("address") or offer.get("latitude") is None:
                continue
            key = offer.get("osm_id") or f"{offer['latitude']},{offer['longitude']}"
            if key not in geocoded:
                geocoded[key] = await reverse_geocode(
                    self.session, offer["latitude"], offer["longitude"]
                )
                await asyncio.sleep(NOMINATIM_DELAY)
            offer["address"] = geocoded[key]

    # --------------------------------------------------------------- scoring
    def _filter(self, offers: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
        include_upcoming = bool(self.opt(CONF_INCLUDE_UPCOMING, DEFAULT_INCLUDE_UPCOMING))
        exclude_loyalty = bool(self.opt(CONF_EXCLUDE_LOYALTY, DEFAULT_EXCLUDE_LOYALTY))
        exclude_na = bool(self.opt(CONF_EXCLUDE_NONALCOHOLIC, DEFAULT_EXCLUDE_NONALCOHOLIC))
        result = []
        stats = {
            "downloaded": len(offers),
            "brand_mismatch": 0,
            "expired": 0,
            "upcoming_excluded": 0,
            "loyalty_excluded": 0,
            "nonalcoholic_excluded": 0,
        }
        for offer in offers:
            brand = (
                match_brand(offer["product"], self.brands)
                if not self.all_brands
                else (
                    match_brand(offer["product"], list(KNOWN_BRANDS))
                    or offer["product"].split(" ")[0]
                )
            )
            if not brand:
                stats["brand_mismatch"] += 1
                continue
            if offer["valid_to"] and date.fromisoformat(offer["valid_to"]) < today:
                stats["expired"] += 1
                continue
            upcoming = bool(offer["valid_from"] and date.fromisoformat(offer["valid_from"]) > today)
            if upcoming and not include_upcoming:
                stats["upcoming_excluded"] += 1
                continue
            if exclude_loyalty and offer["loyalty"]:
                stats["loyalty_excluded"] += 1
                continue
            if exclude_na and offer["nonalcoholic"]:
                stats["nonalcoholic_excluded"] += 1
                continue
            result.append({**offer, "brand": brand, "upcoming": upcoming})
        stats["matching"] = len(result)
        # ukázka stažených názvů – podle ní jde poznat, proč nic neodpovídá značkám
        stats["sample_products"] = [
            f"{o['product']} | {o['shop']} | {o['price']} | {o.get('source')}" for o in offers[:15]
        ]
        self._filter_stats = stats
        if offers and not result:
            _LOGGER.warning(
                "Staženo %d akcí, ale žádná neodpovídá nastavení (značky: %s). Vyřazeno: %s. "
                "Ukázka stažených akcí: %s",
                len(offers),
                ", ".join(self.brands),
                {k: v for k, v in stats.items() if k.endswith(("mismatch", "expired", "excluded"))},
                "; ".join(stats["sample_products"][:8]),
            )
        return result

    def _history_key(self, offer: dict[str, Any]) -> str:
        return f"{normalize(offer['product'])}|{offer['chain']}"

    def _evaluate(self, offers: list[dict[str, Any]], today: date) -> None:
        history: dict[str, dict[str, float]] = self._cache["history"]
        alert = self.price_alert
        symbol = self.currency_symbol
        cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()

        # průměrná cena za 0,5 l pro každou značku (napříč obchody)
        per_brand: dict[str, list[float]] = {}
        for offer in offers:
            if offer.get("price_per_half_liter"):
                per_brand.setdefault(offer["brand"], []).append(offer["price_per_half_liter"])
        brand_avg = {b: sum(v) / len(v) for b, v in per_brand.items()}

        for offer in offers:
            metric = offer.get("price_per_half_liter") or offer["price"]
            key = self._history_key(offer)
            past = {
                d: p for d, p in history.get(key, {}).items() if cutoff <= d < today.isoformat()
            }
            flags: list[str] = []
            offer["history_min"] = min(past.values()) if past else None
            offer["history_days"] = len(past)
            if past and metric <= min(past.values()):
                flags.append(f"Nejlevněji za posledních {HISTORY_DAYS} dní")
            avg = brand_avg.get(offer["brand"])
            offer["cheaper_than_avg"] = (
                round(avg - offer["price_per_half_liter"], 2)
                if avg and offer.get("price_per_half_liter")
                else None
            )
            if offer["cheaper_than_avg"] and offer["cheaper_than_avg"] >= 1:
                flags.append(
                    f"O {offer['cheaper_than_avg']:.2f} {symbol}/0,5 l levnější než průměr akcí"
                )
            if offer.get("discount_percent") and offer["discount_percent"] >= 30:
                flags.append(f"Sleva {offer['discount_percent']:g} %")
            if offer.get("price_per_half_liter") and offer["price_per_half_liter"] <= alert:
                flags.append(f"Pod limitem {alert:g} {symbol}/0,5 l")
                offer["below_alert"] = True
            else:
                offer["below_alert"] = False
            if offer["valid_to"] == today.isoformat():
                flags.append("Končí dnes")
            elif offer["valid_to"] == (today + timedelta(days=1)).isoformat():
                flags.append("Končí zítra")
            if offer["upcoming"]:
                flags.append(f"Platí od {offer['valid_from']}")
            if offer["loyalty"]:
                flags.append("Jen s věrnostní kartou/aplikací")
            if offer["pieces"] and offer["pieces"] >= 6:
                flags.append(f"Multipack {offer['pieces']} ks")
            offer["flags"] = flags

            if not offer["upcoming"]:
                day_prices = history.setdefault(key, {})
                previous = day_prices.get(today.isoformat())
                day_prices[today.isoformat()] = (
                    metric if previous is None else min(previous, metric)
                )

        for key in list(history):
            history[key] = {d: p for d, p in history[key].items() if d >= cutoff}
            if not history[key]:
                del history[key]

    def _fire_alerts(self, offers: list[dict[str, Any]]) -> None:
        alerted: list[str] = self._cache["alerted"]
        current = {o["id"] for o in offers}
        for offer in offers:
            if offer["below_alert"] and offer["id"] not in alerted:
                alerted.append(offer["id"])
                self.hass.bus.async_fire(
                    EVENT_CHEAP_BEER,
                    {
                        "entry_id": self.entry.entry_id,
                        "product": offer["product"],
                        "brand": offer["brand"],
                        "shop": offer["shop"],
                        "price": offer["price"],
                        "currency": self.currency,
                        "country": self.country,
                        "price_per_half_liter": offer["price_per_half_liter"],
                        "address": offer.get("address"),
                        "distance_km": offer.get("distance_km"),
                        "valid_to": offer["valid_to"],
                        "url": offer["url"],
                    },
                )
        self._cache["alerted"] = [a for a in alerted if a in current]

    def _build_result(
        self, offers: list[dict[str, Any]], lat: float, lon: float, source: str
    ) -> dict[str, Any]:
        sort_by = self.opt(CONF_SORT_BY, DEFAULT_SORT_BY)
        top_count = int(self.opt(CONF_TOP_COUNT, DEFAULT_TOP_COUNT))
        max_distance = float(self.opt(CONF_MAX_DISTANCE_KM, DEFAULT_MAX_DISTANCE_KM))
        require_nearby = bool(self.opt(CONF_REQUIRE_NEARBY_STORE, DEFAULT_REQUIRE_NEARBY_STORE))

        usable = []
        for offer in offers:
            nearby = offer.get("distance_km") is not None and offer["distance_km"] <= max_distance
            offer["nearby"] = nearby
            if require_nearby and not nearby:
                continue
            usable.append(offer)
        usable.sort(key=sort_key(sort_by))
        # aktuálně platné nabídky mají přednost před budoucími
        current = [o for o in usable if not o["upcoming"]]
        upcoming = [o for o in usable if o["upcoming"]]

        brands: dict[str, dict[str, Any]] = {}
        for offer in current:
            brands.setdefault(offer["brand"], offer)

        for rank, offer in enumerate(current, start=1):
            offer["rank"] = rank

        return {
            "offers": current,
            "top": current[:top_count],
            "upcoming": upcoming[:top_count],
            "brands": brands,
            "location": {"latitude": lat, "longitude": lon, "source": source},
            "sort_by": sort_by,
            "top_count": top_count,
            "updated": dt_util.now().isoformat(),
            "total_found": len(offers),
            "sources": self._status,
            "filter_stats": self._filter_stats,
            "country": self.country,
            "currency": self.currency,
            "currency_symbol": self.currency_symbol,
            "by_source": {
                key: sum(1 for o in current if key in o.get("sources", [o.get("source")]))
                for key in self._status
            },
        }

    # ---------------------------------------------------------------- update
    async def _async_update_data(self) -> dict[str, Any]:
        async with self._lock:
            today = dt_util.now().date()
            raw = await self._fetch_offers(today)
            if not raw:
                if self.data:
                    _LOGGER.warning("Žádný zdroj nevrátil akce, ponechávám poslední data")
                    return self.data
                raise UpdateFailed(
                    "Nepodařilo se načíst žádné akce na pivo (zdroje: "
                    + ", ".join(f"{k}: {v['errors'][:1]}" for k, v in self._status.items())
                    + ")"
                )
            offers = self._filter(raw, today)
            self._raw_offers = offers
            return await self._process(offers, today)

    async def _process(self, offers: list[dict[str, Any]], today: date) -> dict[str, Any]:
        lat, lon, source = self.current_location()
        offers = [dict(o) for o in offers]
        await self._attach_stores(offers, lat, lon)
        self._evaluate(offers, today)
        result = self._build_result(offers, lat, lon, source)
        await self._fill_addresses(result["top"] + result["upcoming"])
        self._fire_alerts(result["offers"])
        await self._async_save()
        return result

    def _schedule_store_retry(self) -> None:
        """Po výpadku OpenStreetMap zkusí pobočky načíst znovu, bez nového stahování akcí."""
        if self._store_retry_unsub is not None:
            return

        async def _retry(_now: Any) -> None:
            self._store_retry_unsub = None
            if not self._raw_offers:
                return
            async with self._lock:
                result = await self._process(self._raw_offers, dt_util.now().date())
            self.async_set_updated_data(result)

        self._store_retry_unsub = async_call_later(
            self.hass, timedelta(minutes=STORE_RETRY_MINUTES), _retry
        )
        self.entry.async_on_unload(self._cancel_store_retry)

    def _cancel_store_retry(self) -> None:
        if self._store_retry_unsub is not None:
            self._store_retry_unsub()
            self._store_retry_unsub = None

    async def async_relocate(self) -> None:
        """Přepočítá vzdálenosti po změně polohy bez nového stahování akcí."""
        now = dt_util.utcnow()
        if not self._raw_offers or (
            self._last_relocate and now - self._last_relocate < timedelta(minutes=10)
        ):
            return
        if self.data:
            loc = self.data["location"]
            lat, lon, _ = self.current_location()
            if haversine_km(lat, lon, loc["latitude"], loc["longitude"]) < RELOCATE_DISTANCE_KM:
                return
        self._last_relocate = now
        async with self._lock:
            result = await self._process(self._raw_offers, dt_util.now().date())
        self.async_set_updated_data(result)
