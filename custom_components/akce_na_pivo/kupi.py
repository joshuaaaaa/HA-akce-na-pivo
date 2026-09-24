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


# Obal podle textu (bez diakritiky). Pořadí je důležité: "PET lahev" je PET, ne sklo.
_PACKAGING_PATTERNS = (
    ("can", re.compile(r"\bplech|\bcan\b|\bcans\b|\bdoza\b|\bdose\b")),
    ("pet", re.compile(r"\bpet\b|\bplast")),
    ("glass", re.compile(r"\bsklo|\bsklen[eay]n|\blahe?v|\blahv|\bflas|\bbottle|\bvratn")),
)


def detect_packaging(*texts: str | None, volume: float | None = None) -> str | None:
    """Vrátí "can" / "glass" / "pet", nebo None, když obal z textu nejde poznat."""
    for text in texts:
        norm = normalize(text)
        if not norm:
            continue
        for kind, pattern in _PACKAGING_PATTERNS:
            if pattern.search(norm):
                return kind
    # pivo v balení od 1 l se v obchodech prodává v PET lahvích
    if volume and volume >= 1.0:
        return "pet"
    return None


# Stupňovitost piva (10°, 11°, 12°…)
_DEGREE_EXPLICIT = re.compile(r"(?<![\d,.\-])(\d{1,2})\s*(?:°|%|stup)")
_DEGREE_BARE = re.compile(
    r"(?<![\d,.x×])\b(1[0-6]|[7-9])\b"
    r"(?!\s*(?:x\b|×|ks|kus|l\b|ml\b|,\d|\.\d|pack|-pack|plech|lahv|%|°))"
)
_DEGREE_WORDS = {
    "desitka": 10,
    "desinka": 10,
    "jedenactka": 11,
    "dvanactka": 12,
    "vycepni": 10,
    "vycapne": 10,
}
# známá piva, u kterých stupeň v názvu často chybí
_DEGREE_KNOWN = (
    ("pilsner urquell", 12),
    ("gambrinus original", 10),
    ("gambrinus plna", 12),
    ("radegast razna", 10),
    ("radegast ryze horka", 12),
    ("kozel svetly", 10),
    ("kozel premium", 11),
    ("budweiser budvar b:original", 12),
    ("budvar b:original", 12),
    ("zlaty bazant 73", 10),
)


def detect_degree(*texts: str | None) -> int | None:
    """Stupňovitost z názvu: "Kozel 11", "12°", "12%" (SK), "desítka"… jinak None."""
    norms = [normalize(t) for t in texts if t]
    for norm in norms:
        for match in _DEGREE_EXPLICIT.finditer(norm):
            value = int(match.group(1))
            # "%" bez desetinné čárky ve slovenských názvech = stupňovitost (7–16)
            if 6 <= value <= 20 and not (match.group(0).endswith("%") and value < 7):
                return value
        for word, value in _DEGREE_WORDS.items():
            if word in norm:
                return value
        match = _DEGREE_BARE.search(norm)
        if match:
            return int(match.group(1))
    joined = " ".join(norms)
    for name, value in _DEGREE_KNOWN:
        if name in joined:
            return value
    return None


def degree_group(degree: int | None) -> str | None:
    """10 / 11 / 12 -> "10" / "11" / "12", jiná stupňovitost -> "other"."""
    if degree is None:
        return None
    return str(degree) if degree in (10, 11, 12) else "other"


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


def _wrap_info(wrap: Any) -> dict[str, str]:
    title = wrap.select_one(".product_name h2 a[title], .product_name a[title], h2 a[title]")
    name = clean_text(title["title"]) if title else _text(wrap, ".product_name h2, .product_name")
    amount = _text(wrap, ".product_name .nowrap, .product_name .amount")
    if name and amount and normalize(amount) not in normalize(name):
        name = f"{name} {amount}".strip()
    link = wrap.select_one(".product_name a[href], .product_image a[href], a[href*='/sleva/']")
    img = wrap.select_one(".product_image img, img")
    image = ""
    if img is not None:
        image = str(img.get("data-src") or img.get("src") or "")
        if image.startswith("data:"):
            image = ""
    return {
        "name": name,
        "url": urljoin(KUPI_BASE_URL, link["href"]) if link else "",
        "image": urljoin(KUPI_BASE_URL, image) if image else "",
    }


