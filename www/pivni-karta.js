/*
 * 🍺 Pivní karta – samostatná Lovelace karta pro integraci "Akce na pivo"
 *
 * Ukáže, KAM JÍT pro nejlevnější pivo (obchod, adresa, vzdálenost, cena),
 * výběr značky, žebříček nejlevnějších akcí a mapu – vše na pivním pozadí
 * s pěnou a bublinkami.
 *
 * Instalace (bez HACS):
 *   1. zkopírujte soubor do /config/www/pivni-karta.js
 *   2. Nastavení → Ovládací panely → ⋮ → Zdroje → Přidat zdroj
 *        URL: /local/pivni-karta.js      Typ: JavaScript modul
 *   3. do dashboardu přidejte kartu "Pivní karta" (type: custom:pivni-karta)
 */

const PIVNI_KARTA_VERSION = "1.5.0";

console.info(
  `%c 🍺 PIVNI-KARTA %c v${PIVNI_KARTA_VERSION} `,
  "color:#3b1f00;background:#f6b21b;font-weight:700;border-radius:3px 0 0 3px",
  "color:#f6b21b;background:#3b1f00;border-radius:0 3px 3px 0"
);

const FLAGS = { CZ: "🇨🇿", SK: "🇸🇰" };
const ALL = "__all__";
// Texty karty – čeština, slovenčina, angličtina
const I18N = {
  cs: {
    title: "Kam na pivo", updated: "aktualizováno", waiting: "čekám na data…", all: "Vše",
    any_pack: "Každý obal", any_degree: "Každý stupeň", not_on_sale: "Není v akci",
    go: "Dnes jdi do", sorry: "Bohužel", selected_beer: "Vybrané pivo", now_not_on_sale: "teď není v akci 😢",
    navigate: "Navigovat", map: "Mapa", leaflet: "Leták", ranking: "🏆 Nejlevnější akce",
    loyalty_only: "jen s kartou", online: "online obchod", refresh: "Aktualizovat akce",
    glass: "Sklo", can: "Plech", pet: "PET", other: "Ostatní", brand_select: "Výběr značky",
    all_brands: "Všechny značky", need_entity: "Zadejte entitu – senzor „Nejlevnější pivo“ z integrace Akce na pivo",
    not_found: "Entita nenalezena",
  },
  sk: {
    title: "Kam na pivo", updated: "aktualizované", waiting: "čakám na dáta…", all: "Všetko",
    any_pack: "Každý obal", any_degree: "Každý stupeň", not_on_sale: "Nie je v akcii",
    go: "Dnes choď do", sorry: "Bohužiaľ", selected_beer: "Vybrané pivo", now_not_on_sale: "teraz nie je v akcii 😢",
    navigate: "Navigovať", map: "Mapa", leaflet: "Leták", ranking: "🏆 Najlacnejšie akcie",
    loyalty_only: "len s kartou", online: "online obchod", refresh: "Aktualizovať akcie",
    glass: "Sklo", can: "Plech", pet: "PET", other: "Ostatné", brand_select: "Výber značky",
    all_brands: "Všetky značky", need_entity: "Zadajte entitu – senzor „Najlacnejšie pivo“ z integrácie Akcie na pivo",
    not_found: "Entita sa nenašla",
  },
  en: {
    title: "Where to buy beer", updated: "updated", waiting: "waiting for data…", all: "All",
    any_pack: "Any packaging", any_degree: "Any degree", not_on_sale: "Not on sale",
    go: "Today go to", sorry: "Sorry", selected_beer: "Selected beer", now_not_on_sale: "is not on sale now 😢",
    navigate: "Navigate", map: "Map", leaflet: "Flyer", ranking: "🏆 Cheapest deals",
    loyalty_only: "loyalty card only", online: "online shop", refresh: "Refresh deals",
    glass: "Glass", can: "Can", pet: "PET", other: "Other", brand_select: "Brand",
    all_brands: "All brands", need_entity: "Set the entity – the “Cheapest beer” sensor of the Akce na pivo integration",
    not_found: "Entity not found",
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
// v editoru ještě nemáme data – jazyk podle HA
let EDITOR_LANG = "cs";

const DEGREES = { "10": "10°", "11": "11°", "12": "12°", other: "other" };
const BRAND_CHIPS_MAX = 6;
const degreeGroup = (d) => (d == null ? null : [10, 11, 12].includes(Number(d)) ? String(d) : "other");
const PACKAGING = {
  glass: { icon: "🍾", label: "glass" },
  can: { icon: "🥫", label: "can" },
  pet: { icon: "🧴", label: "pet" },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const fmt = (value, symbol, locale = "cs-CZ") =>
  value === null || value === undefined || value === ""
    ? "–"
    : `${Number(value).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${symbol}`;

const km = (value, locale = "cs-CZ") =>
  value === null || value === undefined ? "" : `${Number(value).toLocaleString(locale, { maximumFractionDigits: 1 })} km`;

const shortDate = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getDate()}. ${d.getMonth() + 1}.`;
};

class PivniKarta extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._brand = null;
    this._packaging = null;
    this._degree = null;
    this._lastKey = "";
  }

  static getConfigElement() {
    return document.createElement("pivni-karta-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.offers) && "sort_by" in hass.states[id].attributes
    );
    return { entity: entity || "" };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error(I18N[pickLang(config?.language, navigator.language)].need_entity);
    this._config = {
      count: 5,
      show_map: true,
      show_list: true,
      show_brands: true,
      show_packaging: true,
      show_degrees: true,
      bubbles: true,
      map_height: 180,
      ...config,
    };
    this._brand = this._config.brand || null;
    this._packaging = this._config.packaging || null;
    this._degree = this._config.degree ? String(this._config.degree) : null;
    this._picked = null;
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
    return 5 + (this._config?.show_list ? this._config.count : 0) + (this._config?.show_map ? 3 : 0);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _lang() {
    return pickLang(this._config?.language, this._attrs().language, this._hass?.language, this._attrs().country === "SK" ? "sk" : "");
  }

  _t(key) {
    return I18N[this._lang()][key] ?? I18N.cs[key] ?? key;
  }

  _packLabel(kind) {
    return PACKAGING[kind] ? this._t(PACKAGING[kind].label) : "";
  }

  _degreeLabel(kind) {
    return kind === "other" ? this._t("other") : DEGREES[kind] || "";
  }

  _attrs() {
    return this._hass.states[this._config.entity]?.attributes || {};
  }

  _selection(attrs) {
    const brand = this._brand && this._brand !== ALL ? this._brand : null;
    const pack = this._packaging && this._packaging !== ALL ? this._packaging : null;
    const deg = this._degree && this._degree !== ALL ? this._degree : null;
    const list = (attrs.offers || []).filter(
      (o) => (!brand || o.brand === brand) && (!pack || o.packaging === pack) && (!deg || degreeGroup(o.degree) === deg)
    );
    // nabídka mimo zobrazený seznam (nejlevnější pro značku / obal) z atributů senzoru
    let best = list[0] || null;
    if (!best && brand && !pack && !deg) best = (attrs.brands || {})[brand] || null;
    if (!best && pack && !brand && !deg) best = (attrs.packaging_best || {})[pack] || null;
    if (!best && deg && !brand && !pack) best = (attrs.degree_best || {})[deg] || null;
    return { best, list: list.length ? list : best ? [best] : [] };
  }

  _render() {
    if (!this._config || !this._hass) return;
    const stateObj = this._hass.states[this._config.entity];
    if (!stateObj) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="beer"><div class="empty">${this._t("not_found")}: ${esc(this._config.entity)}</div></div></ha-card>`;
      return;
    }
    const attrs = this._attrs();
    const symbol = attrs.currency_symbol || "Kč";
    const locale = LOCALES[this._lang()];
    this._locale = locale;
    // jen možnosti vybrané v nastavení integrace, na které je teď nějaká akce
    const selected = attrs.selected || {};
    const degKinds = Object.keys(DEGREES).filter(
      (k) =>
        (!selected.degrees || selected.degrees.includes(k)) &&
        ((attrs.degree_best || {})[k] || (attrs.offers || []).some((o) => degreeGroup(o.degree) === k))
    );
    const packKinds = Object.keys(PACKAGING).filter(
      (k) =>
        (!selected.packaging || selected.packaging.includes(k)) &&
        ((attrs.packaging_best || {})[k] || (attrs.offers || []).some((o) => o.packaging === k))
    );
    // výchozí obal/stupeň z karty, který v integraci vybraný není, se ignoruje
    if (this._packaging && this._packaging !== ALL && !packKinds.includes(this._packaging)) this._packaging = null;
    if (this._degree && this._degree !== ALL && !degKinds.includes(this._degree)) this._degree = null;
    const selection = this._selection(attrs);
    const list = selection.list;
    // klepnutím na akci v žebříčku se ukáže nahoře
    const best = (this._picked && list.find((o) => this._offerKey(o) === this._picked)) || selection.best;
    const notOnSale = attrs.not_on_sale || [];
    const brandNames = [...Object.keys(attrs.brands || {}), ...notOnSale.filter((b) => !(attrs.brands || {})[b])];
    const count = Math.max(1, Number(this._config.count) || 5);
    const updated = attrs.updated ? new Date(attrs.updated) : null;

    const bubbles = this._config.bubbles
      ? `<div class="bubbles" aria-hidden="true">${Array.from({ length: 18 }, (_, i) => {
          const size = 4 + ((i * 7) % 9);
          return `<span style="left:${(i * 53) % 100}%;width:${size}px;height:${size}px;animation-duration:${6 + ((i * 3) % 7)}s;animation-delay:-${(i * 1.7) % 9}s"></span>`;
        }).join("")}</div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card><div class="beer">
        ${bubbles}
        <div class="foam">
          <div class="head">
            <div class="title">🍺 ${esc(this._config.title || this._t("title"))} ${attrs.country ? FLAGS[attrs.country] || "" : ""}</div>
            <button class="refresh" title="${this._t("refresh")}" aria-label="${this._t("refresh")}"><ha-icon icon="mdi:refresh"></ha-icon></button>
          </div>
          <div class="sub">${updated ? `${this._t("updated")} ${updated.toLocaleString(locale, { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}` : this._t("waiting")}</div>
        </div>

        <div class="content">
          ${this._config.show_brands && brandNames.length > 1 && brandNames.length > BRAND_CHIPS_MAX ? `
            <div class="brands">
              <select class="brand-select" aria-label="${this._t("brand_select")}">
                <option value="${ALL}" ${!this._brand || this._brand === ALL ? "selected" : ""}>${this._t("all_brands")} (${brandNames.length})</option>
                ${brandNames.map((b) => `<option value="${esc(b)}" ${this._brand === b ? "selected" : ""}>${esc(b)}${notOnSale.includes(b) ? ` – ${this._t("not_on_sale").toLowerCase()}` : ""}</option>`).join("")}
              </select>
            </div>` : ""}
          ${this._config.show_brands && brandNames.length > 1 && brandNames.length <= BRAND_CHIPS_MAX ? `
            <div class="brands" role="tablist">
              <button class="chip ${!this._brand || this._brand === ALL ? "on" : ""}" data-brand="${ALL}">${this._t("all")}</button>
              ${brandNames.map((b) => `<button class="chip ${this._brand === b ? "on" : ""} ${notOnSale.includes(b) ? "off" : ""}" data-brand="${esc(b)}" ${notOnSale.includes(b) ? `title="${this._t("not_on_sale")}"` : ""}>${esc(b)}</button>`).join("")}
            </div>` : ""}
          ${notOnSale.length && (!this._brand || this._brand === ALL) ? `<div class="nosale">❌ ${this._t("not_on_sale")}: ${notOnSale.map(esc).join(", ")}</div>` : ""}
          ${this._config.show_packaging && packKinds.length > 1 ? `
            <div class="brands packs" role="tablist">
              <button class="chip ${!this._packaging || this._packaging === ALL ? "on" : ""}" data-pack="${ALL}">${this._t("any_pack")}</button>
              ${packKinds.map((k) => `<button class="chip ${this._packaging === k ? "on" : ""}" data-pack="${k}">${PACKAGING[k].icon} ${this._packLabel(k)}</button>`).join("")}
            </div>` : ""}
          ${this._config.show_degrees && degKinds.length > 1 ? `
            <div class="brands packs" role="tablist">
              <button class="chip ${!this._degree || this._degree === ALL ? "on" : ""}" data-deg="${ALL}">${this._t("any_degree")}</button>
              ${degKinds.map((k) => `<button class="chip ${this._degree === k ? "on" : ""}" data-deg="${k}">${this._degreeLabel(k)}</button>`).join("")}
            </div>` : ""}

          ${best ? this._hero(best, symbol) : `<div class="hero nosale-hero"><div class="go">${this._t("sorry")}</div><div class="shop">${this._brand && this._brand !== ALL ? esc(this._brand) : this._t("selected_beer")}${this._packaging && this._packaging !== ALL ? ` (${this._packLabel(this._packaging).toLowerCase()})` : ""}${this._degree && this._degree !== ALL ? ` ${this._degreeLabel(this._degree)}` : ""}</div><div class="where">${this._t("now_not_on_sale")}</div></div>`}

          ${best && this._config.show_map && best.latitude != null ? this._map(best) : ""}

          ${this._config.show_list && list.length > 1 ? `
            <div class="section">${this._t("ranking")}</div>
            <div class="list">${list.slice(0, count).map((o, i) => this._row(o, i, symbol, o === best)).join("")}</div>` : ""}
        </div>
      </div></ha-card>`;

    this.shadowRoot.querySelector(".refresh")?.addEventListener("click", () =>
      this._hass.callService("akce_na_pivo", "refresh", {})
    );
    this.shadowRoot.querySelectorAll(".brands .chip").forEach((chip) =>
      chip.addEventListener("click", () => {
        this._picked = null;
        if (chip.dataset.brand) this._brand = chip.dataset.brand;
        if (chip.dataset.pack) this._packaging = chip.dataset.pack;
        if (chip.dataset.deg) this._degree = chip.dataset.deg;
        this._render();
      })
    );
    this._bindExtra();
  }

  _offerKey(o) {
    return `${o.shop}|${o.product}|${o.price}`;
  }

  _bindExtra() {
    this.shadowRoot.querySelector(".brand-select")?.addEventListener("change", (ev) => {
      this._brand = ev.target.value;
      this._picked = null;
      this._render();
    });
    this.shadowRoot.querySelectorAll(".list .row[data-key]").forEach((row) =>
      row.addEventListener("click", () => {
        this._picked = row.dataset.key;
        this._render();
        this.shadowRoot.querySelector(".hero")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      })
    );
  }

  _hero(o, symbol) {
    const shop = o.store_name || o.shop;
    const validity = o.valid_from && o.valid_to
      ? `${shortDate(o.valid_from)} – ${shortDate(o.valid_to)}`
      : o.valid_to ? `do ${shortDate(o.valid_to)}` : esc(o.validity || "");
    const flags = (o.flags || []).slice(0, 4).map((f) => `<span class="tag">${esc(f)}</span>`).join("");
    return `
      <div class="hero">
        ${o.discount_percent ? `<div class="badge">−${Number(o.discount_percent)} %</div>` : ""}
        <div class="go">${this._t("go")}</div>
        <div class="shop">${esc(shop)}</div>
        <div class="where">
          ${o.address ? `<ha-icon icon="mdi:map-marker"></ha-icon>${esc(o.address)}` : o.online ? this._t("online") : ""}
          ${o.distance_km != null ? `<span class="dist">${km(o.distance_km, this._locale)}</span>` : ""}
        </div>
        ${o.opening_hours ? `<div class="hours"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(o.opening_hours)}</div>` : ""}
        <div class="deal">
          <div class="product">
            ${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy">` : `<div class="mug">🍺</div>`}
            <div>
              <div class="pname">${esc(o.product)}</div>
              <div class="pmeta">${o.degree ? `<b>${Number(o.degree)}°</b> · ` : ""}${PACKAGING[o.packaging] ? `${PACKAGING[o.packaging].icon} ${this._packLabel(o.packaging)} · ` : ""}${o.amount ? esc(o.amount) : ""}${validity ? ` · ${validity}` : ""}${o.loyalty ? ` · ${this._t("loyalty_only")}` : ""}</div>
            </div>
          </div>
          <div class="price">
            <div class="big">${fmt(o.price, symbol, this._locale)}</div>
            ${o.old_price ? `<div class="old">${fmt(o.old_price, symbol, this._locale)}</div>` : ""}
            ${o.price_per_half_liter ? `<div class="unit">${fmt(o.price_per_half_liter, symbol, this._locale)} / 0,5 l</div>` : ""}
          </div>
        </div>
        ${flags ? `<div class="tags">${flags}</div>` : ""}
        <div class="actions">
          ${o.navigate_url ? `<a class="btn primary" href="${esc(o.navigate_url)}" target="_blank" rel="noopener"><ha-icon icon="mdi:navigation-variant"></ha-icon>${this._t("navigate")}</a>` : ""}
          ${o.map_url ? `<a class="btn" href="${esc(o.map_url)}" target="_blank" rel="noopener"><ha-icon icon="mdi:map"></ha-icon>${this._t("map")}</a>` : ""}
          ${o.url ? `<a class="btn" href="${esc(o.url)}" target="_blank" rel="noopener"><ha-icon icon="mdi:newspaper-variant-outline"></ha-icon>${this._t("leaflet")}</a>` : ""}
        </div>
      </div>`;
  }

  _map(o) {
    const d = 0.006;
    const src = `https://www.openstreetmap.org/export/embed.html?bbox=${o.longitude - d},${o.latitude - d / 2},${o.longitude + d},${o.latitude + d / 2}&layer=mapnik&marker=${o.latitude},${o.longitude}`;
    return `<div class="map" style="height:${Number(this._config.map_height) || 180}px"><iframe title="Mapa obchodu" loading="lazy" src="${src}"></iframe></div>`;
  }

  _row(o, i, symbol, isBest) {
    return `
      <div class="row ${isBest ? "best" : ""}" data-key="${esc(this._offerKey(o))}">
        <div class="rank">${i + 1}</div>
        <div class="info">
          <div class="rname">${esc(o.product)}</div>
          <div class="rshop">${esc(o.store_name || o.shop)}${o.distance_km != null ? ` · ${km(o.distance_km, this._locale)}` : ""}</div>
        </div>
        <div class="rprice">
          <div>${fmt(o.price, symbol, this._locale)}</div>
          ${o.price_per_half_liter ? `<small>${fmt(o.price_per_half_liter, symbol, this._locale)}/0,5 l</small>` : ""}
        </div>
      </div>`;
  }
}

