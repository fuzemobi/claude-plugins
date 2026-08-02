---
name: carrier-tower-research
description: Build authoritative tower/cell-site master lists for any mobile carrier given an MCC/MNC pair, TADIG code, or carrier name. Use whenever the user provides an MCC/MNC, TADIG, or carrier name and asks to find, research, build, populate, map, or enrich towers, cell sites, cell IDs, LAC/CI, eNB, sectors, or CGI data. Triggers on "tower list for <carrier>", "cell sites for 310-xxx", "who owns this tower", "build me a tower master", "tower coordinates for <operator>". Covers US sources (FCC ULS/ASR/OE-AAA/BDC/ECFS) and international regulators, plus crowdsourced observations (CellMapper, OpenCelliD), and outputs a provenance-tagged CSV ready to join against CDR/TAP location data.
---

# Carrier Tower Research

Build tower/cell-site master data for any mobile carrier from authoritative regulatory sources plus crowdsourced RF observations, merged in explicit trust order, with per-row provenance. The end goal is usually a working `(mcc, mnc, lac, ci)` → site join for CDR/TAP billing or coverage analysis.

## When this fires

The user will typically give one or more of:
- **MCC/MNC** — e.g., `310-410`, `234 20`
- **TADIG** — the 5-char GSMA roaming code, e.g., `USACG`, `GBRHU`
- **Carrier name** — trade name or legal entity
- **Region/country** — e.g., "all 310 carriers in Alaska"

The ask will be some flavor of: *find the towers*, *build a tower list*, *get the cell sites*, *map LAC/CI for X*, *who owns tower X*. If MCC/MNC + "tower" are in the same sentence, use this skill.

## The pipeline, in one paragraph

Authoritative coordinates come from government regulators (in the US: FCC ULS for licensed transmitters, FCC ASR for registered structures, FAA OE/AAA for recent obstruction filings). Coverage polygons come from FCC BDC. Named site commitments come from ECFS dockets (Alaska Plan, RDOF, etc.). LAC/CI/eNB observations come from crowdsourced platforms (CellMapper, OpenCelliD). Merge these in trust order (regulator > commitment > crowdsourced > centroid placeholder) into a single CSV where every row carries its source.

## Step-by-step workflow

### 1. Identify the carrier

Confirm MCC/MNC ↔ TADIG ↔ legal-entity-name. If the user gives only one, resolve the others via web search (`"MCC MNC <code>"`) cross-checked against GSMA data or mcc-mnc.net.

The **legal entity name** matters because that's what ULS/ASR search by — not the trade name. A brand name often searches poorly; the registered cooperative/LLC name hits every record. `references/us_sources.md` lists common entity-name variants to try.

### 2. Decide country/region path

- **US carriers (MCC 310–316):** use `references/us_sources.md`. FCC ULS + ASR + OE-AAA do the heavy lifting.
- **Non-US carriers:** use `references/intl_sources.md`. Each major regulator has a structure/license registry (Ofcom UK, BNetzA DE, ACMA AU, ISED CA, ANATEL BR, ANFR FR, ComReg IE, etc.).
- **Always layer on crowdsourced:** `references/crowdsourced.md` for CellMapper + OpenCelliD — this is what provides the `(lac, ci, enb_id)` tuple that regulators never publish.

### 3. Pull the data

FCC bulk dumps beat portal scraping — download once, query locally. The `.dat` files are huge: **grep/awk them, never read them into an LLM context window**. If a live FCC/ASR/CellMapper portal times out (they are JavaScript-rendered), drive it with a headless browser; if still blocked, ask the user rather than silently downgrading to a centroid.

Use the bundled scripts where possible — faster and less error-prone than manual scraping:

- `scripts/uls_bulk_pull.py` — downloads an FCC weekly ULS dump, joins `HD.dat → EN.dat → LO.dat → FR.dat → AN.dat`, filters by licensee name or FRN, emits per-site rows with lat/lon, call sign, FRN, and antenna height.
- `scripts/opencellid_fetch.py` — pulls OpenCelliD data for a given MCC/MNC (API key via `OPENCELLID_API_KEY`), outputs `(lac, ci, enb_id, lat, lon, samples)` per observation.
- `scripts/asr_search.py` — queries the FCC ASR advanced search by entity name.
- `scripts/merge_sources.py` — applies the trust-order promotion rule and emits the final CSV.

