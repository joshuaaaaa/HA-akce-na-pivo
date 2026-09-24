"""Test nastavení integrace v Home Assistantu (spustí se, jen když je HA nainstalovaný)."""

import re
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.akce_na_pivo.const import DOMAIN, EVENT_CHEAP_BEER  # noqa: E402

from .test_generic import KOMPAS_LIKE  # noqa: E402
from .test_kupi import HTML  # noqa: E402

KOMPAS_PU = """
<div class="card"><h3>Pilsner Urquell 0,5 l</h3><span>Kaufland</span><b>19,90 Kč</b><i>23.9. - 29.9.</i></div>
"""

OVERPASS = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": 50.08,
            "lon": 14.43,
            "tags": {
                "shop": "supermarket",
                "brand": "Albert",
                "name": "Albert Supermarket",
                "addr:street": "Vodičkova",
                "addr:housenumber": "10",
                "addr:city": "Praha",
                "addr:postcode": "11000",
            },
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 50.10, "lon": 14.50},
            "tags": {
                "shop": "supermarket",
                "brand": "Lidl",
                "name": "Lidl",
                "addr:street": "Kolbenova",
                "addr:housenumber": "5",
                "addr:city": "Praha",
            },
        },
        {
            "type": "node",
            "id": 3,
            "lat": 50.09,
            "lon": 14.45,
            "tags": {"shop": "supermarket", "brand": "Penny", "name": "Penny"},
        },
        # pobočky v zahraničí se musí zahodit (Penny v DE je blíž než ta v Praze)
        {
            "type": "node",
            "id": 4,
            "lat": 50.088,
            "lon": 14.422,
            "tags": {"shop": "supermarket", "brand": "Penny", "addr:country": "DE"},
        },
        {
            "type": "node",
            "id": 5,
            "lat": 48.2,
            "lon": 16.37,
            "tags": {"shop": "supermarket", "brand": "Albert"},
        },
    ]
}


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    # bez pauz mezi požadavky (se zmrazeným časem by asyncio.sleep nikdy neskončil)
    with (
        patch("custom_components.akce_na_pivo.coordinator.REQUEST_DELAY", 0),
        patch("custom_components.akce_na_pivo.coordinator.NOMINATIM_DELAY", 0),
    ):
        yield


