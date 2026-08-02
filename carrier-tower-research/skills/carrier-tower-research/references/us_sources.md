# US Regulatory Sources

Authoritative tower data for any US carrier (MCC 310, 311, 312, 313, 316) comes from these five sources in this order of preference. Always start with ULS for operational coords; fall back as needed.

> **Order of attack:** (1) a **local ULS bulk cache** (§1 below) — download once, query with grep/awk, never page into an LLM context. (2) If you must hit a live FCC/CellMapper portal and it **times out** (ULS, ASR, CellMapper are JavaScript-rendered and fail under plain HTTP fetches), drive it with a **headless browser**. (3) If the browser path is also blocked (login wall, CAPTCHA), **ask the user to help** rather than silently falling back to a low-trust centroid.

---

## 1. FCC ULS (Universal Licensing System) — HIGHEST TRUST

Every licensed transmitter site has exact lat/lon in ULS. This is the primary source for operational tower coordinates. Most rural/tribal carriers don't file every structure in ASR (height thresholds), but every transmitter site is in ULS.

### Web search
```
https://wireless2.fcc.gov/UlsApp/UlsSearch/searchLicense.jsp
```
Fields:
- **Licensee Name:** full legal name (not trade name)
- **Status:** `Active`
- **State:** optional filter
- **Service:** leave blank to get all radio services

### Bulk pull (preferred)
```
https://www.fcc.gov/uls/transactions/daily-weekly
```

Download these zips depending on the carrier's licensed services:
- `l_cell.zip` — Cellular Radiotelephone Service (Part 22)
- `l_LMpriv.zip` — Private Land Mobile (PLMR)
- `l_paging.zip` — Paging
- `l_micro.zip` — Microwave (point-to-point backhaul)
- `l_market.zip` — Market-based (PCS, AWS, 700 MHz, H-block, WCS, etc.) — **this is where modern LTE/5G licenses live**

### Key tables and join

| File | Contents | Key field |
|---|---|---|
| `HD.dat` | License header (call sign, licensee name, FRN, status) | `unique_system_id` |
| `EN.dat` | Entity/licensee details (entity name, FRN, contact) | `unique_system_id` |
| `LO.dat` | Location records (lat, lon, structure type, height AGL) | `unique_system_id`, `location_number` |
| `FR.dat` | Frequency records (per-site per-frequency) | `unique_system_id`, `location_number`, `frequency_number` |
| `AN.dat` | Antenna records (azimuth, downtilt, gain, height) | `unique_system_id`, `location_number`, `antenna_number` |

**Join recipe:**
```
HD.unique_system_id = EN.unique_system_id
HD.unique_system_id = LO.unique_system_id
LO.(unique_system_id, location_number) = FR.(unique_system_id, location_number)
LO.(unique_system_id, location_number) = AN.(unique_system_id, location_number, location_number)
```

**Filter:**
```
EN.entity_name LIKE '%<CARRIER LEGAL NAME>%'
OR EN.frn = '<FRN>'
```

Output columns that matter for the tower master:
- `HD.call_sign` → `uls_call_sign`
- `EN.frn` → `frn`
- `LO.lat_degrees`, `LO.lat_minutes`, `LO.lat_seconds`, `LO.lat_direction` → `latitude` (convert DMS → decimal)
- `LO.long_degrees`, `LO.long_minutes`, `LO.long_seconds`, `LO.long_direction` → `longitude`
- `LO.structure_type`, `LO.overall_height_of_structure_AGL` → `structure_type`, `height_agl_ft`
- `LO.location_city`, `LO.location_state` → `city`, `state`
- `AN.azimuth`, `AN.height_to_tip`, `AN.mech_beam_tilt` → per-sector attributes

### Gotchas

- ULS uses **DMS** (degrees-minutes-seconds), not decimal. Convert: `decimal = deg + min/60 + sec/3600`, negate for W longitude and S latitude.
- Some carriers file under a holding-company entity name. If the carrier name search returns nothing, try the FRN. If you don't know the FRN, check ECFS or BDC (providers report their FRN).
- `status='A'` = active. Filter out canceled/expired.

### Local ULS cache — BUILD ONE, THEN QUERY IT FIRST

Download the bulk zips once and keep them unzipped locally, e.g.:
```
./uls_cache/{l_cell,l_market,l_micro}/
```
`l_cell` = Part 22 Cellular (where many rural/tribal cell licenses live), `l_market` = PCS/AWS/700/etc., `l_micro` = backhaul. **Query the cache directly rather than re-hitting the FCC website.** These `.dat` files are huge (some >100 MB); **never page them into an LLM context — always `grep`/`awk`.**