const STYLE = `
  :host { display:block; }
  ha-card {
    display:block; overflow:hidden; background:none; border:0;
    border-radius: var(--ha-card-border-radius, 16px);
  }
  .beer {
    position: relative; overflow: hidden; color: #2b1600;
    border-radius: var(--ha-card-border-radius, 16px);
    background:
      radial-gradient(120% 60% at 20% 110%, rgba(255,255,255,.18), transparent 60%),
      linear-gradient(175deg, #ffd35c 0%, #f6b21b 38%, #e08a0b 75%, #b8640a 100%);
    box-shadow: 0 6px 18px rgba(120,60,0,.35), inset 0 0 0 1px rgba(255,255,255,.15);
  }
  /* bublinky */
  .bubbles { position:absolute; inset:0; pointer-events:none; z-index:0; }
  .bubbles span {
    position:absolute; bottom:-12px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,.95), rgba(255,255,255,.35) 60%, rgba(255,255,255,.1));
    animation-name: rise; animation-timing-function: ease-in; animation-iteration-count: infinite;
  }
  @keyframes rise {
    0% { transform: translate(0, 0); opacity: 0; }
    10% { opacity: .9; }
    50% { transform: translate(6px, -50vh); }
    100% { transform: translate(-4px, -110vh); opacity: 0; }
  }
  @media (prefers-reduced-motion: reduce) { .bubbles { display:none; } }

  /* pěna */
  .foam {
    position: relative; z-index: 1; padding: 14px 16px 22px;
    background: #fffaf0;
    box-shadow: 0 2px 0 rgba(255,255,255,.6) inset;
  }
  .foam::after {
    content:""; position:absolute; left:0; right:0; bottom:-14px; height:28px;
    background:
      radial-gradient(circle at 10px 6px, #fffaf0 12px, transparent 13px) 0 0/34px 28px repeat-x,
      radial-gradient(circle at 27px 2px, #fffaf0 10px, transparent 11px) 0 0/34px 28px repeat-x;
  }
  .head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .title { font-size: 1.35em; font-weight: 800; letter-spacing:.2px; color:#6b3a00; }
  .sub { font-size: .8em; color: #9a6a2a; margin-top: 2px; }
  .refresh { background:none; border:0; cursor:pointer; color:#6b3a00; border-radius:50%; padding:6px; }
  .refresh:hover { background: rgba(107,58,0,.08); }

  .content { position:relative; z-index:1; padding: 18px 14px 14px; }

  .brands { display:flex; flex-wrap:wrap; gap:6px; margin-bottom: 12px; }
  .brands.packs { margin-top: -4px; }
  .brand-select {
    font: inherit; font-weight: 700; color: #3b1f00; background: rgba(255,250,240,.85);
    border: 0; border-radius: 10px; padding: 7px 10px; box-shadow: inset 0 0 0 1px rgba(90,48,0,.2); max-width: 100%;
  }
  .list .row { cursor: pointer; }
  .chip {
    border:0; cursor:pointer; font: inherit; font-size:.82em; font-weight:600;
    padding: 5px 11px; border-radius: 999px; color:#5a3000;
    background: rgba(255,250,240,.55); box-shadow: inset 0 0 0 1px rgba(90,48,0,.15);
  }
  .chip.on { background:#3b1f00; color:#ffd35c; box-shadow:none; }
  .chip.off:not(.on) { opacity:.6; text-decoration: line-through; }
  .nosale { margin: -4px 2px 10px; font-size:.82em; font-weight:700; color:#4a2600; }
  .nosale-hero .shop { padding-right: 0; }
  .nosale-hero .where { font-size: 1.05em; font-weight: 700; }

  .hero {
    background: rgba(255,250,240,.9); border-radius: 16px; padding: 14px 14px 12px;
    box-shadow: 0 4px 14px rgba(90,40,0,.25); position: relative;
  }
  .go { text-transform: uppercase; font-size:.72em; font-weight:800; letter-spacing: 1.5px; color:#b8640a; }
  .shop { padding-right: 64px; font-size: 1.9em; font-weight: 900; line-height:1.1; color:#2b1600; margin: 2px 0 4px; word-break: break-word; }
  .where, .hours { display:flex; align-items:center; flex-wrap:wrap; gap:4px; font-size:.9em; color:#5a3a14; }
  .hours { font-size:.8em; margin-top:2px; }
  .where ha-icon, .hours ha-icon { --mdc-icon-size:16px; color:#b8640a; }
  .dist { margin-left:6px; background:#3b1f00; color:#ffd35c; border-radius:999px; padding:1px 8px; font-weight:700; font-size:.85em; }

  .deal { display:flex; align-items:center; gap:10px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(90,48,0,.25); position:relative; }
  .product { display:flex; align-items:center; gap:10px; flex:1; min-width:0; }
  .product img { width:54px; height:54px; object-fit:contain; background:#fff; border-radius:10px; flex:0 0 54px; }
  .mug { font-size: 2.2em; flex:0 0 auto; }
  .pname { font-weight:700; line-height:1.2; }
  .pmeta { font-size:.78em; color:#7a5424; margin-top:2px; }
  .price { text-align:right; flex:0 0 auto; }
  .big { font-size:1.6em; font-weight:900; color:#b34700; white-space:nowrap; }
  .old { font-size:.8em; color:#8a6a4a; text-decoration: line-through; }
  .unit { font-size:.78em; color:#5a3a14; white-space:nowrap; }
  .badge {
    position:absolute; top:12px; right:12px; transform: rotate(8deg);
    background:#c62828; color:#fff; font-weight:900; font-size:.85em; padding:3px 8px; border-radius:8px;
    box-shadow: 0 2px 6px rgba(0,0,0,.25);
  }
  .tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:10px; }
  .tag { font-size:.7em; font-weight:600; padding:2px 8px; border-radius:999px; background:#fde7b0; color:#5a3000; }
  .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
  .btn {
    display:inline-flex; align-items:center; gap:4px; text-decoration:none; font-weight:700; font-size:.85em;
    padding: 7px 12px; border-radius: 10px; color:#3b1f00; background: rgba(59,31,0,.08);
  }
  .btn ha-icon { --mdc-icon-size:18px; }
  .btn.primary { background:#3b1f00; color:#ffd35c; }

  .map { margin-top: 12px; border-radius: 14px; overflow:hidden; box-shadow: 0 4px 14px rgba(90,40,0,.25); background:#fffaf0; }
  .map iframe { width:100%; height:100%; border:0; display:block; }

  .section { margin: 14px 2px 6px; font-weight:800; color:#2b1600; text-shadow: 0 1px 0 rgba(255,255,255,.35); }
  .list { display:flex; flex-direction:column; gap:6px; }
  .row { display:flex; align-items:center; gap:10px; padding: 8px 10px; border-radius: 12px; background: rgba(255,250,240,.72); }
  .row.best { background: rgba(255,250,240,.95); box-shadow: inset 0 0 0 2px #3b1f00; }
  .rank {
    flex:0 0 28px; height:28px; border-radius:8px 8px 10px 10px; display:flex; align-items:center; justify-content:center;
    font-weight:900; color:#3b1f00; background: linear-gradient(#fffaf0 0 30%, #f6b21b 30%); box-shadow: inset 0 0 0 2px #3b1f00;
  }
  .info { flex:1; min-width:0; }
  .rname { font-weight:700; font-size:.9em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .rshop { font-size:.78em; color:#6a4a20; }
  .rprice { text-align:right; font-weight:800; color:#b34700; white-space:nowrap; }
  .rprice small { display:block; font-weight:600; color:#6a4a20; font-size:.72em; }
  .empty { padding: 18px 14px; font-weight:600; position:relative; z-index:1; }
`;