async def test_flow_and_setup(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.latitude, hass.config.longitude = 50.087, 14.421
    aioclient_mock.get("https://www.kupi.cz/slevy/pivo", text=HTML)
    aioclient_mock.get("https://www.kupi.cz/slevy/pivo?page=2", text="<html></html>")
    aioclient_mock.get("https://www.kupi.cz/hledej?f=Moje+Pivo", text="<html></html>")
    aioclient_mock.get("https://kompasslev.cz/produkty/pivo", text=KOMPAS_LIKE)
    aioclient_mock.get("https://kompasslev.cz/produkty/pilsner-urquell", text=KOMPAS_PU)
    # ostatní adresy (AkcniCeny, Cenito, neznámé značky) neexistují
    aioclient_mock.get(
        re.compile(r"^https://(www\.akcniceny\.cz|cenito\.cz|kompasslev\.cz)/"), status=404
    )
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=OVERPASS)
    aioclient_mock.get(
        "https://nominatim.openstreetmap.org/reverse",
        json={
            "address": {
                "road": "Seifertova",
                "house_number": "1",
                "city": "Praha",
                "postcode": "13000",
            }
        },
    )
    events = []
    hass.bus.async_listen(EVENT_CHEAP_BEER, events.append)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Pivo", "language": "cs", "country": "CZ"}
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "brands": ["Pilsner Urquell", "Birell (nealko), Moje Pivo"],
            "sources": ["kupi", "kompasslev", "akcniceny", "cenito"],
            "custom_urls": "",
            "update_time": "07:30:00",
            "update_interval_hours": 0,
            "top_count": 5,
            "sort_by": "unit",
            "max_distance_km": 15,
            "require_nearby_store": False,
            "price_alert": 18,
            "include_upcoming": True,
            "exclude_loyalty": False,
            "exclude_nonalcoholic": False,
            "max_pages": 3,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["brands"] == ["Pilsner Urquell", "Birell (nealko)", "Moje Pivo"]
    await hass.async_block_till_done()

    cheapest = hass.states.get("sensor.pivo_nejlevnejsi_pivo") or hass.states.get(
        "sensor.pivo_cheapest_beer"
    )
    assert cheapest is not None, [s.entity_id for s in hass.states.async_all()]
    top = cheapest.attributes["offers"]
    # Birell 14,90 Kč/0,5 l, Pilsner Urquell 24,90 Kč; Lidl multipack začíná až zítra
    assert [o["shop"] for o in top] == ["Penny Market", "Kaufland", "Albert Hypermarket"]
    assert top[1]["source"] == "kompasslev"
    assert cheapest.attributes["source_names"]["kompasslev"] == "Kompas Slev"
    assert float(cheapest.state) == 14.9
    assert top[0]["address"] == "Seifertova 1, 13000 Praha"
    assert top[0]["latitude"] == 50.09  # ne bližší Penny v DE
    overpass_query = next(
        c[2]["data"] for c in aioclient_mock.mock_calls if "overpass" in str(c[1])
    )
    assert "area(id:3600051684)" in overpass_query  # území ČR
    assert top[2]["address"] == "Vodičkova 10, 11000 Praha"
    assert top[2]["distance_km"] < 2
    assert "Končí dnes" in top[0]["flags"]
    assert cheapest.attributes["upcoming"][0]["shop"] == "Lidl"

    where = hass.states.get("sensor.pivo_where_to_buy_beer")
    assert where.state == "Penny"
    assert where.attributes["summary"].startswith("Penny, Seifertova 1, 13000 Praha")
    where_pu = hass.states.get("sensor.pivo_where_to_buy_pilsner_urquell")
    assert where_pu.state == "Kaufland"  # Kompas Slev 19,90 Kč < Albert 24,90 Kč
    moje = hass.states.get("sensor.pivo_where_to_buy_moje_pivo")
    assert moje.state == "Není v akci" and moje.attributes["on_sale"] is False
    assert cheapest.attributes["not_on_sale"] == ["Moje Pivo"]
    brand_price = hass.states.get("sensor.pivo_moje_pivo")
    assert brand_price.state == "unknown" and brand_price.attributes["status"] == "Není v akci"

    rank1 = [s for s in hass.states.async_all("sensor") if s.attributes.get("rank") == 1]
    assert rank1 and rank1[0].attributes["latitude"] == 50.09

    binary = hass.states.async_all("binary_sensor")[0]
    assert binary.state == "on"
    assert len(events) == 1 and events[0].data["shop"] == "Penny Market"

    count = [s for s in hass.states.async_all("sensor") if "matching_by_source" in s.attributes][0]
    sources = count.attributes["sources"]
    assert sources["kupi"]["offers"] == 3
    assert sources["kompasslev"]["offers"] == 3
    assert sources["cenito"]["offers"] == 0 and sources["cenito"]["errors"]
    stats = count.attributes["filter"]
    assert stats["downloaded"] >= 6 and stats["matching"] == 4
    assert stats["brand_mismatch"] == 2  # Kozel a Gambrinus z Kompasu Slev nejsou vybrané
    assert any("Pilsner Urquell" in line for line in stats["sample_products"])

    # telefon v zahraničí -> vzdálenosti se počítají od domova v ČR
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    hass.states.async_set("person.test", "not_home", {"latitude": 45.8, "longitude": 15.97})
    with_entity = {**coordinator.options, "location_entity": "person.test"}
    with patch.object(type(coordinator), "options", new=property(lambda self: with_entity)):
        lat, lon, source = coordinator.current_location()
    assert (lat, lon) == (50.087, 14.421) and "mimo CZ" in source

    # opakovaná aktualizace nesmí znovu poslat stejnou událost
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.async_block_till_done()
    assert len(events) == 1

    # options flow
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert await hass.config_entries.async_unload(entry.entry_id)


SK_HTML = """
<div class="offer">
  <h3>Zlatý Bažant 12% svetlý ležiak 0,5 l</h3>
  <span class="shop">Kaufland</span>
  <span class="price-old">1,19 €</span> <span class="price">0,69 €</span>
  <span>platí od 22. 9. do 28. 9.</span>
</div>
<div class="offer">
  <h3>Šariš 10 svetlé pivo 6 x 0,5 l</h3>
  <span class="shop">COOP Jednota</span>
  <span class="price">€ 4,49</span>
  <span>22.9. - 28.9.</span>
</div>
"""

SK_OVERPASS = {
    "elements": [
        {
            "type": "node",
            "id": 10,
            "lat": 48.15,
            "lon": 17.11,
            "tags": {
                "shop": "supermarket",
                "brand": "Kaufland",
                "addr:street": "Trnavská cesta",
                "addr:housenumber": "41",
                "addr:city": "Bratislava",
                "addr:postcode": "82108",
            },
        },
        {
            "type": "node",
            "id": 11,
            "lat": 48.14,
            "lon": 17.10,
            "tags": {
                "shop": "supermarket",
                "brand": "COOP Jednota",
                "name": "COOP Jednota",
                "addr:street": "Obchodná",
                "addr:housenumber": "1",
                "addr:city": "Bratislava",
            },
        },
        # pobočka v ČR se pro Slovensko nepoužije
        {
            "type": "node",
            "id": 12,
            "lat": 48.16,
            "lon": 17.10,
            "tags": {"shop": "supermarket", "brand": "Kaufland", "addr:country": "CZ"},
        },
    ]
}


