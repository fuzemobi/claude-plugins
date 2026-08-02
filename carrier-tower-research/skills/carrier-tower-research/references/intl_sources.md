# International Regulatory Sources

Non-US carriers (MCC other than 310-316) require per-country regulator lookups. Coverage quality varies wildly — some countries publish full structure registries with coords, others only publish license holdings with no location data.

---

## Coverage tier by country

### Tier 1 — full public structure registry with coords

These regulators publish tower/site data with lat/lon suitable for direct master population.

| Country | MCC | Regulator | Registry URL |
|---|---|---|---|
| UK | 234, 235 | Ofcom | https://www.ofcom.org.uk/manage-your-licence/radiocommunication-licences/mobile-wireless-broadband |
| Germany | 262 | BNetzA | https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/start.html |
| France | 208 | ANFR | https://data.anfr.fr/ (Cartoradio) |
| Australia | 505 | ACMA | https://web.acma.gov.au/rrl/ |
| Canada | 302 | ISED | https://sms-sgs.ic.gc.ca/ |
| Ireland | 272 | ComReg | https://www.comreg.ie/licensing/operator-licensing/ |
| Netherlands | 204 | Agentschap Telecom | https://www.agentschaptelecom.nl/onderwerpen/antenneregister |
| New Zealand | 530 | RSM | https://rrf.rsm.govt.nz/smart-web/smart/page/-smart/Home.wdk |
| Switzerland | 228 | BAKOM | https://www.funksender.ch/ |

### Tier 2 — partial public data (licensees listed, coords sparse)

| Country | MCC | Regulator | Notes |
|---|---|---|---|
| Spain | 214 | SETSI | License holders public, tower coords require FOIA |
| Italy | 222 | MISE | Licensees public, sites not |
| Brazil | 724 | ANATEL | Mosaico system has tower data but requires account |
| Japan | 440, 441 | MIC | Limited public data; NTT/KDDI/SoftBank publish separately |
| South Korea | 450 | KCC | Very limited public tower data |
| Mexico | 334 | IFT | Tower data via SNI portal, sometimes stale |

### Tier 3 — regulator-only, minimal public tower data

Most developing markets. Rely on OpenCelliD/CellMapper for these.

---

## Quick recipes

### Ofcom UK (Tier 1)

1. Go to https://www.ofcom.org.uk/manage-your-licence/radiocommunication-licences/mobile-wireless-broadband
2. Download the WTR (Wireless Telegraphy Register) — published quarterly as CSV.
3. Filter by licensee name (e.g., `Hutchison 3G UK` for 234-20 Three).
4. Fields: `licensee_name`, `station_latitude`, `station_longitude`, `station_height`, `station_azimuth`, `frequency`, `power`.

Map to master:
- `licensee_name` → `carrier_name`
- `station_latitude/longitude` → `latitude/longitude` (already decimal degrees, no DMS conversion)
- `station_height` → `height_agl_m` (already meters, not feet)

Source tag: `INTL_REGULATOR` with sub-tag in notes: `OFCOM_WTR`.

### BNetzA DE (Tier 1)

1. Go to https://emf3.bundesnetzagentur.de/karte/
2. Interactive map of every registered EMF-relevant site (≥ 10W EIRP).
3. Export via the data portal: https://www.bundesnetzagentur.de/cln_134/DE/Service-Funktionen/OpenData/Datensaetze/start.html
4. File: `Standortdatenbank` — site database with lat/lon, operator, antenna details.

Fields: `Standort-ID`, `Laengengrad`, `Breitengrad`, `Standortbescheinigung-Ausstellungsdatum`, operator antenna data.

### ACMA AU (Tier 1)

1. https://web.acma.gov.au/rrl/site_search.main_page
2. Register of Radiocommunications Licences — searchable by licensee, site, or frequency.
3. Bulk extracts: https://www.acma.gov.au/register-radiocommunications-licences-rrl

Each site has `site_id`, lat/lon, address, and per-license details.

### Cartoradio FR (Tier 1)

1. https://data.anfr.fr/
2. Cartoradio provides every radio emitter site in France with coords.
3. Dataset: `Observatoire des antennes-relais`.

### ISED Canada (Tier 1)

1. https://sms-sgs.ic.gc.ca/
2. Spectrum Management System — public search by licensee.
3. Radio site data also available via https://www.ic.gc.ca/eic/site/smt-gst.nsf/eng/sf08942.html (Spectrum Direct).

---

## When in doubt: regulator web search pattern

For any country:
```
"<country> telecom regulator" OR "<country> spectrum registry" OR "<country> mobile license register"
```

Then look for:
- Downloadable data (CSV, XML, API)
- Interactive map with export
- FOIA/ATI pathway if nothing public

---

## Fallback: ITU BR IFIC

The ITU-BR International Frequency Information Circular lists notified frequencies but not towers. Useful only to confirm a carrier holds spectrum in a given band.

```
https://www.itu.int/pub/R-SP-BR.IFIC
```

---

## Fallback: TowerXchange / commercial databases

Commercial tower infrastructure data is available from:
- TowerXchange (market reports, not individual coords)
- Ookla / Opensignal (coverage polygons, not tower coords)
- Tutela / Rootmetrics (drive-test, no public coords)

None of these are primary sources; use only as sanity check against the merged master.

---

## Mapping to the tower master CSV

International regulator fields map mostly the same as US, with these differences:

| Master column | International source | Notes |
|---|---|---|
| `height_agl_ft` | convert from meters if needed | `ft = m × 3.28084` |
| `height_agl_m` | native for most Tier-1 regulators | Populate both when possible |
| `asr_number` | N/A | leave blank |
| `uls_call_sign` | N/A | leave blank |
| `frn` | N/A | leave blank or use regulator's operator ID |
| `oe_study_number` | N/A | leave blank |
| `source` | `INTL_REGULATOR` | |
| `source_url` | specific registry page per row | |
| `notes` | regulator short-tag (`OFCOM_WTR`, `BNETZA_STANDORT`, `ACMA_RRL`, etc.) | |

---

## Crowdsourced remains the fallback

For Tier-2 and Tier-3 countries, `references/crowdsourced.md` (OpenCelliD + CellMapper) is often the only usable source. For those, every row gets `source=OPENCELLID` or `source=CELLMAPPER` and is treated as observational rather than authoritative.
