"""Obecný parser akčních nabídek pro weby bez známé struktury.

Používá se pro Kompas Slev, AkcniCeny.cz, Cenito a vlastní URL zadané uživatelem.
Zkouší postupně:
  1. strukturovaná data schema.org (JSON-LD: Product / Offer / ItemList),
  2. JSON vložený do stránky (Next.js __NEXT_DATA__, Nuxt, application/json),
  3. heuristiku nad HTML – nejmenší blok, který obsahuje cenu (Kč nebo €) a název řetězce.
Modul nezávisí na Home Assistantu.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Comment, Tag

from .const import CHAIN_ALIASES, CHAIN_NAMES, COUNTRIES, DEFAULT_COUNTRY
from .kupi import (
    build_offer,
    clean_text,
    make_soup,
    normalize,
    parse_validity,
    to_float,
)

_NUMBER = r"(?<![\d,.])(\d{1,4}(?:[,.]\d{1,2})?)"
PRICE_RES = {
    "CZ": re.compile(_NUMBER + r"\s*(?:Kč|kč|KČ|CZK|,-)"),
    "SK": re.compile(_NUMBER + r"\s*(?:€|EUR|eur|Eur)"),
}
PRICE_RE = PRICE_RES["CZ"]
# "€ 0,59" -> "0,59 €", aby stačil jeden regulární výraz
_EURO_PREFIX_RE = re.compile(r"(?:€|EUR)\s*(\d{1,4}(?:[,.]\d{1,2})?)(?![\d,.])")


def price_re(country: str) -> re.Pattern:
    return PRICE_RES.get(country, PRICE_RES[DEFAULT_COUNTRY])


def normalize_prices(text: str, country: str) -> str:
    if country == "SK":
        return _EURO_PREFIX_RE.sub(r"\1 €", text)
    return text


AMOUNT_RE = re.compile(r"(?:\d{1,2}\s*[x×]\s*)?\d+(?:[,.]\d+)?\s*(?:ml|l)\b", re.IGNORECASE)
DISCOUNT_RE = re.compile(r"[-–−]\s*(\d{1,2})\s*%")
DATE_RANGE_RE = re.compile(
    r"(?:od|plat[ií] od)\s+\d{1,2}\.\s*\d{1,2}\.(?:\s*\d{4})?\s+do\s+\d{1,2}\.\s*\d{1,2}\.(?:\s*\d{4})?"
    r"|(?:(?:od|platí od)\s*)?\d{1,2}\.\s*\d{1,2}\.(?:\s*\d{4})?\s*[-–]\s*(?:do\s*)?\d{1,2}\.\s*\d{1,2}\.(?:\s*\d{4})?"
    r"|(?:platí\s+)?do\s+\d{1,2}\.\s*\d{1,2}\.(?:\s*\d{4})?"
    r"|dnes končí|zítra končí|zajtra končí",
    re.IGNORECASE,
)
LOYALTY_WORDS = (
    "s kartou",
    "s aplikaci",
    "lidl plus",
    "clubcard",
    "moje billa",
    "muj albert",
    "penny karta",
    "cleny klubu",
    "vernostni",
    "s aplikaciou",
    "billa club",
    "moja billa",
    "kartou coop",
)
CARD_TAGS = ("article", "li", "div", "a", "tr", "section")
MAX_CARD_TEXT = 500

NAME_KEYS = ("name", "title", "productName", "product_name", "nazev", "label")
PRICE_KEYS = (
    "price",
    "actionPrice",
    "action_price",
    "salePrice",
    "sale_price",
    "currentPrice",
    "current_price",
    "discountPrice",
    "discount_price",
    "priceAction",
    "akcniCena",
    "cena",
    "priceWithVat",
    "finalPrice",
)
OLD_PRICE_KEYS = (
    "oldPrice",
    "old_price",
    "originalPrice",
    "original_price",
    "regularPrice",
    "priceBefore",
)
SHOP_KEYS = (
    "shop",
    "store",
    "retailer",
    "seller",
    "offeredBy",
    "shopName",
    "shop_name",
    "storeName",
    "store_name",
    "chain",
    "retailerName",
    "obchod",
    "merchant",
    "brandShop",
)
FROM_KEYS = ("validFrom", "valid_from", "dateFrom", "date_from", "from", "startDate", "start")
TO_KEYS = (
    "validTo",
    "valid_to",
    "validUntil",
    "dateTo",
    "date_to",
    "to",
    "endDate",
    "end",
    "priceValidUntil",
)
AMOUNT_KEYS = ("amount", "quantity", "volume", "package", "packageSize", "unit", "mnozstvi")
URL_KEYS = ("url", "link", "href", "slug")
IMAGE_KEYS = ("image", "imageUrl", "image_url", "img", "thumbnail", "picture")

_CHAIN_PATTERNS = [
    (key, re.compile(rf"(?<![a-z]){re.escape(alias)}(?![a-z])"))
    for key in sorted(CHAIN_ALIASES, key=len, reverse=True)
    for alias in (key, *CHAIN_ALIASES[key])
]


def detect_chain(*texts: str | None) -> str | None:
    """Najde v textu název obchodního řetězce a vrátí jeho zobrazovaný název."""
    for text in texts:
        norm = normalize(text).replace("-", " ").replace("_", " ")
        if not norm:
            continue
        for key, pattern in _CHAIN_PATTERNS:
            if pattern.search(norm):
                return CHAIN_NAMES.get(key, key.title())
    return None


def _chain_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    for key in ("store", "shop", "obchod", "retailer"):
        if query.get(key):
            return detect_chain(query[key][0])
    return None


def _price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if 0 < value < 10000 else None
    if isinstance(value, dict):
        for key in ("value", "amount", "price", "withVat", "czk"):
            if key in value:
                return _price(value[key])
        return None
    match = re.search(r"\d{1,4}(?:[,.]\d{1,2})?", str(value).replace("\xa0", " "))
    return to_float(match.group(0)) if match else None


def _date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            from datetime import datetime, timezone

            stamp = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


CURRENCY_KEYS = ("priceCurrency", "currency", "currencyCode", "mena")


def _foreign_currency(*objs: Any, country: str = DEFAULT_COUNTRY) -> bool:
    """True, když nabídka výslovně uvádí jinou měnu, než platí ve zvolené zemi."""
    allowed = COUNTRIES[country]["currency_aliases"]
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        value = _first(obj, CURRENCY_KEYS)
        if isinstance(value, dict):
            value = _first(value, ("code", "name", "symbol"))
        if value and normalize(str(value)) not in allowed:
            return True
    return False


def _first(obj: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, "", [], {}):
            return obj[key]
    return None


def _name_of(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(str(_first(value, ("name", "title", "label")) or ""))
    if isinstance(value, list):
        return _name_of(value[0]) if value else ""
    return clean_text(str(value or ""))


def _image_of(value: Any) -> str:
    if isinstance(value, list):
        return _image_of(value[0]) if value else ""
    if isinstance(value, dict):
        return str(_first(value, ("url", "src", "contentUrl")) or "")
    return str(value or "")


def _make(
    *,
    source: str,
    country: str = DEFAULT_COUNTRY,
    name: str,
    shop: str,
    price: float,
    page_url: str,
    today: date,
    old_price: float | None = None,
    discount: float | None = None,
    amount: str = "",
    validity: str = "",
    valid_from: date | None = None,
    valid_to: date | None = None,
    loyalty: bool = False,
    url: str = "",
    image: str = "",
    packaging_hint: str = "",
) -> dict[str, Any]:
    if validity and not (valid_from or valid_to):
        valid_from, valid_to = parse_validity(validity, today)
    if image.startswith("data:"):
        image = ""
    return build_offer(
        product_id=normalize(name),
        discount_id="",
        name=name,
        shop=shop,
        price=price,
        amount=amount,
        unit_text="",
        discount=discount,
        validity=validity,
        valid_from=valid_from,
        valid_to=valid_to,
        loyalty=loyalty,
        url=urljoin(page_url, url) if url else page_url,
        image=urljoin(page_url, image) if image else "",
        source=source,
        old_price=old_price,
        currency=COUNTRIES[country]["currency"],
        packaging_hint=packaging_hint,
    )


# --------------------------------------------------------------------- JSON-LD
def _jsonld_products(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _jsonld_products(item)
        return
    if not isinstance(data, dict):
        return
    kind = data.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    if "Product" in kinds:
        yield data
    if "ItemList" in kinds or "OfferCatalog" in kinds:
        for element in data.get("itemListElement") or []:
            yield from _jsonld_products(
                element.get("item", element) if isinstance(element, dict) else element
            )
    if "@graph" in data:
        yield from _jsonld_products(data["@graph"])


def parse_jsonld(
    html_or_soup: Any, page_url: str, today: date, source: str, country: str = DEFAULT_COUNTRY
) -> list[dict[str, Any]]:
    soup = html_or_soup if isinstance(html_or_soup, BeautifulSoup) else make_soup(html_or_soup)
    fallback_shop = _chain_from_url(page_url)
    offers: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        for product in _jsonld_products(data):
            name = clean_text(product.get("name"))
            if not name:
                continue
            raw = product.get("offers") or []
            if isinstance(raw, dict):
                raw = raw.get("offers") or [raw]
            for offer in raw if isinstance(raw, list) else []:
                if not isinstance(offer, dict):
                    continue
                if _foreign_currency(offer, product.get("offers"), country=country):
                    continue
                shop = _name_of(offer.get("offeredBy") or offer.get("seller")) or fallback_shop
                price = _price(offer.get("price") or offer.get("lowPrice"))
                if not shop or price is None:
                    continue
                valid_to = _date(offer.get("priceValidUntil") or offer.get("validThrough"))
                valid_from = _date(offer.get("validFrom")) or today
                offers.append(
                    _make(
                        source=source,
                        country=country,
                        name=name,
                        shop=shop,
                        price=price,
                        page_url=page_url,
                        today=today,
                        validity=f"do {valid_to.day}. {valid_to.month}." if valid_to else "",
                        valid_from=valid_from,
                        valid_to=valid_to,
                        url=str(offer.get("url") or product.get("url") or ""),
                        image=_image_of(product.get("image")),
                    )
                )
    return offers


# --------------------------------------------------------------- vložený JSON
def _walk(data: Any, depth: int = 0):
    if depth > 25:
        return
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _walk(value, depth + 1)
    elif isinstance(data, list):
        for value in data:
            yield from _walk(value, depth + 1)


def parse_embedded_json(
    soup: BeautifulSoup, page_url: str, today: date, source: str, country: str = DEFAULT_COUNTRY
) -> list[dict[str, Any]]:
    fallback_shop = _chain_from_url(page_url)
    offers: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        kind = (script.get("type") or "").lower()
        text = script.string or ""
        if kind == "application/ld+json" or not text.strip():
            continue
        data = None
        if kind == "application/json" or script.get("id") == "__NEXT_DATA__":
            try:
                data = json.loads(text)
            except ValueError:
                data = None
        if data is None:
            continue
        for obj in _walk(data):
            name = _first(obj, NAME_KEYS)
            price = _price(_first(obj, PRICE_KEYS))
            if not isinstance(name, str) or price is None:
                continue
            if _foreign_currency(
                obj,
                obj.get("price") if isinstance(obj.get("price"), dict) else None,
                country=country,
            ):
                continue
            shop = _name_of(_first(obj, SHOP_KEYS)) or fallback_shop
            if not shop:
                continue
            offers.append(
                _make(
                    source=source,
                    country=country,
                    name=clean_text(name),
                    shop=shop,
                    price=price,
                    page_url=page_url,
                    today=today,
                    old_price=_price(_first(obj, OLD_PRICE_KEYS)),
                    discount=_price(obj.get("discount") or obj.get("discountPercent")),
                    amount=clean_text(str(_first(obj, AMOUNT_KEYS) or "")),
                    valid_from=_date(_first(obj, FROM_KEYS)),
                    valid_to=_date(_first(obj, TO_KEYS)),
                    url=str(_first(obj, URL_KEYS) or ""),
                    image=_image_of(_first(obj, IMAGE_KEYS)),
                )
            )
    return offers


# ------------------------------------------------------------- HTML heuristika
def _card_text(node: Tag) -> str:
    return clean_text(node.get_text(" ", strip=True))


def _card_shop(node: Tag, text: str) -> str | None:
    hints = [text]
    for img in node.find_all("img"):
        hints.append(f"{img.get('alt', '')} {img.get('title', '')} {img.get('src', '')}")
    for tag in node.find_all(True):
        classes = tag.get("class") or []
        hints.append(
            " ".join(classes) + " " + str(tag.get("data-shop") or tag.get("data-store") or "")
        )
    for link in node.find_all("a", href=True):
        hints.append(link["href"])
    return detect_chain(*hints)


def _card_name(node: Tag, text: str, pattern: re.Pattern = PRICE_RE) -> str:
    for selector in (
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "[itemprop=name]",
        "[class*=name]",
        "[class*=title]",
        "strong",
    ):
        found = node.select_one(selector)
        if found:
            name = clean_text(found.get("title") or found.get_text(" ", strip=True))
            if name and not pattern.fullmatch(name) and len(name) > 2:
                return name
    for tag in node.find_all(["a", "img"]):
        name = clean_text(tag.get("title") or tag.get("alt") or "")
        if len(name) > 2 and (detect_chain(name) is None or len(name) > 15):
            return name
    head = pattern.split(text)[0]
    return clean_text(head)[:120]


def _card_prices(
    node: Tag, text: str, pattern: re.Pattern = PRICE_RE, country: str = DEFAULT_COUNTRY
) -> tuple[float | None, float | None]:
    old = None
    for tag in node.find_all(["del", "s", "strike"]) + node.select(
        "[class*=old], [class*=original], [class*=before]"
    ):
        match = pattern.search(normalize_prices(tag.get_text(" ", strip=True), country))
        if match:
            old = to_float(match.group(1))
            break
    prices = [to_float(m.group(1)) for m in pattern.finditer(text)]
    # ceny za jednotku ("… Kč / 1 l", "1,18 €/l") nechceme brát jako cenu produktu
    unit_spans = [
        m.span()
        for m in re.finditer(r"\d[\d,.\s]*\s*(?:Kč|€|EUR)\s*/\s*\d*[,.]?\d*\s*(?:l|kg|ks)\b", text)
    ]
    prices = [
        to_float(m.group(1))
        for m in pattern.finditer(text)
        if not any(a <= m.start() < b for a, b in unit_spans)
    ] or prices
    candidates = [p for p in prices if p and p != old]
    price = min(candidates) if candidates else None
    if old is None and len(set(prices)) > 1 and price is not None:
        higher = [p for p in prices if p > price]
        old = min(higher) if higher and min(higher) < price * 3 else None
    return price, old


CURRENCY_HINT_RE = re.compile(r"Kč|kč|KČ|CZK|,-|€|EUR")


def _text_lengths(soup: BeautifulSoup) -> dict[int, int]:
    """Přibližná délka viditelného textu každého prvku, spočítaná jedním průchodem."""
    lengths: dict[int, int] = {}
    for tag in reversed(soup.find_all(True)):
        if tag.name in ("script", "style", "noscript"):
            lengths[id(tag)] = 0
            continue
        total = 0
        for child in tag.children:
            if isinstance(child, Tag):
                total += lengths.get(id(child), 0)
            elif not isinstance(child, Comment):
                total += len(child.strip()) + 1
        lengths[id(tag)] = total
    return lengths


def parse_html_cards(
    soup: BeautifulSoup, page_url: str, today: date, source: str, country: str = DEFAULT_COUNTRY
) -> list[dict[str, Any]]:
    fallback_shop = _chain_from_url(page_url)
    pattern = price_re(country)

    def card_text(node: Tag) -> str:
        return normalize_prices(_card_text(node), country)

    # Délky textu všech prvků jedním průchodem (děti před rodiči) – dřív se text
    # celé stránky počítal znovu pro každý prvek, což bylo kvadratické a blokovalo HA.
    lengths = _text_lengths(soup)
    too_long = MAX_CARD_TEXT + 1

    def short(node: Tag | None) -> bool:
        return node is not None and lengths.get(id(node), too_long) <= MAX_CARD_TEXT

    cards: dict[int, Tag] = {}
    for string in soup.find_all(string=CURRENCY_HINT_RE):
        node = string.parent
        if node is None or node.name in ("script", "style", "noscript"):
            continue
        # nejmenší blok nad cenou, který obsahuje i název obchodu (karta, ne celý seznam)
        while node is not None and short(node):
            if node.name in CARD_TAGS:
                text = card_text(node)
                if pattern.search(text) and (_card_shop(node, text) or fallback_shop):
                    cards.setdefault(id(node), node)
                    break
            node = node.parent

    offers: list[dict[str, Any]] = []
    for card in cards.values():
        # bloky s cenou bývají menší než celá karta – vezmeme rodiče, který má i název
        node = card
        text = card_text(node)
        while short(node.parent) and not node.find(["h1", "h2", "h3", "h4", "img"]):
            node = node.parent
            text = card_text(node)
        shop = _card_shop(node, text) or fallback_shop
        price, old = _card_prices(node, text, pattern, country)
        name = _card_name(node, text, pattern)
        if not shop or price is None or not name:
            continue
        validity_match = DATE_RANGE_RE.search(text)
        discount_match = DISCOUNT_RE.search(text)
        amount_match = AMOUNT_RE.search(name) or AMOUNT_RE.search(text)
        link = node if node.name == "a" and node.get("href") else node.find("a", href=True)
        img = node.find("img")
        norm = normalize(text)
        offers.append(
            _make(
                source=source,
                country=country,
                name=name,
                shop=shop,
                price=price,
                page_url=page_url,
                today=today,
                old_price=old,
                discount=float(discount_match.group(1)) if discount_match else None,
                amount=amount_match.group(0) if amount_match else "",
                validity=validity_match.group(0) if validity_match else "",
                loyalty=any(word in norm for word in LOYALTY_WORDS),
                packaging_hint=text,
                url=link["href"] if link else "",
                image=str(img.get("data-src") or img.get("src") or "") if img else "",
            )
        )
    return offers


def dedupe(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sloučí stejné nabídky (řetězec + produkt + cena), i napříč zdroji."""
    result: dict[tuple, dict[str, Any]] = {}
    for offer in offers:
        key = (offer["chain"], normalize(offer["product"]), round(offer["price"], 1))
        if key in result:
            kept = result[key]
            for src in offer.get("sources", [offer.get("source")]):
                if src not in kept["sources"]:
                    kept["sources"] = [*kept["sources"], src]
            for field in (
                "valid_to",
                "valid_from",
                "image",
                "old_price",
                "discount_percent",
                "price_per_liter",
            ):
                if not kept.get(field) and offer.get(field):
                    kept[field] = offer[field]
            if kept.get("price_per_liter") and not kept.get("price_per_half_liter"):
                kept["price_per_half_liter"] = round(kept["price_per_liter"] / 2, 2)
        else:
            result[key] = dict(offer)
    return list(result.values())


def parse_generic(
    html: str | BeautifulSoup,
    page_url: str,
    today: date,
    source: str,
    country: str = DEFAULT_COUNTRY,
    heuristics: bool = True,
) -> list[dict[str, Any]]:
    soup = make_soup(html)
    offers = parse_jsonld(soup, page_url, today, source, country)
    offers += parse_embedded_json(soup, page_url, today, source, country)
    if not offers and heuristics:
        offers = parse_html_cards(soup, page_url, today, source, country)
    return dedupe(offers)