def _product_lookup(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    """Názvy produktů podle data-product-id.

    Atribut data-product-id mají i drobné prvky uvnitř bloku produktu (tlačítka
    „hlídat“, oblíbené…). Ty nesmí přepsat název nalezený v hlavním bloku.
    """
    products: dict[str, dict[str, str]] = {}
    wraps = soup.select(".product--wrap[data-product-id]") + soup.select("[data-product-id]")
    for wrap in wraps:
        product_id = str(wrap.get("data-product-id"))
        if products.get(product_id, {}).get("name"):
            continue
        info = _wrap_info(wrap)
        if info["name"] or product_id not in products:
            products[product_id] = info
    return products


def name_from_url(href: str | None) -> str:
    """'/sleva/pivo-velkopopovicky-kozel-11' -> 'pivo velkopopovicky kozel 11'."""
    if not href or "/sleva/" not in href:
        return ""
    slug = href.split("/sleva/", 1)[1].split("?")[0].split("#")[0].strip("/").split("/")[0]
    return clean_text(slug.replace("-", " "))


def _ancestor_name(row: Any) -> str:
    """Název z nejbližšího bloku produktu nad řádkem slevy.

    Hledá jen v blocích, které jsou opravdu produkt (data-product-id nebo třída
    s „product“), ne v celé sekci – jinak by se vzal nadpis typu „Akce dle ceny“.
    """
    node = row
    for _ in range(4):
        node = node.parent
        if node is None or node.name in ("body", "html", "main"):
            return ""
        classes = " ".join(node.get("class") or [])
        if not node.has_attr("data-product-id") and "product" not in classes:
            continue
        info = _wrap_info(node)
        if info["name"]:
            return info["name"]
        link = node.select_one("a[href*='/sleva/']")
        if link and (name := name_from_url(link["href"])):
            return name
    return ""


def parse_offers(html: str, source_url: str, today: date) -> list[dict[str, Any]]:
    """Najde všechny akční nabídky (řádky slev) na stránce kupi.cz."""
    soup = BeautifulSoup(html, "html.parser")
    products = _product_lookup(soup)
    page_title = _text(soup, "h1")
    # nadpis stránky je název produktu jen na detailu (/sleva/...), ne na výpisu kategorie
    is_detail = "/sleva/" in source_url
    # nadpisy sekcí stránky ("Akce dle ceny", "Pivo v akci"…) nejsou názvy produktů
    headings = {
        normalize(h.get_text(" ", strip=True))
        for h in soup.select("h1, h2, h3, h4")
        if not h.find_parent(attrs={"data-product-id": True})
        and not h.find_parent(class_=re.compile("product"))
    }
    if is_detail:
        headings.discard(normalize(page_title))
    offers: list[dict[str, Any]] = []

    for row in soup.select(".discount_row"):
        product_id = str(row.get("data-product") or "")
        if not product_id:
            parent = row.find_parent(attrs={"data-product-id": True})
            product_id = str(parent.get("data-product-id")) if parent else ""
        product = products.get(product_id, {})
        row_link = row.select_one("a.product_link_history[href], a[href*='/sleva/']")
        candidates = (
            product.get("name"),
            _ancestor_name(row),
            name_from_url(row_link["href"] if row_link else ""),
            name_from_url(product.get("url")),
        )
        name = next((c for c in candidates if c and normalize(c) not in headings), "")
        if not name and is_detail:
            name = page_title
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
                packaging_hint=row_text,
                url=urljoin(KUPI_BASE_URL, link["href"])
                if link
                else (product.get("url") or source_url),
                image=product.get("image", ""),
            )
        )
    if not is_detail:
        # stejný "název" u mnoha různých produktů = nadpis stránky/sekce, ne jméno piva
        ids_by_name: dict[str, set[str]] = {}
        for offer in offers:
            ids_by_name.setdefault(normalize(offer["product"]), set()).add(offer["product_id"])
        generic = {name for name, ids in ids_by_name.items() if len(ids) > 3}
        offers = [o for o in offers if normalize(o["product"]) not in generic]
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
    packaging_hint: str = "",
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
        "packaging": detect_packaging(name, amount, packaging_hint, volume=volume),
        "degree": detect_degree(name),
        "url": url,
        "image": image,
    }


def kupi_html_sample(html: str, limit: int = 1500) -> str:
    """Zkrácené HTML první akce se dvěma nadřazenými bloky – pro diagnostiku."""
    soup = BeautifulSoup(html, "html.parser")
    row = soup.select_one(".discount_row")
    if row is None:
        return "stránka neobsahuje .discount_row"
    node = row
    for _ in range(2):
        if node.parent is not None and node.parent.name not in ("body", "html"):
            node = node.parent
    for tag in node.find_all(["script", "style", "svg"]):
        tag.decompose()
    return " ".join(str(node).split())[:limit]
