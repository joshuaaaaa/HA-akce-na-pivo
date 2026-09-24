from datetime import date

from akce_na_pivo.generic import parse_jsonld
from akce_na_pivo.kupi import (
    chain_key,
    is_nonalcoholic,
    match_brand,
    parse_offers,
    parse_unit_price,
    parse_validity,
    parse_volume,
)

TODAY = date(2026, 9, 23)

HTML = """
<h1>Pivo v akci</h1>
<div class="product--wrap" data-product-id="11">
  <div class="product_image"><a href="/sleva/pivo-pilsner-urquell"><img data-src="/img/pu.jpg" src="data:image/gif;base64,xx"></a></div>
  <div class="product_name"><h2><a title="Pilsner Urquell ležák" href="/sleva/pivo-pilsner-urquell">Pilsner Urquell</a>
     <span class="nowrap">0,5&nbsp;l</span></h2></div>
  <div class="discount_row" data-product="11" data-discount="100">
    <div class="discounts_shop_name"><a href="/obchod/albert">Albert Hypermarket</a></div>
    <span class="discount_price_value">24,90&nbsp;Kč</span>
    <span class="discount_amount">/ 0,5 l</span>
    <span class="discount_percentage">–31 %</span>
    <span class="price_per_unit">49,80 Kč / 1 l</span>
    <span class="discounts_validity">st 23. 9. – út 29. 9.</span>
    <a class="btn_link_leaflet" href="/letak/albert">leták</a>
  </div>
  <div class="discount_row" data-product="11" data-discount="101">
    <div class="discounts_shop_name"><a>Lidl</a></div>
    <span class="discount_price_value">139,90 Kč</span>
    <span class="discount_amount">/ 8 x 0,5 l</span>
    <span class="discounts_validity">čt 24. 9. – ne 27. 9.</span>
    Platí pro členy klubu Lidl Plus
  </div>
</div>
<div class="product--wrap" data-product-id="12">
  <div class="product_name"><h2><a title="Birell světlý nealko" href="/x">Birell</a></h2></div>
  <div class="discount_row" data-product="12" data-discount="200">
    <div class="discounts_shop_name"><a>Penny Market</a></div>
    <span class="discount_price_value">14,90 Kč</span>
    <span class="discount_amount">/ 0,5 l</span>
    <span class="discounts_validity">dnes končí</span>
  </div>
</div>
"""


def test_parse_offers_listing():
    offers = parse_offers(HTML, "https://www.kupi.cz/slevy/pivo", TODAY)
    assert len(offers) == 3
    albert, lidl, penny = offers
    assert albert["product"] == "Pilsner Urquell ležák 0,5 l"
    assert albert["shop"] == "Albert Hypermarket"
    assert albert["chain"] == "albert"
    assert albert["price"] == 24.9
    assert albert["price_per_liter"] == 49.8
    assert albert["price_per_half_liter"] == 24.9
    assert albert["discount_percent"] == 31
    assert albert["old_price"] == 36.09
    assert albert["valid_from"] == "2026-09-23"
    assert albert["valid_to"] == "2026-09-29"
    assert albert["url"] == "https://www.kupi.cz/letak/albert"
    assert albert["image"] == "https://www.kupi.cz/img/pu.jpg"
    assert not albert["loyalty"]

    assert lidl["pieces"] == 8
    assert lidl["price_per_piece"] == 17.49
    assert lidl["price_per_half_liter"] == 17.49
    assert lidl["loyalty"]
    assert lidl["valid_from"] == "2026-09-24"

    assert penny["chain"] == "penny"
    assert penny["valid_to"] == "2026-09-23"
    assert penny["nonalcoholic"]


def test_jsonld_fallback():
    html = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product",
    "name":"Pivo Gambrinus","image":"x.jpg","offers":{"@type":"AggregateOffer","lowPrice":"17.9",
    "offers":[{"@type":"Offer","offeredBy":"Kaufland","price":"17.9","priceCurrency":"CZK","priceValidUntil":"2026-09-30"}]}}</script>"""
    offers = parse_jsonld(html, "https://www.kupi.cz/sleva/pivo-gambrinus", TODAY, "kupi")
    assert len(offers) == 1
    assert offers[0]["shop"] == "Kaufland"
    assert offers[0]["price"] == 17.9
    assert offers[0]["valid_to"] == "2026-09-30"


def test_volume_and_unit():
    assert parse_volume("10 x 0,5 l") == (10, 0.5)
    assert parse_volume("4× 330 ml") == (4, 0.33)
    assert parse_volume("", "Kozel 11 1,5l") == (1, 1.5)
    assert parse_unit_price("39,80 Kč / 1 l") == 39.8
    assert parse_unit_price("19,90 Kč / 0,5 l") == 39.8


def test_validity():
    assert parse_validity("zítra končí", TODAY) == (TODAY, date(2026, 9, 24))
    assert parse_validity("platí do 30. 9.", TODAY) == (TODAY, date(2026, 9, 30))
    assert parse_validity("po 28. 12. – ne 3. 1.", TODAY) == (date(2026, 12, 28), date(2027, 1, 3))


def test_brand_and_chain():
    assert match_brand("Velkopopovický Kozel 11 0,5 l", ["Pilsner Urquell", "Kozel"]) == "Kozel"
    assert match_brand("Budweiser Budvar B:Original", ["Budweiser Budvar"]) == "Budweiser Budvar"
    assert match_brand("Svijanský Máz 11", ["Svijany"]) == "Svijany"
    assert match_brand("Moje Pivo", ["moje pivo"]) == "moje pivo"
    assert match_brand("Gambrinus", ["Kozel"]) is None
    assert chain_key("Tesco Hypermarket") == "tesco"
    assert chain_key("COOP") == "coop"
    assert not is_nonalcoholic("Radegast 10 % 0,5 l")
    assert is_nonalcoholic("Pilsner Urquell nealko 0,0 %")


def test_listing_row_without_product_id_uses_nearest_name():
    html = """
    <h1>Akce na pivo levně</h1>
    <div class="product">
      <div class="product_name"><h2><a title="Gambrinus Originál 10">Gambrinus</a></h2></div>
      <div class="discount_row">
        <div class="discounts_shop_name"><a>Tesco</a></div>
        <span class="discount_price_value">15,90 Kč</span>
      </div>
    </div>
    """
    offers = parse_offers(html, "https://www.kupi.cz/slevy/pivo", TODAY)
    assert [o["product"] for o in offers] == ["Gambrinus Originál 10"]
