"""Constants for the Akce na pivo integration."""

from __future__ import annotations

DOMAIN = "akce_na_pivo"
NAME = "Akce na pivo"

PLATFORMS = ["sensor", "binary_sensor", "button"]

# Config / options keys
CONF_BRANDS = "brands"
CONF_LOCATION_ENTITY = "location_entity"
CONF_UPDATE_TIME = "update_time"
CONF_TOP_COUNT = "top_count"
CONF_SORT_BY = "sort_by"
CONF_MAX_DISTANCE_KM = "max_distance_km"
CONF_REQUIRE_NEARBY_STORE = "require_nearby_store"
CONF_EXCLUDE_LOYALTY = "exclude_loyalty"
CONF_INCLUDE_UPCOMING = "include_upcoming"
CONF_PRICE_ALERT = "price_alert"
CONF_EXCLUDE_NONALCOHOLIC = "exclude_nonalcoholic"
CONF_PACKAGING = "packaging"
CONF_INCLUDE_UNKNOWN_PACKAGING = "include_unknown_packaging"

# Obal piva
PACKAGING_GLASS = "glass"
PACKAGING_CAN = "can"
PACKAGING_PET = "pet"
PACKAGING_OPTIONS = [PACKAGING_GLASS, PACKAGING_CAN, PACKAGING_PET]

# Stupňovitost piva
CONF_DEGREES = "degrees"

# Typ obchodu: kamenné i online / jen kamenné / jen online
CONF_SHOP_TYPE = "shop_type"
SHOP_TYPE_ALL = "all"
SHOP_TYPE_PHYSICAL = "physical"
SHOP_TYPE_ONLINE = "online"
SHOP_TYPE_OPTIONS = [SHOP_TYPE_ALL, SHOP_TYPE_PHYSICAL, SHOP_TYPE_ONLINE]
CONF_INCLUDE_UNKNOWN_DEGREE = "include_unknown_degree"
DEGREE_OPTIONS = ["10", "11", "12", "other"]
CONF_MAX_PAGES = "max_pages"

SORT_UNIT = "unit"  # cena za 0,5 l
SORT_PRICE = "price"  # cena za balení
SORT_DISTANCE = "distance"  # nejbližší obchod, pak cena
SORT_OPTIONS = [SORT_UNIT, SORT_PRICE, SORT_DISTANCE]

ALL_BRANDS = "__all__"

DEFAULT_BRANDS = ["Pilsner Urquell", "Kozel", "Gambrinus"]
# Stahuje se jednou denně v noci – HA je nejméně vytížený a nové letáky už jsou venku.
DEFAULT_UPDATE_TIME = "01:00:00"
OLD_DEFAULT_UPDATE_TIME = "07:00:00"  # výchozí čas ve verzích do 1.9 (převádí se na 1:00)
# zmeškané noční stahování se po startu HA provede až s odstupem
STARTUP_REFRESH_DELAY_MINUTES = 5
DEFAULT_TOP_COUNT = 5
DEFAULT_SORT_BY = SORT_UNIT
DEFAULT_MAX_DISTANCE_KM = 15
DEFAULT_REQUIRE_NEARBY_STORE = False
DEFAULT_EXCLUDE_LOYALTY = False
DEFAULT_INCLUDE_UPCOMING = True
DEFAULT_PRICE_ALERT = 15.0  # Kč za 0,5 l
DEFAULT_EXCLUDE_NONALCOHOLIC = False
DEFAULT_PACKAGING = [PACKAGING_GLASS, PACKAGING_CAN, PACKAGING_PET]
DEFAULT_INCLUDE_UNKNOWN_PACKAGING = True
DEFAULT_DEGREES = list(DEGREE_OPTIONS)
DEFAULT_INCLUDE_UNKNOWN_DEGREE = True
DEFAULT_SHOP_TYPE = SHOP_TYPE_ALL
DEFAULT_MAX_PAGES = 6

MAX_TOP_COUNT = 10

