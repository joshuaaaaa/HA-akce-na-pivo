"""Parser akčních nabídek z kupi.cz.

Modul nezávisí na Home Assistantu, aby šel snadno testovat.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .const import CHAIN_ALIASES, KNOWN_BRANDS, KUPI_BASE_URL, NONALCOHOLIC_WORDS, ONLINE_SHOPS

CZECH_MONTHS = {
    "ledna": 1,
    "leden": 1,
    "unora": 2,
    "unor": 2,
    "brezna": 3,
    "brezen": 3,
    "dubna": 4,
    "duben": 4,
    "kvetna": 5,
    "kveten": 5,
    "cervna": 6,
    "cerven": 6,
    "cervence": 7,
    "cervenec": 7,
    "srpna": 8,
    "srpen": 8,
    "zari": 9,
    "rijna": 10,
    "rijen": 10,
    "listopadu": 11,
    "listopad": 11,
    "prosince": 12,
    "prosinec": 12,
}

_NUM = r"\d+(?:[,.]\d+)?"


def clean_text(text: str | None) -> str:
    """Sjednotí mezery (včetně nezlomitelných)."""
    if not text:
        return ""
    return " ".join(str(text).replace("\xa0", " ").split())


def normalize(text: str | None) -> str:
    """Malá písmena bez diakritiky."""
    text = unicodedata.normalize("NFKD", clean_text(text).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def to_float(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


def parse_price(text: str | None) -> float | None:
    match = re.search(rf"({_NUM})\s*(?:Kč|,-)", clean_text(text))
    if not match:
        match = re.search(rf"({_NUM})", clean_text(text))
    return to_float(match.group(1)) if match else None


def parse_percentage(text: str | None) -> float | None:
    match = re.search(rf"({_NUM})\s*%", clean_text(text))
    return to_float(match.group(1)) if match else None


def parse_volume(*texts: str | None) -> tuple[int, float | None]:
    """Vrátí (počet kusů, objem jednoho kusu v litrech)."""
    for raw in texts:
        text = normalize(raw).replace("×", "x")
        if not text:
            continue
        multi = re.search(rf"(\d+)\s*x\s*({_NUM})\s*(ml|l)\b", text)
        if multi:
            pieces = int(multi.group(1))
            volume = to_float(multi.group(2))
            if multi.group(3) == "ml":
                volume /= 1000
            return pieces, volume
        single = re.search(rf"({_NUM})\s*(ml|l)\b", text)
        if single:
            volume = to_float(single.group(1))
            if single.group(2) == "ml":
                volume /= 1000
            pieces = 1
            pack = re.search(r"(\d+)\s*(?:ks|kusu|pack|-pack|plechovek|lahvi)\b", text)
            if pack:
                pieces = int(pack.group(1))
            return pieces, volume
    return 1, None


def parse_unit_price(text: str | None) -> float | None:
    """'39,80 Kč / 1 l' -> cena za litr."""
    text = normalize(text)
    match = re.search(rf"({_NUM})\s*kc\s*/\s*({_NUM})?\s*(ml|l)\b", text)
    if not match:
        return None
    price = to_float(match.group(1))
    qty = to_float(match.group(2)) if match.group(2) else 1.0
    if match.group(3) == "ml":
        qty /= 1000
    return round(price / qty, 2) if qty else None


def _partial_date(text: str, today: date) -> date | None:
    match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(\d{4}))?", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else None
    else:
        match = re.search(r"(\d{1,2})\.\s*([a-z]+)", text)
        if not match or match.group(2) not in CZECH_MONTHS:
            return None
        day, month, year = int(match.group(1)), CZECH_MONTHS[match.group(2)], None
    try:
        parsed = date(year or today.year, month, day)
    except ValueError:
        return None
    if year is None and parsed < today - timedelta(days=180):
        parsed = date(today.year + 1, month, day)
    elif year is None and parsed > today + timedelta(days=180):
        parsed = date(today.year - 1, month, day)
    return parsed


def parse_validity(text: str | None, today: date) -> tuple[date | None, date | None]:
    """Převede text platnosti z kupi.cz na (od, do)."""
    norm = normalize(text)
    if not norm:
        return None, None
    if "dnes konci" in norm:
        return today, today
    if "zitra konci" in norm or "zajtra konci" in norm:
        return today, today + timedelta(days=1)
    if "plati do" in norm or norm.startswith("do "):
        return today, _partial_date(norm, today)
    both = re.search(r"\bod\s+(.+?)\s+do\s+(.+)", norm)
    if both:
        return _partial_date(both.group(1), today), _partial_date(both.group(2), today)
    if norm.startswith("od ") or "plati od" in norm:
        return _partial_date(norm, today), None
    parts = re.split(r"\s+[–-]\s+|\s*[–-]\s*(?=[a-z]{2}\s*\d|\d)", norm, maxsplit=1)
    if len(parts) == 2:
        return _partial_date(parts[0], today), _partial_date(parts[1], today)
    single = _partial_date(norm, today)
    return today, single


def chain_key(shop: str | None) -> str:
    """'Albert Hypermarket' -> 'albert'."""
    norm = normalize(shop)
    for key in sorted(CHAIN_ALIASES, key=len, reverse=True):
        if key in norm:
            return key
    return norm.split(" ")[0] if norm else ""


def is_online_shop(shop: str | None) -> bool:
    norm = normalize(shop)
    return any(word in norm for word in ONLINE_SHOPS)


def is_nonalcoholic(name: str | None) -> bool:
    norm = normalize(name)
    if any(word in norm for word in NONALCOHOLIC_WORDS):
        return True
    return bool(re.search(r"(?<![\d,.])0[,.]0\s*%", norm))


def brand_aliases(brand: str) -> tuple[str, ...]:
    if brand in KNOWN_BRANDS:
        return KNOWN_BRANDS[brand][0]
    return (normalize(brand),)


def match_brand(product: str, brands: list[str]) -> str | None:
    """Vrátí první značku, která odpovídá názvu produktu."""
    norm = normalize(product)
    for brand in brands:
        for alias in brand_aliases(brand):
            if alias and alias in norm:
                return brand
    return None


def _text(node: Any, selector: str) -> str:
    found = node.select_one(selector) if node is not None else None
    return clean_text(found.get_text(" ", strip=True)) if found else ""


def _product_lookup(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    products: dict[str, dict[str, str]] = {}
    for wrap in soup.select("[data-product-id]"):
        product_id = str(wrap.get("data-product-id"))
        title = wrap.select_one(".product_name h2 a[title], .product_name a[title], h2 a[title]")
        name = (
            clean_text(title["title"])
            if title
            else _text(wrap, ".product_name h2, .product_name, h2")
        )
        amount = _text(wrap, ".product_name .nowrap, .product_name .amount")
        if amount and normalize(amount) not in normalize(name):
            name = f"{name} {amount}".strip()
        link = wrap.select_one(".product_name a[href], .product_image a[href], a[href]")
        img = wrap.select_one(".product_image img, img")
        image = ""
        if img is not None:
            image = str(img.get("data-src") or img.get("src") or "")
            if image.startswith("data:"):
                image = ""
        products[product_id] = {
            "name": name,
            "url": urljoin(KUPI_BASE_URL, link["href"]) if link else "",
            "image": urljoin(KUPI_BASE_URL, image) if image else "",
        }
    return products


def _ancestor_name(row: Any) -> str:
    """Název produktu z nejbližšího nadřazeného bloku (když chybí data-product-id)."""
    node = row
    for _ in range(6):
        node = node.parent
        if node is None:
            return ""
        found = node.select_one(".product_name h2 a[title], .product_name a[title], h2 a[title]")
        if found:
            return clean_text(found["title"])
        found = node.select_one(".product_name, h2, h3")
        if found:
            text = clean_text(found.get_text(" ", strip=True))
            if text:
                return text
    return ""


def parse_offers(html: str, source_url: str, today: date) -> list[dict[str, Any]]:
    """Najde všechny akční nabídky (řádky slev) na stránce kupi.cz."""
    soup = BeautifulSoup(html, "html.parser")
    products = _product_lookup(soup)
    page_title = _text(soup, "h1")
    # nadpis stránky je název produktu jen na detailu (/sleva/...), ne na výpisu kategorie
    is_detail = "/sleva/" in source_url
    offers: list[dict[str, Any]] = []

    for row in soup.select(".discount_row"):
        product_id = str(row.get("data-product") or "")
        if not product_id:
            parent = row.find_parent(attrs={"data-product-id": True})
            product_id = str(parent.get("data-product-id")) if parent else ""
        product = products.get(product_id, {})
        name = product.get("name") or _ancestor_name(row) or (page_title if is_detail else "")
        shop = _text(row, ".discounts_shop_name a, .discounts_shop_name")
        price = parse_price(_text(row, ".discount_price_value, .discount_price"))
        if not name or not shop or price is None:
            continue

        amount = _text(row, ".discount_amount").lstrip("/ ").strip()
        unit_text = _text(row, ".price_per_unit")
        discount = parse_percentage(_text(row, ".discount_percentage"))
        validity = _text(row, ".discounts_validity")
        valid_from, valid_to = parse_validity(validity, today)
        row_text = normalize(row.get_text(" ", strip=True))
        loyalty = any(
            word in row_text
            for word in (
                "cleny klubu",
                "s kartou",
                "s aplikaci",
                "lidl plus",
                "clubcard",
                "moje billa",
                "muj albert",
                "penny karta",
            )
        )
        link = next(
            (
                found
                for selector in ("a.btn_link_leaflet[href]", "a.product_link_history[href]")
                if (found := row.select_one(selector)) is not None
            ),
            None,
        )

        offers.append(
            build_offer(
                product_id=product_id or normalize(name),
                discount_id=str(row.get("data-discount") or ""),
                name=name,
                shop=shop,
                price=price,
                amount=amount,
                unit_text=unit_text,
                discount=discount,
                validity=validity,
                valid_from=valid_from,
                valid_to=valid_to,
                loyalty=loyalty,
                url=urljoin(KUPI_BASE_URL, link["href"])
                if link
                else (product.get("url") or source_url),
                image=product.get("image", ""),
            )
        )
    return offers


def build_offer(
    *,
    product_id: str,
    discount_id: str,
    name: str,
    shop: str,
    price: float,
    amount: str,
    unit_text: str,
    discount: float | None,
    validity: str,
    valid_from: date | None,
    valid_to: date | None,
    loyalty: bool,
    url: str,
    image: str,
    source: str = "kupi",
    old_price: float | None = None,
    currency: str = "CZK",
) -> dict[str, Any]:
    pieces, volume = parse_volume(amount, name)
    per_liter = parse_unit_price(unit_text)
    total_l = round(pieces * volume, 3) if volume else None
    if per_liter is None and total_l:
        per_liter = round(price / total_l, 2)
    if old_price is not None and old_price <= price:
        old_price = None
    if old_price is None and discount and 0 < discount < 100:
        old_price = round(price / (1 - discount / 100), 2)
    if discount is None and old_price:
        discount = round((1 - price / old_price) * 100)
    return {
        "id": f"{source}|{normalize(shop)}|{product_id}|{discount_id or price}",
        "source": source,
        "sources": [source],
        "currency": currency,
        "product_id": product_id,
        "product": name,
        "shop": shop,
        "chain": chain_key(shop),
        "online": is_online_shop(shop),
        "price": round(price, 2),
        "old_price": old_price,
        "discount_percent": discount,
        "amount": amount
        or (
            f"{pieces} × {volume:g} l"
            if volume and pieces > 1
            else (f"{volume:g} l" if volume else "")
        ),
        "pieces": pieces,
        "volume_l": volume,
        "total_l": total_l,
        "price_per_piece": round(price / pieces, 2) if pieces else None,
        "price_per_liter": per_liter,
        "price_per_half_liter": round(per_liter / 2, 2) if per_liter else None,
        "validity": validity,
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_to": valid_to.isoformat() if valid_to else None,
        "loyalty": loyalty,
        "nonalcoholic": is_nonalcoholic(name),
        "url": url,
        "image": image,
    }
