# 🍺 Akce na pivo – Home Assistant

Integrace pro Home Assistant, která každý den (nebo v čase, který si nastavíte) zjistí,
**kde je nejlevnější pivo v akci**, najde **nejbližší pobočku** daného obchodu k vašemu
domovu nebo k poloze vašeho telefonu a ukáže ji **na mapě**. Senzor **Kam pro pivo**
rovnou řekne, do kterého obchodu jít.

Ke stažení jsou dvě Lovelace karty:
- 🍺 **[Pivní karta](#pivní-karta)** (`custom:pivni-karta`): samostatná karta na pivním pozadí
  s pěnou a bublinkami. Přidáte ji vložením souboru do `www`.
- **[Seznam akcí s mapou](#karta-součást-custom-component)** (`custom:akce-na-pivo-card`):
  přibalená v integraci, načte se sama.

- **Česko 🇨🇿 nebo Slovensko 🇸🇰**: zemi vyberete při přidání integrace.
- Ceny z více webů s letákovými akcemi (Albert, Billa, Globus, Kaufland, Lidl, Penny, Tesco,
  Makro, Norma, COOP, JIP, Hruška, na Slovensku COOP Jednota, Terno, Fresh, Kraj, Metro…).
  Stejná akce nalezená na víc webech se sloučí.
- Pobočky, adresy a otevírací doby z OpenStreetMap (Overpass + Nominatim)

## Česko, nebo Slovensko

Při přidání integrace nejdřív zvolíte **zemi**:

| | 🇨🇿 Česko | 🇸🇰 Slovensko |
|---|---|---|
| Weby s akcemi | Kupi.cz, Kompas Slev, AkcniCeny.cz, Cenito | Zlacnene.sk, Kimbino.sk, Letakomat.sk, KdeJeAkcia.sk, Kompas Zliav, Kupino.sk, AkčnéLetáky.sk, Promotheus.sk |
| Měna senzorů | CZK (Kč) | EUR (€) |
| Výchozí značky | Pilsner Urquell, Kozel, Gambrinus | Zlatý Bažant, Šariš, Corgoň |
| Výchozí limit za 0,5 l | 15 Kč | 0,70 € |

- Pobočky z OpenStreetMap se berou **jen uvnitř hranic zvolené země** (Overpass
  `area["ISO3166-1"="CZ"/"SK"]`). U hranic se tak nenabídne obchod v sousední zemi.
- Když je sledovaný telefon nebo osoba mimo zvolenou zemi, vzdálenosti se počítají od domova HA.
- Nabídky v jiné měně (Kč na Slovensku, € v Česku) se zahodí.
- **Chcete obě země?** Přidejte integraci dvakrát, jednou pro Česko a jednou pro Slovensko.
  Každá bude mít vlastní senzory i kartu. Když bydlíte u hranic, nastavte u slovenské
  varianty dostatečnou **vzdálenost poboček** (až 50 km). Obchody se pak hledají na Slovensku
  v tomto okruhu od vašeho domova v ČR.
- Slovenské značky v seznamu: Zlatý Bažant, Šariš, Corgoň, Topvar, Smädný mních, Kelt, Steiger,
  Martiner, Urpiner, Popper (a samozřejmě české značky nebo vlastní).

## Zdroje akcí

| Zdroj | Jak se čte | Výchozí adresy |
|---|---|---|
| **Kupi.cz** | vlastní parser stránek kupi.cz + JSON-LD | `/slevy/pivo` (stránkování), `/sleva/pivo-<značka>`, `/hledej?f=<značka>` |
| **Kompas Slev** | obecný parser | `kompasslev.cz/produkty/pivo`, `kompasslev.cz/produkty/<značka>` |
| **AkcniCeny.cz** | obecný parser | vyhledávání `pivo` / `<značka>` |
| **Cenito** | obecný parser | vyhledávání `pivo` / `<značka>` |
| 🇸🇰 **Zlacnene.sk** | obecný parser | `/akciovy-tovar/napoje-alkoholicke/pivo/`, `/akciovy-tovar/znacka-<značka>/` |
| 🇸🇰 **Kimbino.sk** | obecný parser | `/produkty/pivo/`, `/produkty/<značka>/` |
| 🇸🇰 **Letakomat.sk** | obecný parser | `/hladat/?q=pivo`, `/hladat/?q=<značka>` |
| 🇸🇰 **KdeJeAkcia.sk** | obecný parser | `/kde-je-pivo-v-akcii`, `/kde-je-<značka>-v-akcii` |
| 🇸🇰 **Kompas Zliav** | obecný parser | `kompaszliav.sk/produkty/pivo`, `/produkty/<značka>` |
| 🇸🇰 **Kupino.sk** | obecný parser | `/akcia/pivo`, `/akcia/<značka>` |
| 🇸🇰 **AkčnéLetáky.sk** | obecný parser | `/akcie/Pivo`, `/akcie/<značka>` |
| 🇸🇰 **Promotheus.sk** | obecný parser | `promotheus.sk/pivo`, `promotheus.sk/<značka>` |
| **Vlastní URL** | obecný parser | libovolné stránky zadané v nastavení |

Zdroje zapínáte a vypínáte v nastavení integrace. **Obecný parser** zkouší postupně:
1. strukturovaná data schema.org (JSON-LD `Product` / `Offer` / `ItemList`),
2. JSON vložený do stránky (Next.js `__NEXT_DATA__` a jiný `application/json`),
3. heuristiku nad HTML: najde nejmenší blok stránky, ve kterém je cena (Kč, nebo € na Slovensku) a název řetězce,
   a z něj vezme název produktu, starou cenu, slevu, platnost a odkaz.

> ⚠️ Weby se při vývoji nedaly otevřít, takže parser nebyl vyzkoušený na jejich skutečném
> obsahu. Slovenské adresy a adresa Kompas Slev jsou ověřené přes vyhledávač. Adresy
> AkcniCeny.cz a Cenito jsou odhad. Když některý zdroj nic nevrací, podívejte se na atribut
> `sources` senzoru **Počet akcí**. Ukazuje pro každý zdroj počet akcí, funkční URL a chyby.
> Správnou adresu pak zadejte do **Vlastní URL**. Adresa, která vrátí 404, se týden nezkouší.

**Vlastní URL** (jedna na řádek) může obsahovat zástupné znaky:
- `{query}` = název značky (`Pilsner+Urquell`), při „všech pivech“ `pivo`
- `{slug}` = značka ve tvaru `pilsner-urquell`

```text
https://kompasslev.cz/produkty/pivo?store=kaufland
https://www.nejaky-web.cz/hledat?q={query}
```

## Co umí

| Funkce | Popis |
|---|---|
| Výběr značek | Výběr ze seznamu (Pilsner Urquell, Kozel, Gambrinus, Radegast, Staropramen, Budvar, Bernard, Svijany…), **vlastní značka** (napište ji a potvrďte Enterem, jde zadat i víc značek oddělených čárkou), nebo **„Všechna piva v akci“** |
| Čas kontroly | Denní kontrola v zadaný čas, volitelně navíc každých N hodin. Kdykoli ručně: tlačítko **Aktualizovat akce** nebo služba `akce_na_pivo.refresh` |
| Poloha | Domov HA, nebo entita `person` / `device_tracker` / `zone` (GPS telefonu). Když se posunete o víc než 2 km, nejbližší pobočky se přepočítají |
| TOP N | Počet zobrazených nejlevnějších nabídek volíte v nastavení (1–10, výchozí 5) |
| Mapa a adresa | U každé nabídky je nejbližší pobočka: adresa, vzdálenost, GPS, otevírací doba a odkazy na Mapy.com a navigaci |

### Další ukazatele, že je pivo opravdu levné

- **Cena za 0,5 l**: přepočet i u multipacků (`8 × 0,5 l`), plechovek 0,33 l a PET 1,5 l. Podle toho se standardně řadí.
- **Nejlevněji za posledních 120 dní**: integrace si ukládá historii cen a označí nabídku, která je na historickém minimu.
- **Levnější než průměr**: o kolik Kč/0,5 l je nabídka levnější než průměr všech akcí na stejnou značku.
- **Sleva ≥ 30 %** a odhad původní ceny.
- **Pod limitem**: nastavíte si cenu za 0,5 l a dostanete událost `akce_na_pivo_levne_pivo` a zapne se binární senzor.
- **Končí dnes / zítra**, **Platí od…** (připravované akce z nových letáků), **Jen s věrnostní kartou** (Lidl Plus, Clubcard, Můj Albert…), **Multipack**.
- Filtry: vynechat nealko, vynechat akce jen s kartou, zobrazit jen obchody s pobočkou v okolí (limit km).

## Instalace integrace

### HACS
1. HACS → Integrace → ⋮ → *Vlastní repozitáře* → `https://github.com/joshuaaaaa/HA-akce-na-pivo`, kategorie *Integrace*.
2. Nainstalujte **Akce na pivo** a restartujte Home Assistant.

### Ručně
Zkopírujte `custom_components/akce_na_pivo` do `/config/custom_components/` a restartujte HA.

Potom: **Nastavení → Zařízení a služby → Přidat integraci → Akce na pivo**.
Všechno jde později změnit přes **Konfigurovat**.

## Pivní karta

Samostatná karta `custom:pivni-karta` v souboru [`www/pivni-karta.js`](www/pivni-karta.js).
Na první pohled ukáže, **kam jít pro pivo**:

- nahoře „pěna“ s nadpisem a vlajkou země, pod ní pivní pozadí s bublinkami,
- velké **„Dnes jdi do: Kaufland“**, adresa, vzdálenost a otevírací doba,
- produkt, cena, cena za 0,5 l, přeškrtnutá původní cena a štítek se slevou,
- štítky jako „Nejlevněji za posledních 120 dní“ nebo „Končí dnes“,
- tlačítka **Navigovat**, **Mapa** a **Leták**,
- **přepínač značek** (Vše / Kozel / Pilsner Urquell…): po klepnutí na značku ukáže, kam jít pro ni,
- mapu s označeným obchodem a žebříček nejlevnějších akcí.

### Instalace (vložením do `www`)

1. Stáhněte [`www/pivni-karta.js`](www/pivni-karta.js) a uložte ho do Home Assistantu jako
   `/config/www/pivni-karta.js`. Složku `www` v případě potřeby vytvořte. Po jejím
   prvním vytvoření restartujte HA.
2. **Nastavení → Ovládací panely → ⋮ (vpravo nahoře) → Zdroje → Přidat zdroj**
   - URL: `/local/pivni-karta.js`
   - Typ zdroje: **JavaScript modul**
3. Obnovte prohlížeč (Ctrl+F5, v mobilní aplikaci vymažte mezipaměť frontendu).
4. Upravit ovládací panel → **Přidat kartu** → vyhledejte **Pivní karta**. Má grafický editor.
   Nebo použijte YAML:

```yaml
type: custom:pivni-karta
entity: sensor.akce_na_pivo_nejlevnejsi_pivo   # hlavní senzor integrace
title: Kam na pivo
brand: ""            # výchozí značka, např. "Kozel"; prázdné = všechny
count: 5             # počet akcí v žebříčku
show_brands: true    # přepínač značek
show_map: true       # mapa obchodu (OpenStreetMap)
map_height: 180
show_list: true      # žebříček nejlevnějších
bubbles: true        # animované bublinky (vypnou se i při „omezit pohyb“ v systému)
```

Po aktualizaci souboru změňte URL zdroje na `/local/pivni-karta.js?v=2`, aby prohlížeč
nenačítal starou verzi z mezipaměti.

> **HACS (custom repository):** HACS umí jako *Dashboard* (plugin) přidat jen repozitář,
> který obsahuje právě kartu. V jednom repozitáři nemůže být zároveň integrace a karta.
> Pokud chcete kartu instalovat přes HACS, založte samostatný repozitář
> (např. `pivni-karta`) se souborem `pivni-karta.js` v kořeni a souborem `hacs.json`:
> `{"name": "Pivní karta", "filename": "pivni-karta.js", "render_readme": true}`.
> Pak ho v HACS přidejte přes **⋮ → Vlastní repozitáře**, kategorie **Dashboard**.

## Karta (součást custom component)

Karta `custom:akce-na-pivo-card` je přibalená přímo v integraci
(`custom_components/akce_na_pivo/frontend/akce-na-pivo-card.js`). **Nic nekopírujete ani
nepřidáváte do zdrojů**: integrace ji sama zpřístupní na `/akce_na_pivo/akce-na-pivo-card.js`
a zaregistruje ji ve frontendu. Po instalaci a restartu stačí obnovit prohlížeč (Ctrl+F5)
a v ovládacím panelu přidat kartu **Akce na pivo**. Má i grafický editor.

Kdyby se karta v nabídce neobjevila (třeba bez `default_config`), přidejte zdroj ručně:
**Nastavení → Ovládací panely → ⋮ → Zdroje** → URL `/akce_na_pivo/akce-na-pivo-card.js`,
typ *JavaScript modul*.

```yaml
type: custom:akce-na-pivo-card
entity: sensor.akce_na_pivo_nejlevnejsi_pivo
title: 🍺 Nejlevnější pivo
count: 5            # kolik nabídek zobrazit (1–10)
sort: ""            # "" = podle integrace, nebo unit | price | distance
show_map: true
map_height: 240
show_images: true
show_address: true
show_flags: true
show_source: true   # štítek, ze kterého webu akce pochází
show_upcoming: false
```

Klepnutím na nabídku se na mapě zvýrazní obchod a objeví se odkazy **Mapy.com**,
**Navigovat** a **Leták**. Mapa používá Leaflet z CDN. Když se nenačte, karta
zobrazí vložený OpenStreetMap.

## Entity

| Entita | Stav | Poznámka |
|---|---|---|
| `sensor.*_nejlevnejsi_pivo` | cena za 0,5 l (nebo za balení) | atribut `offers` = TOP N, `upcoming`, `brands`, `location`; zdroj dat pro kartu |
| `sensor.*_nejlevnejsi_pivo_za_0_5_l` | Kč (€)/0,5 l | vhodné do grafu historie |
| `sensor.*_pivo_1` … `_pivo_N` | cena balení | mají `latitude`/`longitude`, takže je zobrazí i standardní karta Mapa |
| `sensor.*_<značka>` | cena | nejlevnější akce každé vybrané značky |
| `sensor.*_kam_pro_pivo` | **název obchodu**, např. `Kaufland` | kam jít pro celkově nejlevnější pivo; atributy `address`, `distance_km`, `navigate_url`, `product`, `price` a `summary` („Kaufland, Bělehradská 118, Praha (1,2 km): Kozel 11 0,5 l za 13,90 Kč“) |
| `sensor.*_kam_pro_<značka>` | **název obchodu** | kam jít pro konkrétní vybranou značku |
| `binary_sensor.*_levne_pivo_pod_limitem` | on/off | je v akci pivo pod limitem? |
| `button.*_aktualizovat_akce` | – | okamžitá aktualizace |
| `sensor.*_pocet_akci` | počet | diagnostika: stav každého zdroje (akce, funkční URL, chyby) |

### Příklad automatizace – upozornění do mobilu

```yaml
automation:
  - alias: Levné pivo
    trigger:
      - platform: event
        event_type: akce_na_pivo_levne_pivo
    action:
      - service: notify.mobile_app_telefon
        data:
          title: "🍺 {{ trigger.event.data.product }}"
          message: >
            {{ trigger.event.data.shop }} za {{ trigger.event.data.price }} {{ trigger.event.data.currency }}
            ({{ trigger.event.data.price_per_half_liter }} {{ trigger.event.data.currency }}/0,5 l),
            {{ trigger.event.data.address }} – {{ trigger.event.data.distance_km }} km,
            platí do {{ trigger.event.data.valid_to }}
```

### Příklad: každé ráno, kam jít na pivo

```yaml
automation:
  - alias: Kam pro pivo
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: notify.mobile_app_telefon
        data:
          title: "🍺 Dnes jdi do: {{ states('sensor.akce_na_pivo_kam_pro_pivo') }}"
          message: "{{ state_attr('sensor.akce_na_pivo_kam_pro_pivo', 'summary') }}"
          data:
            url: "{{ state_attr('sensor.akce_na_pivo_kam_pro_pivo', 'navigate_url') }}"
```

Nebo jednoduše v kartě Entity: `sensor.akce_na_pivo_kam_pro_pivo` ukáže název obchodu.

### Standardní karta Mapa

```yaml
type: map
entities:
  - sensor.akce_na_pivo_pivo_1
  - sensor.akce_na_pivo_pivo_2
  - sensor.akce_na_pivo_pivo_3
  - zone.home
```

## Poznámky

- Integrace stahuje veřejné stránky šetrně: pár stránek jednou denně, s pauzami mezi požadavky.
  Chyba jednoho zdroje neshodí ostatní. Když kupi.cz změní vzhled stránek, bude potřeba upravit
  `kupi.py`. Ostatní weby čte obecný parser `generic.py`.
- XML feed kupi.cz je určený pro obchodní partnery, ne pro veřejné použití, proto ho integrace nepoužívá.
- Kupi.cz uvádí akce za celý řetězec. Pobočka na mapě je **nejbližší prodejna daného řetězce**,
  konkrétní akce se tam ale může lišit (třeba hypermarket vs. supermarket).
- Pobočky z OpenStreetMap se ukládají do mezipaměti na 7 dní a obnoví se, když se změní poloha.

## Vývoj

```bash
pip install beautifulsoup4 pytest
pytest tests/test_kupi.py tests/test_generic.py   # parsery bez Home Assistantu
pip install pytest-homeassistant-custom-component
pytest tests                         # včetně testu integrace
```