class PivniKartaEditor extends HTMLElement {
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
      this._form.computeLabel = (s) => (EDITOR_LABELS[EDITOR_LANG] || EDITOR_LABELS.cs)[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const attrs = this._hass.states[this._config.entity]?.attributes || {};
    EDITOR_LANG = pickLang(this._config.language, attrs.language, this._hass.language);
    const T = I18N[EDITOR_LANG];
    const brands = Object.keys(attrs.brands || {});
    this._form.hass = this._hass;
    this._form.schema = [
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
        name: "brand",
        selector: {
          select: {
            mode: "dropdown",
            custom_value: true,
            options: [{ value: "", label: T.all_brands }, ...brands.map((b) => ({ value: b, label: b }))],
          },
        },
      },
      {
        name: "degree",
        selector: {
          select: {
            mode: "dropdown",
            options: [{ value: "", label: T.any_degree }, ...Object.keys(DEGREES).map((value) => ({ value, label: value === "other" ? T.other : DEGREES[value] }))],
          },
        },
      },
      {
        name: "packaging",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "", label: T.any_pack },
              ...Object.entries(PACKAGING).map(([value, p]) => ({ value, label: `${p.icon} ${T[p.label]}` })),
            ],
          },
        },
      },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "count", selector: { number: { min: 1, max: 10, mode: "box" } } },
          { name: "map_height", selector: { number: { min: 100, max: 500, step: 10, mode: "box" } } },
          { name: "show_map", selector: { boolean: {} } },
          { name: "show_list", selector: { boolean: {} } },
          { name: "show_brands", selector: { boolean: {} } },
          { name: "show_packaging", selector: { boolean: {} } },
          { name: "show_degrees", selector: { boolean: {} } },
          { name: "bubbles", selector: { boolean: {} } },
        ],
      },
    ];
    this._form.data = { count: 5, map_height: 180, show_map: true, show_list: true, show_brands: true, show_packaging: true, show_degrees: true, bubbles: true, ...this._config };
  }
}