# Známé značky: zobrazovaný název -> (aliasy pro hledání v názvu produktu, slug na kupi.cz)
KNOWN_BRANDS: dict[str, tuple[tuple[str, ...], str]] = {
    "Pilsner Urquell": (("pilsner urquell", "plzensky prazdroj"), "pivo-pilsner-urquell"),
    "Gambrinus": (("gambrinus",), "pivo-gambrinus"),
    "Kozel": (("kozel",), "pivo-velkopopovicky-kozel"),
    "Radegast": (("radegast",), "pivo-radegast"),
    "Staropramen": (("staropramen",), "pivo-staropramen"),
    "Budweiser Budvar": (("budvar", "budweiser"), "pivo-budweiser-budvar"),
    "Bernard": (("bernard",), "pivo-bernard"),
    "Krušovice": (("krusovice",), "pivo-krusovice"),
    "Starobrno": (("starobrno",), "pivo-starobrno"),
    "Braník": (("branik",), "pivo-branik"),
    "Ostravar": (("ostravar",), "pivo-ostravar"),
    "Svijany": (("svijan",), "pivo-svijany"),
    "Rohozec": (("rohozec", "skalak"), "pivo-rohozec"),
    "Primátor": (("primator",), "pivo-primator"),
    "Zubr": (("zubr",), "pivo-zubr"),
    "Holba": (("holba",), "pivo-holba"),
    "Lobkowicz": (("lobkowicz",), "pivo-lobkowicz"),
    "Březňák": (("breznak",), "pivo-breznak"),
    "Samson": (("samson",), "pivo-samson"),
    "Radler": (("radler",), "pivo-radler"),
    "Birell (nealko)": (("birell",), "pivo-birell"),
    "Heineken": (("heineken",), "pivo-heineken"),
    "Plzeň (vše z Prazdroje)": (("pilsner", "gambrinus", "kozel", "radegast"), ""),
    # slovenské značky
    "Zlatý Bažant": (("zlaty bazant", "golden pheasant"), "pivo-zlaty-bazant"),
    "Šariš": (("saris",), "pivo-saris"),
    "Corgoň": (("corgon",), "pivo-corgon"),
    "Topvar": (("topvar",), "pivo-topvar"),
    "Smädný mních": (("smadny mnich",), "pivo-smadny-mnich"),
    "Kelt": (("kelt",), "pivo-kelt"),
    "Steiger": (("steiger",), "pivo-steiger"),
    "Martiner": (("martiner",), "pivo-martiner"),
    "Urpiner": (("urpiner",), "pivo-urpiner"),
    "Popper": (("popper",), "pivo-popper"),
}

# Slova, podle kterých poznáme nealko pivo (porovnává se s textem bez diakritiky)
NONALCOHOLIC_WORDS = (
    "nealko",
    "birell",
    "alkohol free",
    "alcohol free",
    "bezalkohol",
    "nealkoholicke",
)

# Názvy obchodních řetězců, jak je uvádí kupi.cz -> klíč pro vyhledání v OpenStreetMap
CHAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "albert": ("albert",),
    "billa": ("billa",),
    "globus": ("globus",),
    "kaufland": ("kaufland",),
    "lidl": ("lidl",),
    "penny": ("penny",),
    "tesco": ("tesco",),
    "makro": ("makro",),
    "norma": ("norma",),
    "coop": ("coop", "jednota", "tempo", "terno"),
    "tamda": ("tamda",),
    "flop": ("flop",),
    "hruska": ("hruska",),
    "terno": ("terno",),
    "trefa": ("trefa",),
    "ratio": ("ratio",),
    "brnenka": ("brnenka",),
    "cba": ("cba",),
    "zabka": ("zabka",),
    "tesco express": ("tesco",),
    "potraviny cz": ("potraviny cz",),
    "enapo": ("enapo",),
    "rohlik": ("rohlik",),
    "kosik": ("kosik",),
    "jip": ("jip",),
    "travel free": ("travel free",),
    "tuty": ("tuty",),
    # slovenské řetězce
    "fresh": ("fresh",),
    "kraj": ("kraj",),
    "koruna": ("koruna",),
    "metro": ("metro",),
    "klas": ("klas",),
    "moja samoska": ("moja samoska", "samoska"),
    "milk agro": ("milk agro", "milk-agro"),
    "kon rad": ("kon rad", "kon-rad"),
    "yeme": ("yeme",),
}

