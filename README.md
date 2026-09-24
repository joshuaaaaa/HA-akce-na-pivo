# 🍺 Akce na pivo – Home Assistant

Integrace pro Home Assistant, která každý den (nebo v čase, který si nastavíte) zjistí,
**kde je nejlevnější pivo v akci**, najde **nejbližší pobočku** daného obchodu k vašemu
domovu nebo k poloze vašeho telefonu a ukáže ji **na mapě**. Senzor **Kam pro pivo**
rovnou řekne, do kterého obchodu jít.

Ve složce [`www/`](www) jsou dvě samostatné Lovelace karty. Do Home Assistantu je
přidáte ručně (viz [Lovelace karty](#lovelace-karty-složka-www)):
- 🍺 **[Pivní karta](#-pivní-karta)** (`custom:pivni-karta`): karta na pivním pozadí
  s pěnou a bublinkami, „Dnes jdi do: …“, přepínač značek a obalu,
- 🗺️ **[Seznam akcí s mapou](#️-seznam-akcí-s-mapou)** (`custom:akce-na-pivo-card`):
  žebříček akcí a mapa se všemi obchody.

- **Česko 🇨🇿 nebo Slovensko 🇸🇰**: zemi vyberete při přidání integrace.
- **Čeština, slovenčina, nebo angličtina 🇨🇿 🇸🇰 🇬🇧**: integrace i obě karty jsou přeložené,
  viz [Jazyk](#jazyk--jazyk--language).
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

## Jazyk / Jazyk / Language

- **Průvodce nastavením, názvy entit a služby** jsou česky, slovensky i anglicky
  (`translations/cs.json`, `sk.json`, `en.json`). Home Assistant je zobrazí podle jazyka
  v profilu uživatele, u slovenštiny tedy např. „Kam po pivo“ nebo „Najlacnejšie pivo“.
- **Jazyk textů v senzorech** vyberete hned v prvním kroku přidání integrace (a později
  v *Konfigurovat*): **Automaticky** (podle jazyka HA), **Čeština**, **Slovenčina**, nebo **English**.
  Týká se štítků akcí („Zľava 30 %“, „Končí zajtra“…), stavu „Není v akci“ / „Nie je v akcii“ /
  „Not on sale“ a shrnutí v senzorech *Kam pro pivo*.
- **Karty** se přizpůsobí samy: jazyk vezmou z integrace, případně z jazyka HA. V editoru
  karty ho jde nastavit i ručně (`language: sk`).

Slovenský překlad vychází z forku [FARKIr/HA-akce-na-pivo](https://github.com/FARKIr/HA-akce-na-pivo). Díky!

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
| Sklo, nebo plech | Vyberete obal: **🍾 sklo**, **🥫 plech**, **🧴 PET** (libovolná kombinace). Obal se pozná z názvu akce („plech“, „plechovka“, „lahev“, „sklo“, „fľaša“, „PET“…), pivo od 1 l se bere jako PET. Letáky obal často neuvádějí, proto volba **„Zahrnout akce, u kterých obal nejde poznat“** (výchozí zapnuto). Když ji vypnete, uvidíte jen akce s jistě uvedeným obalem. |
| 10°, 11°, nebo 12° | Vyberete **stupňovitost**: 10° (desítka), 11° (jedenáctka), 12° (dvanáctka) a/nebo **ostatní** (výčepní 7–9°, speciály 13° a víc). Stupeň se pozná z názvu akce („Kozel 11“, „12°“, slovenské „12%“, „desítka“, „výčepní“). U známých piv bez čísla v názvu se doplní (Pilsner Urquell = 12°, Gambrinus Originál = 10°, Radegast Rázná = 10°…). Volba **„Zahrnout akce, u kterých stupeň nejde poznat“** (výchozí zapnuto) rozhodne, co s ostatními akcemi. |
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
- Filtry: stupňovitost (10° / 11° / 12° / ostatní), obal (sklo / plech / PET), vynechat nealko, vynechat akce jen s kartou, zobrazit jen obchody s pobočkou v okolí (limit km).

## Instalace integrace

### HACS
1. HACS → Integrace → ⋮ → *Vlastní repozitáře* → `https://github.com/joshuaaaaa/HA-akce-na-pivo`, kategorie *Integrace*.
2. Nainstalujte **Akce na pivo** a restartujte Home Assistant.

### Ručně
Zkopírujte `custom_components/akce_na_pivo` do `/config/custom_components/` a restartujte HA.

Potom: **Nastavení → Zařízení a služby → Přidat integraci → Akce na pivo**.
Všechno jde později změnit přes **Konfigurovat**.

Integrace vytvoří senzory. Karty do ovládacího panelu se instalují zvlášť, viz
[Lovelace karty](#lovelace-karty-složka-www).

## Lovelace karty (složka `www`)

Obě karty jsou samostatné soubory ve složce [`www/`](www). Integrace je sama nenačítá, přidáte
je ručně. Stejný postup platí pro obě:

1. Stáhněte soubor karty a uložte ho do Home Assistantu do složky `/config/www/`:
   - [`www/pivni-karta.js`](www/pivni-karta.js) → `/config/www/pivni-karta.js`
   - [`www/akce-na-pivo-card.js`](www/akce-na-pivo-card.js) → `/config/www/akce-na-pivo-card.js`

   Soubor nahrajete třeba doplňkem *File editor* nebo *Samba share*. Když složka `www`
   ještě neexistuje, vytvořte ji a restartujte HA, jinak se soubory na adrese `/local/`
   nezobrazí.
2. **Nastavení → Ovládací panely → ⋮ (vpravo nahoře) → Zdroje → Přidat zdroj**
   (zdroje se zobrazí jen se zapnutým *Rozšířeným režimem* v profilu uživatele):
   - URL: `/local/pivni-karta.js` nebo `/local/akce-na-pivo-card.js`
   - Typ zdroje: **JavaScript modul**
3. Obnovte prohlížeč (Ctrl+F5; v mobilní aplikaci *Nastavení → Companion app → Ladění →
   Obnovit mezipaměť frontendu*).
4. Upravit ovládací panel → **Přidat kartu** → vyhledejte **Pivní karta** nebo **Akce na pivo**.
   Obě karty mají grafický editor.

**Aktualizace karty:** přepište soubor v `/config/www/` a u zdroje zvyšte číslo verze v URL,
např. `/local/pivni-karta.js?v=4`, aby prohlížeč nenačítal starou verzi z mezipaměti.

> **HACS (custom repository):** HACS umí jako *Dashboard* (plugin) přidat jen repozitář,
> který obsahuje právě kartu. V jednom repozitáři nemůže být zároveň integrace a karta.
> Pokud chcete kartu instalovat přes HACS, založte samostatný repozitář s daným `.js`
> souborem v kořeni a souborem `hacs.json`, např.
> `{"name": "Pivní karta", "filename": "pivni-karta.js", "render_readme": true}`.
> Pak ho v HACS přidejte přes **⋮ → Vlastní repozitáře**, kategorie **Dashboard**.

### 🍺 Pivní karta

`custom:pivni-karta` ukáže na první pohled, **kam jít pro pivo**:

- nahoře „pěna“ s nadpisem a vlajkou země, pod ní pivní pozadí s bublinkami,
- velké **„Dnes jdi do: Kaufland“**, adresa, vzdálenost a otevírací doba,
- produkt, cena, cena za 0,5 l, přeškrtnutá původní cena a štítek se slevou,
- štítky jako „Nejlevněji za posledních 120 dní“ nebo „Končí dnes“,
- tlačítka **Navigovat**, **Mapa** a **Leták**,
- **přepínač značek** (Vše / Kozel / Pilsner Urquell…): po klepnutí na značku ukáže, kam jít pro ni.
  Při více než 6 značkách se místo tlačítek zobrazí rozbalovací seznam.
- **klepnutí na akci v žebříčku** ji zobrazí nahoře (obchod, adresa, navigace).
  Vybrané značky, na které teď akce není, jsou přeškrtnuté a karta u nich napíše **„teď není v akci“**.
  Ostatní značky se zobrazují normálně.
- **přepínač obalu** (Každý obal / 🍾 Sklo / 🥫 Plech / 🧴 PET): třeba „kam pro Kozla v plechu“,
- **přepínač stupně** (Každý stupeň / 10° / 11° / 12°): třeba „kam pro dvanáctku“,
- mapu s označeným obchodem a žebříček nejlevnějších akcí.

```yaml
type: custom:pivni-karta
entity: sensor.akce_na_pivo_nejlevnejsi_pivo   # hlavní senzor integrace
title: Kam na pivo
brand: ""            # výchozí značka, např. "Kozel"; prázdné = všechny
count: 5             # počet akcí v žebříčku
show_brands: true    # přepínač značek
degree: ""           # výchozí stupeň v kartě: "10" | "11" | "12" | other, prázdné = každý
show_degrees: true   # přepínač stupně 10° / 11° / 12°
packaging: ""        # výchozí obal v kartě: glass | can | pet, prázdné = každý
show_packaging: true # přepínač obalu 🍾 Sklo / 🥫 Plech / 🧴 PET
show_map: true       # mapa obchodu (OpenStreetMap)
map_height: 180
show_list: true      # žebříček nejlevnějších
bubbles: true        # animované bublinky (vypnou se i při „omezit pohyb“ v systému)
language: ""         # "" = podle integrace / HA, nebo cs | sk | en
```

### 🗺️ Seznam akcí s mapou

`custom:akce-na-pivo-card` zobrazí žebříček nejlevnějších akcí a nad ním **mapu se všemi
obchody** (očíslované špendlíky podle pořadí) a vaší polohou 🏠.

- Klepnutím na nabídku nebo na špendlík se obchod na mapě přiblíží a zvýrazní. Objeví se
  odkazy **Mapy.com**, **Navigovat** a **Leták**.
- Mapou jde posouvat tažením. Tlačítka **+ / −** mění přiblížení, **⤢** ukáže všechny obchody.
- Mapa se kreslí přímo z dlaždic, bez externích knihoven. Výchozí podklad je **CARTO Voyager**
  (data OpenStreetMap), v tmavém motivu HA **CARTO Dark**. Přímé dlaždice z
  `tile.openstreetmap.org` HA blokuje hláškou „Access blocked“, protože neposílá hlavičku
  Referer. Proto se nepoužívají, pokud je výslovně nenastavíte (`map_style: osm`).

```yaml
type: custom:akce-na-pivo-card
entity: sensor.akce_na_pivo_nejlevnejsi_pivo
title: 🍺 Nejlevnější pivo
count: 5            # kolik nabídek zobrazit (1–10)
sort: ""            # "" = podle integrace, nebo unit | price | distance
show_map: true
map_height: 240
map_style: auto     # auto | carto | carto_dark | osm
show_images: true
show_address: true
show_flags: true
show_source: true   # štítek, ze kterého webu akce pochází
language: ""        # "" = podle integrace / HA, nebo cs | sk | en
show_upcoming: false
```

> Starší verze integrace kartu `akce-na-pivo-card` načítaly samy z adresy
> `/akce_na_pivo/akce-na-pivo-card.js`. Tato adresa už neexistuje. Pokud jste ji přidali jako
> zdroj, smažte ho a přidejte `/local/akce-na-pivo-card.js`.

## Entity

| Entita | Stav | Poznámka |
|---|---|---|
| `sensor.*_nejlevnejsi_pivo` | cena za 0,5 l (nebo za balení) | atribut `offers` = TOP N, `upcoming`, `brands`, `location`; zdroj dat pro kartu |
| `sensor.*_nejlevnejsi_pivo_za_0_5_l` | Kč (€)/0,5 l | vhodné do grafu historie |
| `sensor.*_pivo_1` … `_pivo_N` | cena balení | mají `latitude`/`longitude`, takže je zobrazí i standardní karta Mapa |
| `sensor.*_<značka>` | cena | nejlevnější akce každé vybrané značky; bez akce je stav „neznámý“ a atribut `status: Není v akci` |
| `sensor.*_kam_pro_pivo` | **název obchodu**, např. `Kaufland` | kam jít pro celkově nejlevnější pivo; atributy `address`, `distance_km`, `navigate_url`, `product`, `price` a `summary` („Kaufland, Bělehradská 118, Praha (1,2 km): Kozel 11 0,5 l za 13,90 Kč“) |
| `sensor.*_kam_pro_<značka>` | **název obchodu**, nebo **`Není v akci`** | kam jít pro konkrétní vybranou značku; atribut `on_sale` (true/false) |
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

## Řešení potíží

**Senzory ukazují „Neznámé“ (Unknown).** Akce se stáhly, ale žádná neodpovídá nastavení.
Otevřete **Nastavení → Zařízení a služby → Akce na pivo → senzor Počet akcí → Atributy**:

- `filter.downloaded`: kolik akcí se celkem stáhlo,
- `filter.brand_mismatch` / `expired` / `loyalty_excluded` / `packaging_excluded` / `degree_excluded` / …: kolik akcí se vyřadilo a proč,
- `filter.sample_products`: ukázka stažených názvů (produkt | obchod | cena | zdroj). Z ní je vidět,
  jestli web vrací správná data,
- `sources.<zdroj>.errors`: chyby jednotlivých webů, třeba `HTTP 403`, „ochrana proti robotům“
  nebo „parser na stránce nenašel žádnou akci“.

Stejné shrnutí se zapíše i do logu jako varování „Staženo N akcí, ale žádná neodpovídá nastavení“.
Když chcete nahlásit chybu, pošlete tyto atributy.

**Na mapě je „Access blocked – App is not following the tile usage policy…“.** Máte starou
verzi karty `akce-na-pivo-card.js` (s knihovnou Leaflet a dlaždicemi OpenStreetMap). Nahraďte
soubor v `/config/www/` novou verzí, zvyšte verzi v URL zdroje a obnovte prohlížeč (Ctrl+F5).

**„OpenStreetMap (Overpass) nedostupné“.** Veřejné servery Overpass bývají přetížené.
Integrace zkusí tři servery a nejdřív přesný dotaz omezený na území státu. Když neuspěje,
použije rychlejší dotaz jen podle okruhu. Pokud selžou všechny, zkusí to znovu za 30 minut.
Akce se mezitím zobrazují dál, jen bez adresy a vzdálenosti.

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