async def test_slovakia(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.latitude, hass.config.longitude = 48.148, 17.107  # Bratislava
    aioclient_mock.get(
        "https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/", text=SK_HTML
    )
    aioclient_mock.get(re.compile(r"^https://"), status=404)
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=SK_OVERPASS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Pivo SK", "language": "sk", "country": "SK"}
    )
    assert result["step_id"] == "settings"
    source_options = [o["value"] for o in result["data_schema"].schema["sources"].config["options"]]
    assert "zlacnene" in source_options and "kupi" not in source_options
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "brands": ["Zlatý Bažant", "Šariš"],
            "sources": source_options,
            "update_time": "07:00:00",
            "update_interval_hours": 0,
            "top_count": 5,
            "sort_by": "unit",
            "max_distance_km": 15,
            "require_nearby_store": False,
            "price_alert": 0.7,
            "include_upcoming": True,
            "exclude_loyalty": False,
            "exclude_nonalcoholic": False,
            "max_pages": 1,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["country"] == "SK"
    await hass.async_block_till_done()

    cheapest = hass.states.get("sensor.pivo_sk_cheapest_beer")
    assert cheapest is not None
    assert cheapest.attributes["unit_of_measurement"] == "EUR"
    assert cheapest.attributes["currency_symbol"] == "€"
    top = cheapest.attributes["offers"]
    # 0,69 € za 0,5 l vs. multipack 4,49 € / 6 = 0,75 € za 0,5 l
    assert [o["shop"] for o in top] == ["Kaufland", "COOP"]
    assert top[0]["price"] == 0.69 and top[0]["old_price"] == 1.19
    assert (top[0]["valid_from"], top[0]["valid_to"]) == ("2026-09-22", "2026-09-28")
    assert top[0]["address"] == "Trnavská cesta 41, 82108 Bratislava"
    assert top[1]["price"] == 4.49 and top[1]["price_per_half_liter"] == 0.75
    assert all(o["currency"] == "EUR" for o in top)
    assert "Pod limitom 0.7 €/0,5 l" in top[0]["flags"]  # slovenské texty
    assert "below_limit" in top[0]["flag_keys"]

    query = next(c[2]["data"] for c in aioclient_mock.mock_calls if "overpass" in str(c[1]))
    assert "area(id:3600014296)" in query  # území SK

    where = hass.states.get("sensor.pivo_sk_where_to_buy_beer")
    assert where.state == "Kaufland"
    assert "0,69 €" in where.attributes["summary"]
    assert hass.states.get("sensor.pivo_sk_where_to_buy_saris").state == "COOP Jednota"
    assert cheapest.attributes["language"] == "sk"


