"""Nastavení integrace Akce na pivo přes UI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ALL_BRANDS,
    CONF_BRANDS,
    CONF_COUNTRY,
    CONF_CUSTOM_URLS,
    CONF_DEGREES,
    CONF_EXCLUDE_LOYALTY,
    CONF_EXCLUDE_NONALCOHOLIC,
    CONF_INCLUDE_UNKNOWN_DEGREE,
    CONF_INCLUDE_UNKNOWN_PACKAGING,
    CONF_INCLUDE_UPCOMING,
    CONF_LANGUAGE,
    CONF_LOCATION_ENTITY,
    CONF_MAX_DISTANCE_KM,
    CONF_MAX_PAGES,
    CONF_PACKAGING,
    CONF_PRICE_ALERT,
    CONF_REQUIRE_NEARBY_STORE,
    CONF_SHOP_TYPE,
    CONF_SORT_BY,
    CONF_SOURCES,
    CONF_TOP_COUNT,
    CONF_UPDATE_INTERVAL_HOURS,
    CONF_UPDATE_TIME,
    COUNTRIES,
    DEFAULT_COUNTRY,
    DEFAULT_DEGREES,
    DEFAULT_EXCLUDE_LOYALTY,
    DEFAULT_EXCLUDE_NONALCOHOLIC,
    DEFAULT_INCLUDE_UNKNOWN_DEGREE,
    DEFAULT_INCLUDE_UNKNOWN_PACKAGING,
    DEFAULT_INCLUDE_UPCOMING,
    DEFAULT_MAX_DISTANCE_KM,
    DEFAULT_MAX_PAGES,
    DEFAULT_PACKAGING,
    DEFAULT_REQUIRE_NEARBY_STORE,
    DEFAULT_SHOP_TYPE,
    DEFAULT_SORT_BY,
    DEFAULT_TOP_COUNT,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_TIME,
    DEGREE_OPTIONS,
    DOMAIN,
    KNOWN_BRANDS,
    MAX_TOP_COUNT,
    NAME,
    PACKAGING_OPTIONS,
    SHOP_TYPE_OPTIONS,
    SORT_OPTIONS,
    SOURCES,
    country_sources,
)
from .texts import LANGUAGE_AUTO, LANGUAGE_OPTIONS


def _language_field(values: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_LANGUAGE, default=values.get(CONF_LANGUAGE, LANGUAGE_AUTO)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=LANGUAGE_OPTIONS,
                translation_key=CONF_LANGUAGE,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    }


def _country_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=values.get(CONF_NAME, NAME)): str,
            **_language_field(values),
            vol.Required(
                CONF_COUNTRY, default=values.get(CONF_COUNTRY, DEFAULT_COUNTRY)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=code, label=f"{info['name']} ({info['symbol']})"
                        )
                        for code, info in COUNTRIES.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _schema(values: dict[str, Any], country: str, with_language: bool = False) -> vol.Schema:
    info = COUNTRIES[country]
    sources = country_sources(country)
    all_label = "🍺 Všetky pivá v akcii" if country == "SK" else "🍺 Všechna piva v akci"
    brand_options = [selector.SelectOptionDict(value=ALL_BRANDS, label=all_label)]
    brand_options += [selector.SelectOptionDict(value=b, label=b) for b in KNOWN_BRANDS]
    # vlastní značky zadané dříve musí zůstat mezi možnostmi
    for brand in values.get(CONF_BRANDS, []):
        if brand != ALL_BRANDS and brand not in KNOWN_BRANDS:
            brand_options.append(selector.SelectOptionDict(value=brand, label=brand))

    fields: dict[Any, Any] = _language_field(values) if with_language else {}

    location = values.get(CONF_LOCATION_ENTITY)
    fields.update(
        {
            vol.Required(
                CONF_BRANDS, default=values.get(CONF_BRANDS, info["default_brands"])
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=brand_options,
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_PACKAGING, default=values.get(CONF_PACKAGING, DEFAULT_PACKAGING)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PACKAGING_OPTIONS,
                    multiple=True,
                    translation_key=CONF_PACKAGING,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_INCLUDE_UNKNOWN_PACKAGING,
                default=values.get(
                    CONF_INCLUDE_UNKNOWN_PACKAGING, DEFAULT_INCLUDE_UNKNOWN_PACKAGING
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_DEGREES, default=values.get(CONF_DEGREES, DEFAULT_DEGREES)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=DEGREE_OPTIONS,
                    multiple=True,
                    translation_key=CONF_DEGREES,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_INCLUDE_UNKNOWN_DEGREE,
                default=values.get(CONF_INCLUDE_UNKNOWN_DEGREE, DEFAULT_INCLUDE_UNKNOWN_DEGREE),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SHOP_TYPE, default=values.get(CONF_SHOP_TYPE, DEFAULT_SHOP_TYPE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SHOP_TYPE_OPTIONS,
                    translation_key=CONF_SHOP_TYPE,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_SOURCES,
                default=[s for s in values.get(CONF_SOURCES, sources) if s in sources] or sources,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=key, label=SOURCES[key]["name"])
                        for key in sources
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_CUSTOM_URLS,
                description={"suggested_value": values.get(CONF_CUSTOM_URLS, "")},
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            (
                vol.Optional(CONF_LOCATION_ENTITY, description={"suggested_value": location})
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["person", "device_tracker", "zone"])
            ),
            vol.Required(
                CONF_UPDATE_TIME, default=values.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_UPDATE_INTERVAL_HOURS,
                default=values.get(CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=24,
                    step=1,
                    unit_of_measurement="h",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TOP_COUNT, default=values.get(CONF_TOP_COUNT, DEFAULT_TOP_COUNT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=MAX_TOP_COUNT, step=1, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(
                CONF_SORT_BY, default=values.get(CONF_SORT_BY, DEFAULT_SORT_BY)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=SORT_OPTIONS, translation_key=CONF_SORT_BY)
            ),
            vol.Required(
                CONF_MAX_DISTANCE_KM,
                default=values.get(CONF_MAX_DISTANCE_KM, DEFAULT_MAX_DISTANCE_KM),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=50,
                    step=1,
                    unit_of_measurement="km",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_REQUIRE_NEARBY_STORE,
                default=values.get(CONF_REQUIRE_NEARBY_STORE, DEFAULT_REQUIRE_NEARBY_STORE),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_PRICE_ALERT, default=values.get(CONF_PRICE_ALERT, info["default_alert"])
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=info["alert_max"],
                    step=info["alert_step"],
                    unit_of_measurement=info["symbol"],
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_INCLUDE_UPCOMING,
                default=values.get(CONF_INCLUDE_UPCOMING, DEFAULT_INCLUDE_UPCOMING),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXCLUDE_LOYALTY,
                default=values.get(CONF_EXCLUDE_LOYALTY, DEFAULT_EXCLUDE_LOYALTY),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXCLUDE_NONALCOHOLIC,
                default=values.get(CONF_EXCLUDE_NONALCOHOLIC, DEFAULT_EXCLUDE_NONALCOHOLIC),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_MAX_PAGES, default=values.get(CONF_MAX_PAGES, DEFAULT_MAX_PAGES)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )
    return vol.Schema(fields)


def _clean(user_input: dict[str, Any], country: str) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_COUNTRY] = country
    brands: list[str] = []
    for raw in data.get(CONF_BRANDS, []):
        # vlastní hodnotu lze zadat i jako "Značka1, Značka2"
        for brand in str(raw).split(","):
            brand = brand.strip()
            if brand and brand not in brands:
                brands.append(brand)
    data[CONF_BRANDS] = brands
    for key in (CONF_UPDATE_INTERVAL_HOURS, CONF_TOP_COUNT, CONF_MAX_PAGES):
        if key in data:
            data[key] = int(data[key])
    data[CONF_PACKAGING] = [p for p in data.get(CONF_PACKAGING) or [] if p in PACKAGING_OPTIONS]
    if not data[CONF_PACKAGING]:
        data[CONF_PACKAGING] = list(PACKAGING_OPTIONS)
    data[CONF_DEGREES] = [d for d in data.get(CONF_DEGREES) or [] if d in DEGREE_OPTIONS]
    if not data[CONF_DEGREES]:
        data[CONF_DEGREES] = list(DEGREE_OPTIONS)
    allowed = country_sources(country)
    data[CONF_SOURCES] = [s for s in data.get(CONF_SOURCES) or [] if s in allowed]
    if not data[CONF_SOURCES] and not data.get(CONF_CUSTOM_URLS):
        data[CONF_SOURCES] = allowed
    data[CONF_CUSTOM_URLS] = (data.get(CONF_CUSTOM_URLS) or "").strip()
    if not data.get(CONF_LOCATION_ENTITY):
        data.pop(CONF_LOCATION_ENTITY, None)
    return data


class AkceNaPivoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Průvodce nastavením."""

    VERSION = 1

    def __init__(self) -> None:
        self._title = NAME
        self._country = DEFAULT_COUNTRY
        self._language = LANGUAGE_AUTO

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Krok 1: název a země (Česko / Slovensko)."""
        if user_input is not None:
            self._title = user_input.get(CONF_NAME) or NAME
            self._country = user_input.get(CONF_COUNTRY) or DEFAULT_COUNTRY
            self._language = user_input.get(CONF_LANGUAGE) or LANGUAGE_AUTO
            return await self.async_step_settings()
        return self.async_show_form(step_id="user", data_schema=_country_schema({}))

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Krok 2: značky, zdroje a další nastavení pro zvolenou zemi."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input, self._country)
            data[CONF_LANGUAGE] = self._language
            if not data[CONF_BRANDS]:
                errors[CONF_BRANDS] = "no_brands"
            else:
                return self.async_create_entry(title=self._title, data={}, options=data)
        return self.async_show_form(
            step_id="settings",
            data_schema=_schema(user_input or {}, self._country),
            errors=errors,
            description_placeholders={"country": COUNTRIES[self._country]["name"]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AkceNaPivoOptionsFlow()


class AkceNaPivoOptionsFlow(OptionsFlow):
    """Změna nastavení."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        country = current.get(CONF_COUNTRY) or DEFAULT_COUNTRY
        if user_input is not None:
            data = _clean(user_input, country)
            if not data[CONF_BRANDS]:
                errors[CONF_BRANDS] = "no_brands"
            else:
                return self.async_create_entry(data=data)
        values = {**current, **(user_input or {})}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(values, country, with_language=True),
            errors=errors,
            description_placeholders={"country": COUNTRIES[country]["name"]},
        )