**Step 1 — find the licensee (EN.dat): entity_name=col 8, FRN=col 23, call_sign=col 5, USI=col 2**
```bash
cd .../uls_cache/l_cell
grep -iE 'CARRIER LEGAL NAME|tradename|holdingco' EN.dat \
  | awk -F'|' '{print $2"|callsign="$5"|name="$8"|city="$17"|st="$18"|frn="$23}' | sort -u
```
Repeat in `l_market` if the carrier has LTE/5G licenses (cellular-only carriers live in `l_cell`).

**Step 2 — pull that carrier's cell-site coords (LO.dat). DMS at cols 20–27; addr=col 12, city=col 13, county=col 14, state=col 15**
```bash
grep -E '\|(CALLSIGN1|CALLSIGN2|CALLSIGN3)\|' LO.dat   # call signs from Step 1 | awk -F'|' '
{ lat=$20+$21/60+$22/3600; if($23=="S")lat=-lat;
  lon=$24+$25/60+$26/3600; if($27=="W")lon=-lon;
  printf "%s|loc%s|addr=%s|city=%s|county=%s|%s|%.5f|%.5f\n",$5,$9,$12,$13,$14,$15,lat,lon }' | sort
```
LO.dat gives BOTH the structure lat/lon AND a real address (street where filed, else village). Multi-sector towns often register as one structure (co-located sectors → shared coord); dual sites (e.g. "Springfield" + "Springfield #2", or a named utility-building site in the same town) register as separate locations — match each logical cell code to its own location, don't collapse them.

This local-cache path is **FCC_ULS trust tier (highest)** — `enrichment_source=fcc_uls`, confidence `high`, accuracy ~100 m. Always prefer it over centroids.

### Filling a valid address (reverse geocode)

LO.dat's address is often just the village name. To produce a postal address (with ZIP), reverse-geocode the FCC coord via Nominatim — coord stays FCC-authoritative, address is enriched:
```bash
curl -s "https://nominatim.openstreetmap.org/reverse?lat=<LAT>&lon=<LON>&format=json&addressdetails=1" \
  -H "User-Agent: tower-research/1.0 (you@example.com)"
# take address.postcode; compose: "<FCC structure addr>, <city>, <state> <zip>"
```
Respect the 1 req/sec policy; dedupe identical coords. Always sanity-gate the coord against the state bounding box before trusting either source.

---

## 2. FCC ASR (Antenna Structure Registration) — TALL STRUCTURES

ASR covers structures requiring FAA notification, generally >200 ft AGL or near airports. Won't catch every monopole, but the tall backhaul and village sites will be here with owner-attested coords.

### Web search
```
https://wireless2.fcc.gov/UlsApp/AsrSearch/asrAdvancedSearch.jsp
```
Fields:
- **Entity Name:** `<CARRIER LEGAL NAME>`
- **State:** the carrier's service territory
- **Status:** `Constructed`

Each result returns a registration number linked to `https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey=<regKey>`.

### Bulk pull
```
https://www.fcc.gov/uls/transactions/daily-weekly
```
Download `r_tower.zip`. Filter:
- `entity_name LIKE '%<CARRIER LEGAL NAME>%'`
- `state_code = '<ST>'`
- `status_code = 'C'` (constructed)

Maps to master:
- `registration_number` → `asr_number`
- `lat_degrees/minutes/seconds/direction` → `latitude` (DMS, same as ULS)
- `long_degrees/minutes/seconds/direction` → `longitude`
- `overall_height_above_ground` → `height_agl_ft`
- `structure_type` → `structure_type`

### Cross-check

A tall site should appear in BOTH ULS (as a licensed transmitter location) and ASR (as a registered structure). Mismatched coords between the two usually mean the ULS record is the operational antenna and the ASR is the physical tower — use ULS for the pin.

---

## 3. FAA OE/AAA — RECENT/PLANNED SITES

Catches sites built after the last ASR refresh or still in construction.

```
https://oeaaa.faa.gov/oeaaa/external/gisTools/gisAction.jsp?action=showSearchToolForm
```

Search by:
- **Sponsor:** `<CARRIER LEGAL NAME>`
- **State:** service territory
- **Study date range:** last 2 years for recent filings

Every filing has an OE study number (e.g., `2024-ANM-1234-OE`). Use this in the master's `oe_study_number` column.

