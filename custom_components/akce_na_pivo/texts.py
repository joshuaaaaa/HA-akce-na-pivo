"""Texty, které integrace zapisuje do senzorů (štítky akcí, „Není v akci“, shrnutí).

Jazyk se volí při přidání integrace: automaticky podle jazyka Home Assistantu,
nebo ručně čeština / slovenčina / angličtina.
"""

from __future__ import annotations

LANGUAGE_AUTO = "auto"
LANGUAGES = ("cs", "sk", "en")
LANGUAGE_OPTIONS = [LANGUAGE_AUTO, *LANGUAGES]

TEXTS: dict[str, dict[str, str]] = {
    "cs": {
        "history_min": "Nejlevněji za posledních {days} dní",
        "cheaper_than_avg": "O {amount} {symbol}/0,5 l levnější než průměr akcí",
        "discount": "Sleva {percent} %",
        "below_limit": "Pod limitem {limit} {symbol}/0,5 l",
        "ends_today": "Končí dnes",
        "ends_tomorrow": "Končí zítra",
        "valid_from": "Platí od {date}",
        "loyalty": "Jen s věrnostní kartou/aplikací",
        "multipack": "Multipack {pieces} ks",
        "not_on_sale": "Není v akci",
        "summary": "{where}: {product} za {price}",
        "value_package": "cena za balení",
        "value_half_liter": "cena za 0,5 l",
    },
    "sk": {
        "history_min": "Najlacnejšie za posledných {days} dní",
        "cheaper_than_avg": "O {amount} {symbol}/0,5 l lacnejšie ako priemer akcií",
        "discount": "Zľava {percent} %",
        "below_limit": "Pod limitom {limit} {symbol}/0,5 l",
        "ends_today": "Končí dnes",
        "ends_tomorrow": "Končí zajtra",
        "valid_from": "Platí od {date}",
        "loyalty": "Len s vernostnou kartou/aplikáciou",
        "multipack": "Multipack {pieces} ks",
        "not_on_sale": "Nie je v akcii",
        "summary": "{where}: {product} za {price}",
        "value_package": "cena za balenie",
        "value_half_liter": "cena za 0,5 l",
    },
    "en": {
        "history_min": "Cheapest in the last {days} days",
        "cheaper_than_avg": "{amount} {symbol}/0.5 l cheaper than the average deal",
        "discount": "{percent} % off",
        "below_limit": "Below the {limit} {symbol}/0.5 l limit",
        "ends_today": "Ends today",
        "ends_tomorrow": "Ends tomorrow",
        "valid_from": "Valid from {date}",
        "loyalty": "Loyalty card/app only",
        "multipack": "Multipack {pieces} pcs",
        "not_on_sale": "Not on sale",
        "summary": "{where}: {product} for {price}",
        "value_package": "package price",
        "value_half_liter": "price per 0.5 l",
    },
}


def resolve_language(option: str | None, ha_language: str | None, country: str) -> str:
    """Zvolený jazyk; "auto" = jazyk HA, když ho známe, jinak podle země."""
    if option in LANGUAGES:
        return option
    base = (ha_language or "").split("-")[0].lower()
    if base in LANGUAGES:
        return base
    return "sk" if country == "SK" else "cs"


def text(language: str, key: str, **values: object) -> str:
    template = TEXTS.get(language, TEXTS["cs"]).get(key) or TEXTS["cs"][key]
    return template.format(**values)