# Zobrazované názvy řetězců – podle nich obecný parser pozná obchod v textu stránky
CHAIN_NAMES: dict[str, str] = {
    "albert": "Albert",
    "billa": "Billa",
    "globus": "Globus",
    "kaufland": "Kaufland",
    "lidl": "Lidl",
    "penny": "Penny",
    "tesco": "Tesco",
    "makro": "Makro",
    "norma": "Norma",
    "coop": "COOP",
    "tamda": "Tamda",
    "flop": "Flop",
    "hruska": "Hruška",
    "terno": "Terno",
    "trefa": "Trefa",
    "ratio": "Ratio",
    "brnenka": "Brněnka",
    "cba": "CBA",
    "zabka": "Žabka",
    "jip": "JIP",
    "travel free": "Travel Free",
    "tuty": "COOP Tuty",
    "rohlik": "Rohlik.cz",
    "kosik": "Košík.cz",
    "fresh": "Fresh",
    "kraj": "Kraj",
    "koruna": "Koruna",
    "metro": "Metro",
    "klas": "Klas",
    "moja samoska": "Moja Samoška",
    "milk agro": "Milk-Agro",
    "kon rad": "KON-RAD",
    "yeme": "Yeme",
}

# Online obchody – nemají kamennou pobočku
ONLINE_SHOPS = (
    "rohlik",
    "kosik",
    "tesco online",
    "albert online",
    "online",
    "e-shop",
    "eshop",
    "kosik.sk",
    "potravinydomov",
    "freshbox",
    "mall.cz",
    "alza",
)

# Zdroje akcí. URL šablony: {query} = hledaný text, {slug} = značka ve tvaru "pilsner-urquell".
# Adresy mimo kupi.cz nešlo při vývoji ověřit – lze je přepsat v nastavení (vlastní URL).
CONF_SOURCES = "sources"
CONF_CUSTOM_URLS = "custom_urls"
SOURCE_KUPI = "kupi"
SOURCE_KOMPASSLEV = "kompasslev"
SOURCE_AKCNICENY = "akcniceny"
SOURCE_CENITO = "cenito"
SOURCE_CUSTOM = "custom"
SOURCE_ZLACNENE = "zlacnene"
SOURCE_KIMBINO = "kimbino"
SOURCE_LETAKOMAT = "letakomat"
SOURCE_KDEJEAKCIA = "kdejeakcia"
SOURCE_KOMPASZLIAV = "kompaszliav"
SOURCE_KUPINO = "kupino"
SOURCE_AKCNELETAKY = "akcneletaky"
SOURCE_PROMOTHEUS = "promotheus"