---

## 4. FCC BDC (Broadband Data Collection) — COVERAGE VALIDATION

Not tower coords — hexagon-level coverage polygons (H3 resolution 8). But these validate the merged tower map: if you have 10 towers but BDC shows coverage across an area your towers can't reach, you're missing sites.

### Interactive
```
https://broadbandmap.fcc.gov
```

### Bulk
```
https://broadbandmap.fcc.gov/data-download/nationwide-data
```
Pick state, mobile broadband, and filter by `provider_id` once known. Carriers report their Provider ID in consumer broadband labels and BDC filings.

---

## 5. FCC ECFS — CARRIER-ATTESTED SITE COMMITMENTS

For USF/high-cost/tribal carriers (Alaska Plan, Connect America Fund, RDOF), the carrier's own filings name every site they committed to. This is the best source for "what sites exist" independent of whether the license shows up yet.

### Search
```
https://www.fcc.gov/ecfs/search/search-filings
```

Relevant dockets:
- **16-271** — Alaska Plan
- **10-90** — Connect America Fund / High-Cost
- **19-126** — RDOF (Rural Digital Opportunity Fund)
- **09-51** — National Broadband Plan
- **20-32** — 5G Fund for Rural America

Filter by filer = carrier legal name.

Pull PDFs, extract the commitment table (typically named sites with population coverage numbers and backhaul type). These become `source=CARRIER_COMMITMENT` rows with coords at the village centroid unless the filing includes coords.

---

## 6. USAC Form 481 — annual high-cost program data

```
https://www.usac.org/high-cost/resources/forms/form-481/
```

Tab `5013(a-c)` on the Non-Confidential Form 481 has the per-year site commitments. Less detail than ECFS filings but easier to tabulate.

---

## Mapping to the tower master CSV

| Master column | ULS source | ASR source | Notes |
|---|---|---|---|
| `carrier_name` | `EN.entity_name` | `entity_name` | Normalize to legal name |
| `tadig` | derived | derived | From MCC/MNC lookup |
| `mcc`, `mnc` | derived | derived | From TADIG or carrier table |
| `site_id` | synthesize | synthesize | `<TADIG>-<CITY3>-<NN>` |
| `site_name` | `LO.location_address` or synthesize | `structure_address` | Use city/landmark |
| `community`, `city`, `state` | `LO.location_city`, `LO.location_state` | `city`, `state_code` | |
| `latitude`, `longitude` | `LO.lat_*`, `LO.long_*` (DMS → decimal) | same | ULS wins on conflict |
| `height_agl_ft` | `LO.overall_height_of_structure_AGL` | `overall_height_above_ground` | |
| `structure_type` | `LO.structure_type` | `structure_type` | |
| `asr_number` | — | `registration_number` | |
| `uls_call_sign` | `HD.call_sign` | — | |
| `frn` | `EN.frn` | — | |
| `band` | derived from `FR.frequency_assigned` | — | Map frequency → LTE band |
| `technology` | derived from Service code | — | `LTE`, `5G-NR`, `GSM`, `UMTS` |
| `source` | `FCC_ULS` | `FCC_ASR` | |
| `source_url` | License detail page | ASR registration page | |
| `last_verified` | ULS dump date | ASR dump date | ISO-8601 |

---

## Frequency-to-band quick reference (for `band` column)

| FR.frequency_assigned (MHz) | Band | Notes |
|---|---|---|
| 699-798 | B12, B13, B14, B17, B29, B85 | 700 MHz |
| 824-894 | B5, B18, B19, B26 | Cellular |
| 1850-1990 | B2, B25 | PCS |
| 1710-1755 / 2110-2155 | B4, B66 | AWS-1/3 |
| 2496-2690 | B41 | BRS/EBS |
| 3550-3700 | B48, n48 | CBRS |
| 3700-3980 | n77, n78 | C-band (5G) |
| 37000-40000 (37-40 GHz) | n260 | mmWave |

---

## Common entity-name variants

Some carriers file under multiple entities. When the primary name returns nothing, try:

- `<Carrier Name>` (trade name)
- `<Carrier Name>, Inc.`
- `<Carrier Name> Cooperative` / `Cooperative, Inc.`
- `<Holding Company>` (parent)
- `<Carrier Name> Wireless` or `<Carrier Name> Cellular` (spun-out wireless subsidiary)

Always search by FRN if you have it — FRN is unique and never varies across filings.