If no script covers a source (e.g., an international regulator without a bulk dump), search/fetch manually and hand-enter rows, tagging `source` appropriately.

### 4. Merge in trust order

Higher-trust sources always win for `latitude`/`longitude`. Never overwrite a regulator-sourced coordinate with a crowdsourced one. Tag every row with its `source`.

Trust order (highest → lowest):
0. `OPERATOR_EXPORT` — the operator's own cell-site export, when you have one. **Match on the unique cell identity (full E-UTRAN CI), NEVER on eNodeB ID** — eNB ID (`CI >> 8`) is not unique per tower (one eNB value can map to dozens of sites), so an eNB join assigns arbitrary coordinates. Verify keying against real CDR location data (full ECI == export CI). Treat `mcc/mnc/lac/cell_id` as billing identifiers — enrich around them, never change them.
1. `FCC_ULS` — licensed transmitter site, carrier-attested
2. `FCC_ASR` — registered antenna structure, owner-attested
3. `FAA_OE` — obstruction evaluation, recent filings not yet in ASR
4. `INTL_REGULATOR` — non-US national registry (Ofcom/BNetzA/ACMA/etc.)
5. `FCC_BDC` — broadband coverage polygon (derived centroid only)
6. `CARRIER_COMMITMENT` — ECFS/Alaska Plan/RDOF named site, coords approximate
7. `CELLMAPPER` — crowdsourced sector observation, triangulated
8. `OPENCELLID` — crowdsourced, weighted centroid (require ≥5 samples)
9. `OPERATOR_DECLARED` — carrier website / press release, often a town centroid
10. `MANUAL_SEED` — village or admin-centroid placeholder

### 5. Emit the CSV

Use `assets/tower_master_template.csv` as the header. See `references/schema_mapping.md` for the column definitions, an example destination database schema, and a legacy TSS-style cellsite-master mapping.

Suggested filename convention: `<YYYYMMDD>_<TADIG>_CELLSITE_MASTER.csv`.

### 5b. Conformity pass (enriching an existing tower list in place)

When enriching or validating an existing production tower list rather than building a fresh one, normalize **every** field to consistent per-field values:

- `country` → uniform ISO code; `state` → 2-letter upper; `city` → trim, de-underscore, Title-case ALLCAPS (leave proper mixed case like "McCarthy" alone).
- `owner` → ONE canonical label per operator (an owner with three spellings is wrong): use the most-common existing label or the carrier reference name.
- Technology/switch labels → unify vendor variants; set blank-but-determinable values from context; reserve `UNKNOWN` for synthetic placeholder rows.
- Dates → one format (ISO `YYYY-MM-DD`); beware mixed M/D/Y vs D/M/Y in legacy data (a first field >12 means DD/MM).
- `latitude`/`longitude` → uniform decimal precision.
- Time zones → standard offset+abbreviation by state/region, **carrier-aware for split states** (e.g., Idaho has Pacific-zone and Mountain-zone operators).
- Enrichment metadata (`source`/confidence/accuracy) → controlled vocabulary, present on every filled row.
- A bare state-only address ("WA") is not an address — rebuild from city or reverse-geocode from the coordinates.
- Placeholder site names built from raw `MCCMNC|LAC|CI` strings are unhelpful for reporting — rewrite to a human-readable `"<identifier> <Carrier Name>"` form.
- If a name column is a reporting key it must be UNIQUE: `cell_id` alone recurs across LACs, so suffix duplicates with `(lac-cell_id)`. Respect destination column widths — a non-strict database that silently truncates can re-create collisions; trim the base while always keeping the unique suffix.
- Fill-only + fix placeholders: NEVER overwrite existing coordinates or touch the `mcc/mnc/lac/cell_id` billing keys.

### 6. Validate

Before presenting:

- **Every row has MCC + MNC** — these are the join keys downstream pipelines expect.
- **Every row has either (lat, lon) or `source=MANUAL_SEED`** — no silent nulls.
- **`lookup_key` format** — `{mcc}{mnc}|{lac}|{ci}` where available; nullable if LAC/CI not yet observed.
- **Count sanity check** — compare to the carrier's public site count if disclosed in filings or press. An 8-village rural co-op should not return 400 towers.

## Output format

ALWAYS produce two artifacts:

1. **The CSV** — matching `assets/tower_master_template.csv` headers exactly.
2. **A sources/methodology doc** (`<YYYYMMDD>_<TADIG>_TOWER_SOURCES.md`) — every query URL used, trust-order decisions made, row counts per source, and any placeholders still needing higher-trust promotion.

## CGI join hand-off

The point of the tower master is making the LAC/CI→site join work against CDR/TAP data:

- LTE extended-CGI fields commonly pack as `[type][PLMN 3B][LAC 2B][PLMN 3B][CI 3B][sector 1B]`, unpacking to `(mcc, mnc, lac, ci, sector)`.
- `enb_id = ci >> 8` (top 20 bits of the 28-bit E-UTRAN CI) collapses sectors onto towers; `sector = ci & 0xFF`.
- Join key: `lookup_key = {mcc}{mnc}|{lac}|{ci}`.

## What NOT to do

- **Don't invent coordinates.** If no authoritative or observed source exists, tag `source=MANUAL_SEED` with the town centroid and flag it for follow-up. Never ask an LLM to "guess the coordinates" of a tower from its name — that's how a site in Nome, AK lands in Pike Road, Alabama. Decode the site name → place, then pull the coordinate from a real source.
- **Don't page big files into context.** ULS `.dat` files and large tower CSVs must be queried with grep/awk/csv tooling.
- **Don't give up on a timeout.** FCC ULS/ASR and CellMapper are JS-rendered and fail under plain HTTP fetches. Use bulk dumps, a headless browser, or ask the user.
- **Don't scrape aggregator sites as primary sources.** `celltowermaps.com`, `antennasearch.com`, and similar re-package FCC data (usually stale). Go to the regulator.
- **Don't quote long passages from regulatory filings.** Paraphrase; attribute briefly and link.
- **Don't skip the sources doc.** The next person needs to reproduce the pull.

## Examples

### Example 1: US carrier, MCC/MNC given

> *"Find towers for AT&T Mobility in New Mexico, 310-410."*

ULS bulk pull filtered by entity name (try the licensing subsidiary names too); ASR advanced search by state; OE-AAA sponsor search; OpenCelliD pull for 310-410 clipped to NM; merge; emit CSV + sources doc.

### Example 2: rural co-op, name only

> *"Build a tower list for <small rural cooperative>."*

Resolve legal entity name and FRN first (FCC filings, BDC provider list). Rural carriers often file under the cooperative's full legal name, not the brand. ECFS dockets (Alaska Plan 16-271, RDOF 19-126) frequently name every committed site — gold for carriers with sparse crowdsourced coverage. Sanity-check the final count against the number of communities served.

### Example 3: international

> *"234-20 tower list please."*

234-20 → Hutchison 3G UK. International path: Ofcom Wireless Telegraphy Register (quarterly CSV, decimal-degree coords) + OpenCelliD for 234-20. Same merge and validation flow.

## Reference files

- `references/us_sources.md` — FCC ULS/ASR/OE/BDC/ECFS query recipes and field mappings
- `references/intl_sources.md` — non-US regulator registries by country, with tier ratings
- `references/crowdsourced.md` — CellMapper and OpenCelliD recipes, collapse rules, quality flags
- `references/schema_mapping.md` — output CSV schema, example destination DB mapping, TSS-style master mapping

## Scripts

- `scripts/uls_bulk_pull.py` — FCC ULS weekly dump → per-site rows
- `scripts/opencellid_fetch.py` — OpenCelliD → per-sector observations
- `scripts/asr_search.py` — FCC ASR entity search
- `scripts/merge_sources.py` — trust-order merge → final CSV