SOURCES: dict[str, dict] = {
    SOURCE_KUPI: {
        "country": "CZ",
        "name": "Kupi.cz",
        "listing": ("https://www.kupi.cz/slevy/pivo",),
        "brand": (),
        "pages": True,
    },
    SOURCE_KOMPASSLEV: {
        "country": "CZ",
        "name": "Kompas Slev",
        "listing": ("https://kompasslev.cz/produkty/pivo", "https://kompasslev.cz/pivo"),
        "brand": ("https://kompasslev.cz/produkty/{slug}",),
        "pages": False,
    },
    SOURCE_AKCNICENY: {
        "country": "CZ",
        "name": "AkcniCeny.cz",
        "listing": (
            "https://www.akcniceny.cz/hledat/?q=pivo",
            "https://www.akcniceny.cz/vyhledavani/?q=pivo",
        ),
        "brand": (
            "https://www.akcniceny.cz/hledat/?q={query}",
            "https://www.akcniceny.cz/vyhledavani/?q={query}",
        ),
        "pages": False,
    },
    SOURCE_CENITO: {
        "country": "CZ",
        "name": "Cenito",
        "listing": (
            "https://cenito.cz/hledat?q=pivo",
            "https://cenito.cz/vyhledavani?q=pivo",
            "https://cenito.cz/search?q=pivo",
        ),
        "brand": (
            "https://cenito.cz/hledat?q={query}",
            "https://cenito.cz/vyhledavani?q={query}",
            "https://cenito.cz/search?q={query}",
        ),
        "pages": False,
    },
    # Slovensko – adresy ověřené přes vyhledávač (září 2026), {slug} = "zlaty-bazant"
    SOURCE_ZLACNENE: {
        "country": "SK",
        "name": "Zlacnene.sk",
        "listing": ("https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/",),
        "brand": ("https://www.zlacnene.sk/akciovy-tovar/znacka-{slug}/",),
        "pages": False,
    },
    SOURCE_KIMBINO: {
        "country": "SK",
        "name": "Kimbino.sk",
        "listing": ("https://www.kimbino.sk/produkty/pivo/",),
        "brand": ("https://www.kimbino.sk/produkty/{slug}/",),
        "pages": False,
    },
    SOURCE_LETAKOMAT: {
        "country": "SK",
        "name": "Letakomat.sk",
        "listing": ("https://www.letakomat.sk/hladat/?q=pivo",),
        "brand": ("https://www.letakomat.sk/hladat/?q={slug}",),
        "pages": False,
    },
    SOURCE_KDEJEAKCIA: {
        "country": "SK",
        "name": "KdeJeAkcia.sk",
        "listing": ("https://kdejeakcia.sk/kde-je-pivo-v-akcii",),
        "brand": ("https://kdejeakcia.sk/kde-je-{slug}-v-akcii",),
        "pages": False,
    },
    SOURCE_KOMPASZLIAV: {
        "country": "SK",
        "name": "Kompas Zliav",
        "listing": ("https://kompaszliav.sk/produkty/pivo",),
        "brand": ("https://kompaszliav.sk/produkty/{slug}",),
        "pages": False,
    },
    SOURCE_KUPINO: {
        "country": "SK",
        "name": "Kupino.sk",
        "listing": ("https://www.kupino.sk/akcia/pivo",),
        "brand": ("https://www.kupino.sk/akcia/{slug}",),
        "pages": False,
    },
    SOURCE_AKCNELETAKY: {
        "country": "SK",
        "name": "AkčnéLetáky.sk",
        "listing": ("https://www.akcneletaky.sk/akcie/Pivo",),
        "brand": ("https://www.akcneletaky.sk/akcie/{query}",),
        "pages": False,
    },
    SOURCE_PROMOTHEUS: {
        "country": "SK",
        "name": "Promotheus.sk",
        "listing": ("https://promotheus.sk/pivo",),
        "brand": ("https://promotheus.sk/{slug}",),
        "pages": False,
    },
}

CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"
COUNTRY_CZ = "CZ"
COUNTRY_SK = "SK"
DEFAULT_COUNTRY = COUNTRY_CZ

# Nastavení podle země. bbox = hrubý obdélník (lat_min, lat_max, lon_min, lon_max),
# přesnou hranici řeší Overpass area.
COUNTRIES: dict[str, dict] = {
    COUNTRY_CZ: {
        "name": "Česká republika",
        "currency": "CZK",
        "symbol": "Kč",
        "currency_aliases": ("czk", "kc", ",-"),
        "bbox": (48.55, 51.06, 12.09, 18.86),
        "default_brands": ["Pilsner Urquell", "Kozel", "Gambrinus"],
        "default_alert": 15.0,
        "alert_max": 100,
        "alert_step": 0.1,
    },
    COUNTRY_SK: {
        "name": "Slovensko",
        "currency": "EUR",
        "symbol": "€",
        "currency_aliases": ("eur", "€"),
        "bbox": (47.73, 49.61, 16.83, 22.57),
        "default_brands": ["Zlatý Bažant", "Šariš", "Corgoň"],
        "default_alert": 0.7,
        "alert_max": 5,
        "alert_step": 0.01,
    },
}


def country_sources(country: str) -> list[str]:
    return [key for key, spec in SOURCES.items() if spec["country"] == country]


KUPI_BASE_URL = "https://www.kupi.cz"
KUPI_SEARCH_URL = "https://www.kupi.cz/hledej?f={query}"
KUPI_PRODUCT_URL = "https://www.kupi.cz/sleva/{slug}"

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
OSM_USER_AGENT = "HomeAssistant-AkceNaPivo/1.0 (+https://github.com/joshuaaaaa/HA-akce-na-pivo)"

STORE_CACHE_DAYS = 7
RELOCATE_DISTANCE_KM = 2.0
HISTORY_DAYS = 120

EVENT_CHEAP_BEER = f"{DOMAIN}_levne_pivo"
SERVICE_REFRESH = "refresh"


DEFAULT_SOURCES = country_sources(COUNTRY_CZ)