const EDITOR_LABELS = {
  cs: {
    entity: "Senzor „Nejlevnější pivo“", title: "Nadpis (prázdné = výchozí)", language: "Jazyk karty",
    brand: "Výchozí značka", count: "Počet akcí v žebříčku", map_height: "Výška mapy (px)",
    show_map: "Mapa obchodu", show_list: "Žebříček nejlevnějších", show_brands: "Přepínač značek",
    packaging: "Výchozí obal", show_packaging: "Přepínač obalu (sklo / plech / PET)",
    degree: "Výchozí stupeň", show_degrees: "Přepínač stupně (10° / 11° / 12°)", bubbles: "Bublinky 🫧",
  },
  sk: {
    entity: "Senzor „Najlacnejšie pivo“", title: "Nadpis (prázdne = predvolený)", language: "Jazyk karty",
    brand: "Predvolená značka", count: "Počet akcií v rebríčku", map_height: "Výška mapy (px)",
    show_map: "Mapa obchodu", show_list: "Rebríček najlacnejších", show_brands: "Prepínač značiek",
    packaging: "Predvolený obal", show_packaging: "Prepínač obalu (sklo / plech / PET)",
    degree: "Predvolený stupeň", show_degrees: "Prepínač stupňa (10° / 11° / 12°)", bubbles: "Bublinky 🫧",
  },
  en: {
    entity: "“Cheapest beer” sensor", title: "Title (empty = default)", language: "Card language",
    brand: "Default brand", count: "Deals in the ranking", map_height: "Map height (px)",
    show_map: "Store map", show_list: "Cheapest deals ranking", show_brands: "Brand switcher",
    packaging: "Default packaging", show_packaging: "Packaging switcher (glass / can / PET)",
    degree: "Default degree", show_degrees: "Degree switcher (10° / 11° / 12°)", bubbles: "Bubbles 🫧",
  },
};

if (!customElements.get("pivni-karta")) customElements.define("pivni-karta", PivniKarta);
if (!customElements.get("pivni-karta-editor")) customElements.define("pivni-karta-editor", PivniKartaEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "pivni-karta")) {
  window.customCards.push({
    type: "pivni-karta",
    name: "Pivní karta / Pivná karta",
    description: "Kam jít pro nejlevnější pivo – obchod, adresa, cena a mapa na pivním pozadí (CZ / SK / EN).",
    preview: true,
    documentationURL: "https://github.com/joshuaaaaa/HA-akce-na-pivo#lovelace-karty-slo%C5%BEka-www",
  });
}
