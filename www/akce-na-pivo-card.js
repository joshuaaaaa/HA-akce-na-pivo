/*
 * Akce na pivo – Lovelace karta (custom:akce-na-pivo-card)
 * Seznam nejlevnějších akcí na pivo s mapou obchodů pro integraci "akce_na_pivo".
 *
 * Instalace:
 *   1. zkopírujte soubor do /config/www/akce-na-pivo-card.js
 *   2. Nastavení → Ovládací panely → ⋮ → Zdroje → Přidat zdroj
 *        URL: /local/akce-na-pivo-card.js      Typ: JavaScript modul
 *   3. do dashboardu přidejte kartu "Akce na pivo" (type: custom:akce-na-pivo-card)
 *
 * Mapa se kreslí přímo z dlaždic OpenStreetMap – bez externích knihoven.
 */

const CARD_VERSION = "2.4.0";
const FLAGS = { CZ: "🇨🇿", SK: "🇸🇰" };
// Texty karty – čeština, slovenčina, angličtina
const I18N = {
  cs: {
    title: "🍺 Nejlevnější pivo", sorted: "řazeno", updated: "aktualizace", not_on_sale: "Není v akci",
    none: "Žádné vybrané pivo teď není v akci 😢", upcoming: "Připravované akce", navigate: "Navigovat",
    leaflet: "Leták / kupi.cz", home: "Vaše poloha", zoom_in: "Přiblížit", zoom_out: "Oddálit",
    fit: "Ukázat všechny obchody", refresh: "Aktualizovat", glass: "sklo", can: "plech", pet: "PET",
    need_entity: "Zadejte entitu (senzor Nejlevnější pivo)", not_found: "Entita nenalezena",
  },
  sk: {
    title: "🍺 Najlacnejšie pivo", sorted: "zoradené", updated: "aktualizácia", not_on_sale: "Nie je v akcii",
    none: "Žiadne vybrané pivo teraz nie je v akcii 😢", upcoming: "Pripravované akcie", navigate: "Navigovať",
    leaflet: "Leták", home: "Vaša poloha", zoom_in: "Priblížiť", zoom_out: "Oddialiť",
    fit: "Ukázať všetky obchody", refresh: "Aktualizovať", glass: "sklo", can: "plech", pet: "PET",
    need_entity: "Zadajte entitu (senzor Najlacnejšie pivo)", not_found: "Entita sa nenašla",
  },
  en: {
    title: "🍺 Cheapest beer", sorted: "sorted by", updated: "updated", not_on_sale: "Not on sale",
    none: "None of the selected beers is on sale now 😢", upcoming: "Upcoming deals", navigate: "Navigate",
    leaflet: "Flyer", home: "Your location", zoom_in: "Zoom in", zoom_out: "Zoom out",
    fit: "Show all stores", refresh: "Refresh", glass: "glass", can: "can", pet: "PET",
    need_entity: "Set the entity (Cheapest beer sensor)", not_found: "Entity not found",
  },
};
const LOCALES = { cs: "cs-CZ", sk: "sk-SK", en: "en-GB" };
const pickLang = (...candidates) => {
  for (const c of candidates) {
    const base = String(c || "").toLowerCase().split("-")[0];
    if (I18N[base]) return base;
  }
  return "cs";
};
let EDITOR_LANG = "cs";
const PACKAGING_ICONS = { glass: "🍾", can: "🥫", pet: "🧴" };
// štítky, které zvýrazníme (podle klíče z integrace; starší verze posílaly jen text)
const HOT_FLAGS = ["history_min", "below_limit"];
// Mapové podklady. Dlaždice přímo z tile.openstreetmap.org OSM blokuje ("Access blocked"),
// protože Home Assistant neposílá hlavičku Referer – proto výchozí CARTO (data z OpenStreetMap).
const RETINA = (window.devicePixelRatio || 1) > 1.5;
const TILE_PROVIDERS = {
  carto: {
    url: (z, x, y) => `https://${"abcd"[(x + y) % 4]}.basemaps.cartocdn.com/rastertiles/voyager/${z}/${x}/${y}${RETINA ? "@2x" : ""}.png`,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
  },
  carto_dark: {
    url: (z, x, y) => `https://${"abcd"[(x + y) % 4]}.basemaps.cartocdn.com/dark_all/${z}/${x}/${y}${RETINA ? "@2x" : ""}.png`,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
  },
  osm: {
    url: (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`,
    attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  },
};
const TILE = 256;

console.info(
  `%c AKCE-NA-PIVO-CARD %c v${CARD_VERSION} `,
  "color:#fff;background:#d98e04;font-weight:700",
  "color:#d98e04;background:#fff3d6"
);

// Web Mercator – převod GPS na pixely světové mapy v daném zoomu
const project = (lat, lon, z) => {
  const scale = TILE * 2 ** z;
  const sin = Math.sin((Math.max(-85, Math.min(85, lat)) * Math.PI) / 180);
  return {
    x: ((lon + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale,
  };
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const money = (value, symbol = "Kč", locale = "cs-CZ") =>
  value === null || value === undefined || value === ""
    ? "–"
    : `${Number(value).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${symbol}`;

const shortDate = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getDate()}. ${d.getMonth() + 1}.`;
};

const SORTERS = {
  unit: (a, b) => (a.price_per_half_liter ?? a.price) - (b.price_per_half_liter ?? b.price),
  price: (a, b) => a.price - b.price,
  distance: (a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999) || SORTERS.unit(a, b),
};

class AkceNaPivoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._selected = 0;
    this._view = null; // {z, cx, cy}; null = automaticky ukázat všechny obchody
    this._resize = null;
    this._lastKey = "";
  }

  static getConfigElement() {
    return document.createElement("akce-na-pivo-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.offers) && "sort_by" in hass.states[id].attributes
    );
    return { entity: entity || "", count: 5, show_map: true };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error(I18N[pickLang(config?.language, navigator.language)].need_entity);
    this._config = {
      count: 5,
      show_map: true,
      show_images: true,
      show_flags: true,
      show_upcoming: false,
      show_address: true,
      show_source: true,
      map_height: 240,
      sort: "",
      ...config,
    };
    this._lastKey = "";
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this._config?.entity];
    const key = state ? `${state.last_updated}|${state.state}` : "missing";
    if (key !== this._lastKey) {
      this._lastKey = key;
      this._render();
    }
  }

  getCardSize() {
    return 2 + (this._config?.count || 5) + (this._config?.show_map ? 4 : 0);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _offers() {
    const attrs = this._hass.states[this._config.entity]?.attributes || {};
    let offers = [...(attrs.offers || [])];
    if (this._config.sort && SORTERS[this._config.sort]) offers.sort(SORTERS[this._config.sort]);
    offers = offers.slice(0, Math.max(1, Number(this._config.count) || 5));
    const upcoming = this._config.show_upcoming ? (attrs.upcoming || []).slice(0, Number(this._config.count) || 5) : [];
    return { offers, upcoming, attrs };
  }

  _render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `<ha-card><div class="warn">${this._t("not_found")}: ${esc(this._config.entity)}</div></ha-card>`;
      return;
    }
    const { offers, upcoming, attrs } = this._offers();
    if (this._selected >= offers.length) this._selected = 0;
    const updated = attrs.updated ? new Date(attrs.updated) : null;

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <div>
            <div class="title">${esc(this._config.title || this._t("title"))}</div>
            <div class="sub">
              ${attrs.country ? `${FLAGS[attrs.country] || esc(attrs.country)} ` : ""}${attrs.value_type ? `${this._t("sorted")}: ${esc(attrs.value_type)}` : ""}
              ${updated ? ` · ${this._t("updated")} ${updated.toLocaleString(this._locale(), { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}` : ""}
            </div>
          </div>
          <button class="icon-btn" id="refresh" title="${this._t("refresh")}"><ha-icon icon="mdi:refresh"></ha-icon></button>
        </div>
        ${(attrs.not_on_sale || []).length ? `<div class="nosale">❌ ${this._t("not_on_sale")}: ${attrs.not_on_sale.map(esc).join(", ")}</div>` : ""}
        ${offers.length === 0 ? `<div class="empty">${this._t("none")}</div>` : ""}
        ${this._config.show_map && offers.some((o) => o.latitude) ? `<div id="map" style="height:${Number(this._config.map_height) || 240}px"></div>` : ""}
        <div class="list">${offers.map((o, i) => this._row(o, i)).join("")}</div>
        ${upcoming.length ? `<div class="section">${this._t("upcoming")}</div><div class="list">${upcoming.map((o, i) => this._row(o, i, true)).join("")}</div>` : ""}
      </ha-card>`;

    this.shadowRoot.getElementById("refresh")?.addEventListener("click", () =>
      this._hass.callService("akce_na_pivo", "refresh", {})
    );
    this.shadowRoot.querySelectorAll(".row[data-index]").forEach((row) =>
      row.addEventListener("click", (ev) => {
        if (ev.target.closest("a")) return;
        this._select(Number(row.dataset.index));
      })
    );
    if (this._config.show_map) this._setupMap();
  }

  disconnectedCallback() {
    this._resize?.disconnect();
    this._resize = null;
  }

  _row(o, i, upcoming = false) {
    const cfg = this._config;
    const selected = !upcoming && i === this._selected;
    const flags = cfg.show_flags ? (o.flags || []).map((f, k) => `<span class="chip ${(o.flag_keys ? HOT_FLAGS.includes(o.flag_keys[k]) : /Nejlevněji|Pod limitem/.test(f)) ? "hot" : ""}">${esc(f)}</span>`).join("") : "";
    const where = [
      o.store_name && o.store_name !== o.shop ? esc(o.store_name) : "",
      cfg.show_address && o.address ? esc(o.address) : "",
      o.distance_km != null ? `<b>${Number(o.distance_km).toLocaleString(this._locale(), { maximumFractionDigits: 1 })} km</b>` : o.online ? "online" : "",
    ].filter(Boolean).join(" · ");
    const validity = o.valid_from && o.valid_to
      ? `${shortDate(o.valid_from)} – ${shortDate(o.valid_to)}`
      : o.valid_to ? `do ${shortDate(o.valid_to)}` : esc(o.validity || "");
    return `
      <div class="row ${selected ? "selected" : ""} ${upcoming ? "upcoming" : ""}" ${upcoming ? "" : `data-index="${i}"`}>
        <div class="rank">${upcoming ? "⏳" : i + 1}</div>
        ${cfg.show_images && o.image ? `<img class="img" src="${esc(o.image)}" alt="" loading="lazy">` : ""}
        <div class="info">
          <div class="product">${esc(o.product)}</div>
          <div class="shop">${esc(o.shop)}${o.degree ? ` · <b>${Number(o.degree)}°</b>` : ""}${PACKAGING_ICONS[o.packaging] ? ` · ${PACKAGING_ICONS[o.packaging]} ${this._t(o.packaging)}` : ""}${o.amount ? ` · ${esc(o.amount)}` : ""}${o.loyalty ? ` · <ha-icon class="small" icon="mdi:card-account-details-outline"></ha-icon>` : ""}</div>
          ${where ? `<div class="where">${where}</div>` : ""}
          ${o.opening_hours && selected ? `<div class="where">🕒 ${esc(o.opening_hours)}</div>` : ""}
          <div class="meta">${validity ? `<span class="valid">${validity}</span>` : ""}${flags}${this._sourceChips(o)}</div>
          ${selected ? `<div class="links">
              ${o.map_url ? `<a href="${esc(o.map_url)}" target="_blank" rel="noopener">Mapy.com</a>` : ""}
              ${o.navigate_url ? `<a href="${esc(o.navigate_url)}" target="_blank" rel="noopener">${this._t("navigate")}</a>` : ""}
              ${o.url ? `<a href="${esc(o.url)}" target="_blank" rel="noopener">${this._t("leaflet")}</a>` : ""}
            </div>` : ""}
        </div>
        <div class="prices">
          <div class="price">${this._money(o.price)}</div>
          ${o.old_price ? `<div class="old">${this._money(o.old_price)}</div>` : ""}
          ${o.discount_percent ? `<div class="disc">−${Number(o.discount_percent)} %</div>` : ""}
          ${o.price_per_half_liter ? `<div class="unit">${this._money(o.price_per_half_liter)} / 0,5 l</div>` : ""}
        </div>
      </div>`;
  }

  _lang() {
    const attrs = this._hass?.states[this._config?.entity]?.attributes || {};
    return pickLang(this._config?.language, attrs.language, this._hass?.language, attrs.country === "SK" ? "sk" : "");
  }

  _t(key) {
    return I18N[this._lang()][key] ?? I18N.cs[key] ?? key;
  }

  _locale() {
    return LOCALES[this._lang()];
  }

  _money(value) {
    const attrs = this._hass?.states[this._config.entity]?.attributes || {};
    return money(value, attrs.currency_symbol || "Kč", this._locale());
  }

  _sourceChips(o) {
    if (!this._config.show_source) return "";
    const names = this._hass.states[this._config.entity]?.attributes?.source_names || {};
    const list = o.sources && o.sources.length ? o.sources : o.source ? [o.source] : [];
    return list.map((s) => `<span class="chip src">${esc(names[s] || s)}</span>`).join("");
  }

  _select(index) {
    this._selected = index;
    const { offers, attrs } = this._offers();
    const list = this.shadowRoot.querySelector(".list");
    if (list) list.innerHTML = offers.map((o, i) => this._row(o, i)).join("");
    this.shadowRoot.querySelectorAll(".list .row[data-index]").forEach((row) =>
      row.addEventListener("click", (ev) => {
        if (ev.target.closest("a")) return;
        this._select(Number(row.dataset.index));
      })
    );
    const offer = offers[index];
    if (offer?.latitude != null) {
      const z = Math.max(this._view?.z || 0, 15);
      const p = project(offer.latitude, offer.longitude, z);
      this._view = { z, cx: p.x, cy: p.y };
    }
    this._drawMap();
  }

  // ------------------------------------------------------------------ mapa
  _mapPoints() {
    const { offers, attrs } = this._offers();
    const points = offers
      .map((o, i) => ({ o, i }))
      .filter(({ o }) => o.latitude != null && o.longitude != null);
    const home = attrs.location?.latitude != null ? attrs.location : null;
    return { points, home };
  }

  _setupMap() {
    const el = this.shadowRoot.getElementById("map");
    if (!el) return;
    this._resize?.disconnect();
    this._resize = new ResizeObserver(() => this._drawMap());
    this._resize.observe(el);

    // posun mapy tažením
    let drag = null;
    el.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".pin, .zoom")) return;
      const v = this._currentView();
      if (!v) return;
      drag = { x: ev.clientX, y: ev.clientY, v, moved: false };
      el.setPointerCapture(ev.pointerId);
    });
    el.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const dx = ev.clientX - drag.x;
      const dy = ev.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      this._view = { z: drag.v.z, cx: drag.v.cx - dx, cy: drag.v.cy - dy };
      this._drawMap();
    });
    const end = () => (drag = null);
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    this._drawMap();
  }

  // automatický výřez, do kterého se vejdou všechny obchody i domov
  _fitView(width, height) {
    const { points, home } = this._mapPoints();
    const coords = points.map(({ o }) => [o.latitude, o.longitude]);
    if (home) coords.push([home.latitude, home.longitude]);
    if (!coords.length) return null;
    for (let z = 16; z >= 3; z--) {
      const px = coords.map(([lat, lon]) => project(lat, lon, z));
      const xs = px.map((p) => p.x);
      const ys = px.map((p) => p.y);
      const w = Math.max(...xs) - Math.min(...xs);
      const h = Math.max(...ys) - Math.min(...ys);
      if ((w <= width - 60 && h <= height - 60) || z === 3) {
        return { z, cx: (Math.max(...xs) + Math.min(...xs)) / 2, cy: (Math.max(...ys) + Math.min(...ys)) / 2 };
      }
    }
    return null;
  }

  _tileProvider() {
    let style = this._config.map_style || "auto";
    if (style === "auto") style = this._hass?.themes?.darkMode ? "carto_dark" : "carto";
    return TILE_PROVIDERS[style] || TILE_PROVIDERS.carto;
  }

  _currentView() {
    const el = this.shadowRoot.getElementById("map");
    if (!el) return null;
    return this._view || this._fitView(el.clientWidth || 400, el.clientHeight || 240);
  }

  _zoom(delta) {
    const v = this._currentView();
    if (!v) return;
    const z = Math.max(3, Math.min(18, v.z + delta));
    const f = 2 ** (z - v.z);
    this._view = { z, cx: v.cx * f, cy: v.cy * f };
    this._drawMap();
  }

  _drawMap() {
    const el = this.shadowRoot.getElementById("map");
    if (!el) return;
    const width = el.clientWidth;
    const height = el.clientHeight;
    if (!width || !height) return; // karta ještě není vykreslená – překreslí ResizeObserver
    const v = this._currentView();
    if (!v) {
      el.innerHTML = "";
      return;
    }
    const provider = this._tileProvider();
    const left = v.cx - width / 2;
    const top = v.cy - height / 2;
    const n = 2 ** v.z;
    let tiles = "";
    for (let ty = Math.floor(top / TILE); ty <= Math.floor((top + height) / TILE); ty++) {
      if (ty < 0 || ty >= n) continue;
      for (let tx = Math.floor(left / TILE); tx <= Math.floor((left + width) / TILE); tx++) {
        const x = ((tx % n) + n) % n;
        const src = provider.url(v.z, x, ty);
        tiles += `<img class="tile" alt="" draggable="false" referrerpolicy="strict-origin-when-cross-origin" src="${src}" style="left:${Math.round(tx * TILE - left)}px;top:${Math.round(ty * TILE - top)}px">`;
      }
    }
    const { points, home } = this._mapPoints();
    const pin = (lat, lon, cls, label, title, index) => {
      const p = project(lat, lon, v.z);
      return `<div class="pin ${cls}" ${index != null ? `data-index="${index}"` : ""} title="${esc(title)}" style="left:${Math.round(p.x - left)}px;top:${Math.round(p.y - top)}px">${label}</div>`;
    };
    let pins = home ? pin(home.latitude, home.longitude, "home", "🏠", this._t("home")) : "";
    // vybraný obchod kreslíme až nakonec, aby byl nahoře
    const ordered = [...points].sort((a, b) => (a.i === this._selected) - (b.i === this._selected));
    for (const { o, i } of ordered) {
      pins += pin(o.latitude, o.longitude, i === this._selected ? "sel" : "", i + 1, `${i + 1}. ${o.store_name || o.shop} – ${this._money(o.price)}`, i);
    }
    el.innerHTML = `
      <div class="tiles">${tiles}</div>
      ${pins}
      <div class="zoom">
        <button data-zoom="1" title="${this._t("zoom_in")}">+</button>
        <button data-zoom="-1" title="${this._t("zoom_out")}">−</button>
        <button data-fit="1" title="${this._t("fit")}">⤢</button>
      </div>
      <div class="attribution">${provider.attribution}</div>`;
    el.querySelectorAll(".pin[data-index]").forEach((node) =>
      node.addEventListener("click", () => this._select(Number(node.dataset.index)))
    );
    el.querySelectorAll("button[data-zoom]").forEach((b) =>
      b.addEventListener("click", () => this._zoom(Number(b.dataset.zoom)))
    );
    el.querySelector("button[data-fit]")?.addEventListener("click", () => {
      this._view = null;
      this._drawMap();
    });
  }
}

const STYLE = `
  ha-card { overflow: hidden; }
  .header { display:flex; align-items:center; justify-content:space-between; padding:14px 16px 8px; }
  .title { font-size: 1.25em; font-weight: 600; }
  .sub { color: var(--secondary-text-color); font-size: .8em; margin-top: 2px; }
  .icon-btn { background:none; border:none; cursor:pointer; color: var(--primary-text-color); padding:6px; border-radius:50%; }
  .icon-btn:hover { background: var(--secondary-background-color); }
  #map { position: relative; width: 100%; overflow: hidden; background: #e8e4d8; touch-action: none; cursor: grab; user-select: none; }
  #map .tiles { position:absolute; inset:0; }
  #map .tile { position:absolute; width:256px; height:256px; pointer-events:none; }
  #map .pin { position:absolute; transform: translate(-50%, -50%); cursor: pointer; z-index: 2; }
  #map .pin.home { cursor: default; background:#1976d2; font-size:14px; }
  #map .zoom { position:absolute; top:8px; right:8px; display:flex; flex-direction:column; gap:4px; z-index:3; }
  #map .zoom button { width:30px; height:30px; border:0; border-radius:8px; background: rgba(255,255,255,.92); color:#333;
         font-size:18px; font-weight:700; cursor:pointer; box-shadow:0 1px 4px rgba(0,0,0,.3); }
  #map .attribution { position:absolute; right:0; bottom:0; font-size:10px; padding:1px 5px; background: rgba(255,255,255,.8); color:#333; z-index:3; }
  #map .attribution a { color:#333; }
  .list { padding: 4px 8px 10px; }
  .section { padding: 8px 16px 0; font-weight: 600; color: var(--secondary-text-color); }
  .row { display:flex; gap:10px; align-items:flex-start; padding:10px 8px; border-radius:12px; cursor:pointer; }
  .row + .row { border-top: 1px solid var(--divider-color); }
  .row.selected { background: rgba(217,142,4,.12); }
  .row.upcoming { cursor: default; opacity: .8; }
  .rank { flex:0 0 26px; height:26px; border-radius:50%; background:#d98e04; color:#fff; font-weight:700;
          display:flex; align-items:center; justify-content:center; font-size:.9em; }
  .row.upcoming .rank { background: none; }
  .img { width:46px; height:46px; object-fit:contain; border-radius:8px; background:#fff; flex:0 0 46px; }
  .info { flex:1 1 auto; min-width:0; }
  .product { font-weight:600; line-height:1.25; }
  .shop { color: var(--primary-text-color); font-size:.9em; margin-top:2px; }
  .where { color: var(--secondary-text-color); font-size:.82em; margin-top:2px; }
  .meta { display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }
  .valid { font-size:.75em; color: var(--secondary-text-color); padding:2px 0; margin-right:4px; }
  .chip { font-size:.7em; padding:2px 7px; border-radius:10px; background: var(--secondary-background-color); color: var(--primary-text-color); }
  .chip.hot { background:#2e7d32; color:#fff; }
  .chip.src { background:none; border:1px solid var(--divider-color); color: var(--secondary-text-color); }
  .links { display:flex; gap:12px; margin-top:6px; font-size:.85em; }
  .links a { color: var(--primary-color); text-decoration:none; font-weight:500; }
  .prices { text-align:right; flex:0 0 auto; }
  .price { font-size:1.2em; font-weight:700; color:#d98e04; white-space:nowrap; }
  .old { text-decoration: line-through; color: var(--secondary-text-color); font-size:.8em; }
  .disc { display:inline-block; background:#c62828; color:#fff; border-radius:6px; padding:0 5px; font-size:.75em; font-weight:700; }
  .unit { color: var(--secondary-text-color); font-size:.78em; white-space:nowrap; margin-top:2px; }
  .nosale { padding: 0 16px 6px; font-size: .85em; color: var(--secondary-text-color); }
  .empty, .warn { padding: 16px; color: var(--secondary-text-color); }
  ha-icon.small { --mdc-icon-size: 16px; vertical-align: -3px; }
  .pin { width:28px; height:28px; border-radius:50%; background:#d98e04; color:#fff; font-weight:700;
         display:flex; align-items:center; justify-content:center; border:2px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.4); font: 700 13px sans-serif; }
  .pin.sel { background:#2e7d32; transform: scale(1.15); }
  .pin.home { background:#1976d2; font-size:14px; }
`;

class AkceNaPivoCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => (LABELS[EDITOR_LANG] || LABELS.cs)[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    const attrs = this._hass.states[this._config.entity]?.attributes || {};
    EDITOR_LANG = pickLang(this._config.language, attrs.language, this._hass.language);
    this._form.schema = editorSchema(EDITOR_LANG);
    this._form.data = { count: 5, show_map: true, show_images: true, show_flags: true, show_address: true, show_source: true, map_height: 240, ...this._config };
  }
}

const LABELS = {
  cs: {
    entity: "Entita (senzor Nejlevnější pivo)", title: "Nadpis (prázdné = výchozí)", language: "Jazyk karty",
    count: "Počet zobrazených nabídek", sort: "Řazení v kartě", show_map: "Zobrazit mapu",
    map_height: "Výška mapy (px)", map_style: "Mapový podklad", show_images: "Obrázky produktů", show_address: "Adresa obchodu",
    show_flags: "Štítky (sleva, historické minimum…)", show_source: "Zdroj akce (Kupi, Kompas Slev…)",
    show_upcoming: "Zobrazit připravované akce",
  },
  sk: {
    entity: "Entita (senzor Najlacnejšie pivo)", title: "Nadpis (prázdne = predvolený)", language: "Jazyk karty",
    count: "Počet zobrazených ponúk", sort: "Zoradenie v karte", show_map: "Zobraziť mapu",
    map_height: "Výška mapy (px)", map_style: "Mapový podklad", show_images: "Obrázky produktov", show_address: "Adresa obchodu",
    show_flags: "Štítky (zľava, historické minimum…)", show_source: "Zdroj akcie (Zlacnene, Kimbino…)",
    show_upcoming: "Zobraziť pripravované akcie",
  },
  en: {
    entity: "Entity (Cheapest beer sensor)", title: "Title (empty = default)", language: "Card language",
    count: "Number of deals shown", sort: "Sorting in the card", show_map: "Show map",
    map_height: "Map height (px)", map_style: "Map style", show_images: "Product images", show_address: "Store address",
    show_flags: "Labels (discount, historic low…)", show_source: "Deal source (Kupi, Kompas Slev…)",
    show_upcoming: "Show upcoming deals",
  },
};

const SORT_LABELS = {
  cs: ["Podle integrace", "Cena za 0,5 l", "Cena za balení", "Vzdálenost"],
  sk: ["Podľa integrácie", "Cena za 0,5 l", "Cena za balenie", "Vzdialenosť"],
  en: ["As in the integration", "Price per 0.5 l", "Package price", "Distance"],
};

const editorSchema = (lang) => {
  const sorts = SORT_LABELS[lang] || SORT_LABELS.cs;
  return [
    { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "akce_na_pivo" } } },
    { name: "title", selector: { text: {} } },
    {
      name: "language",
      selector: {
        select: {
          mode: "dropdown",
          options: [
            { value: "", label: "Auto (HA / integrace)" },
            { value: "cs", label: "Čeština" },
            { value: "sk", label: "Slovenčina" },
            { value: "en", label: "English" },
          ],
        },
      },
    },
    {
      type: "grid",
      name: "",
      schema: [
        { name: "count", selector: { number: { min: 1, max: 10, mode: "box" } } },
        {
          name: "sort",
          selector: {
            select: {
              mode: "dropdown",
              options: ["", "unit", "price", "distance"].map((value, i) => ({ value, label: sorts[i] })),
            },
          },
        },
        { name: "show_map", selector: { boolean: {} } },
        { name: "map_height", selector: { number: { min: 120, max: 600, step: 10, mode: "box" } } },
        {
          name: "map_style",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "auto", label: "Auto (světlá / tmavá podle motivu)" },
                { value: "carto", label: "CARTO Voyager" },
                { value: "carto_dark", label: "CARTO Dark" },
                { value: "osm", label: "OpenStreetMap (může být blokované)" },
              ],
            },
          },
        },
        { name: "show_images", selector: { boolean: {} } },
        { name: "show_address", selector: { boolean: {} } },
        { name: "show_flags", selector: { boolean: {} } },
        { name: "show_source", selector: { boolean: {} } },
        { name: "show_upcoming", selector: { boolean: {} } },
      ],
    },
  ];
};

if (!customElements.get("akce-na-pivo-card")) customElements.define("akce-na-pivo-card", AkceNaPivoCard);
if (!customElements.get("akce-na-pivo-card-editor")) customElements.define("akce-na-pivo-card-editor", AkceNaPivoCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "akce-na-pivo-card")) {
  window.customCards.push({
    type: "akce-na-pivo-card",
    name: "Akce na pivo",
    description: "Nejlevnější pivo v akci – seznam obchodů, ceny a mapa (CZ / SK / EN).",
    preview: true,
    documentationURL: "https://github.com/joshuaaaaa/HA-akce-na-pivo#lovelace-karty-slo%C5%BEka-www",
  });
}