async def test_packaging_filter(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    """Jen plech – sklo a akce bez údaje o obalu se vyřadí."""
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.latitude, hass.config.longitude = 48.148, 17.107
    html = (
        SK_HTML.replace("svetlý ležiak 0,5 l", "svetlý ležiak fľaša 0,5 l")
        + """
    <div class="offer"><h3>Zlatý Bažant 10 plechovka 0,5 l</h3><span>Lidl</span>
      <span class="price">0,79 €</span><span>22.9. - 28.9.</span></div>"""
    )
    aioclient_mock.get("https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/", text=html)
    aioclient_mock.get(re.compile(r"^https://"), status=404)
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=SK_OVERPASS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Plech", "country": "SK"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "brands": ["Zlatý Bažant", "Šariš"],
            "packaging": ["can"],
            "include_unknown_packaging": False,
            "sources": ["zlacnene"],
            "update_time": "07:00:00",
            "update_interval_hours": 0,
            "top_count": 5,
            "sort_by": "unit",
            "max_distance_km": 15,
            "require_nearby_store": False,
            "price_alert": 0.7,
            "include_upcoming": True,
            "exclude_loyalty": False,
            "exclude_nonalcoholic": False,
            "max_pages": 1,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["packaging"] == ["can"]
    await hass.async_block_till_done()

    offers = hass.states.get("sensor.plech_cheapest_beer").attributes["offers"]
    assert [(o["product"], o["packaging"]) for o in offers] == [
        ("Zlatý Bažant 10 plechovka 0,5 l", "can")
    ]
    count = [s for s in hass.states.async_all("sensor") if "filter" in s.attributes][0]
    assert count.attributes["filter"]["packaging_excluded"] == 2


async def test_degree_filter(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    """Jen dvanáctky: Zlatý Bažant 12% zůstane, Šariš 10 se vyřadí."""
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.latitude, hass.config.longitude = 48.148, 17.107
    aioclient_mock.get(
        "https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/", text=SK_HTML
    )
    aioclient_mock.get(re.compile(r"^https://"), status=404)
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=SK_OVERPASS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Dvanactka", "country": "SK"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "brands": ["Zlatý Bažant", "Šariš"],
            "degrees": ["12"],
            "include_unknown_degree": False,
            "sources": ["zlacnene"],
            "update_time": "07:00:00",
            "update_interval_hours": 0,
            "top_count": 5,
            "sort_by": "unit",
            "max_distance_km": 15,
            "require_nearby_store": False,
            "price_alert": 0.7,
            "include_upcoming": True,
            "exclude_loyalty": False,
            "exclude_nonalcoholic": False,
            "max_pages": 1,
        },
    )
    assert result["options"]["degrees"] == ["12"]
    await hass.async_block_till_done()

    cheapest = hass.states.get("sensor.dvanactka_cheapest_beer")
    assert [(o["product"], o["degree"]) for o in cheapest.attributes["offers"]] == [
        ("Zlatý Bažant 12% svetlý ležiak 0,5 l", 12)
    ]
    assert cheapest.attributes["not_on_sale"] == ["Šariš"]
    count = [s for s in hass.states.async_all("sensor") if "filter" in s.attributes][0]
    assert count.attributes["filter"]["degree_excluded"] == 1


async def test_language_auto_follows_home_assistant(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    """Jazyk "auto" = jazyk HA (tady angličtina); "Není v akci" se přeloží."""
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.language = "en"
    hass.config.latitude, hass.config.longitude = 48.148, 17.107
    aioclient_mock.get(
        "https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/", text=SK_HTML
    )
    aioclient_mock.get(re.compile(r"^https://"), status=404)
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=SK_OVERPASS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Auto", "language": "auto", "country": "SK"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"brands": ["Zlatý Bažant", "Topvar"], "sources": ["zlacnene"], "max_pages": 1},
    )
    assert result["options"]["language"] == "auto"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.auto_where_to_buy_topvar").state == "Not on sale"

    # jazyk jde změnit v Konfiguraci
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "language" in result["data_schema"].schema
    allowed = {str(key) for key in result["data_schema"].schema}
    values = {k: v for k, v in entry.options.items() if k in allowed}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**values, "language": "sk"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.auto_where_to_buy_topvar").state == "Nie je v akcii"


ONLINE_HTML = (
    SK_HTML
    + """
<div class="offer">
  <h3>Zlatý Bažant 10 svetlé pivo 0,5 l</h3>
  <span class="shop">Košík.sk</span>
  <span class="price">0,59 €</span>
  <span>22.9. - 28.9.</span>
</div>
"""
)


@pytest.mark.parametrize(
    ("shop_type", "expected"),
    [
        ("physical", {"Kaufland", "COOP"}),
        ("online", {"Košík.cz"}),
        ("all", {"Kaufland", "COOP", "Košík.cz"}),
    ],
)
async def test_shop_type_filter(
    hass: HomeAssistant, aioclient_mock, freezer, shop_type, expected
) -> None:
    freezer.move_to("2026-09-23 10:00:00+02:00")
    hass.config.latitude, hass.config.longitude = 48.148, 17.107
    aioclient_mock.get(
        "https://www.zlacnene.sk/akciovy-tovar/napoje-alkoholicke/pivo/", text=ONLINE_HTML
    )
    aioclient_mock.get(re.compile(r"^https://"), status=404)
    aioclient_mock.post("https://overpass-api.de/api/interpreter", json=SK_OVERPASS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Obchody", "language": "sk", "country": "SK"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "brands": ["Zlatý Bažant", "Šariš"],
            "sources": ["zlacnene"],
            "shop_type": shop_type,
            "packaging": ["can"],
            "max_pages": 1,
        },
    )
    assert result["options"]["shop_type"] == shop_type
    await hass.async_block_till_done()

    cheapest = hass.states.get("sensor.obchody_cheapest_beer")
    offers = cheapest.attributes["offers"]
    assert {o["shop"] for o in offers} == expected
    assert all(o["online"] for o in offers) if shop_type == "online" else True
    # karty dostanou, co je v nastavení vybrané
    assert cheapest.attributes["selected"] == {
        "packaging": ["can"],
        "degrees": ["10", "11", "12", "other"],
        "shop_type": shop_type,
    }
