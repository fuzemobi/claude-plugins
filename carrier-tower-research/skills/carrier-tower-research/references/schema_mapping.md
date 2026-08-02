# Schema Mapping

Three schemas to reconcile when emitting the tower master:

1. **This skill's output CSV** (the artifact we deliver to the user)
2. **Example destination `towers` table** (a typical roaming-billing database)
3. **TSS-style cellsite master** (a legacy interchange format common in roaming billing)

The skill's output CSV is a superset. Every column in both downstream schemas maps to an output column; extra columns in the output carry authoritative-source provenance.

---

## Output CSV columns (in `assets/tower_master_template.csv`)

| # | Column | Type | Required | Description |
|---|---|---|---|---|
| 1 | `carrier_name` | string | ✓ | Legal entity name |
| 2 | `tadig` | string(5) | ✓ | TADIG code (USAAC, USASN, etc.) |
| 3 | `mcc` | string(3) | ✓ | Mobile Country Code |
| 4 | `mnc` | string(2-3) | ✓ | Mobile Network Code |
| 5 | `site_id` | string | ✓ | Internal PK, `<TADIG>-<CITY3>-<NN>` |
| 6 | `site_name` | string | | Human-readable site name |
| 7 | `community` | string | | Village/community name |
| 8 | `state` | string(2) | | US state or ISO region code |
| 9 | `country` | string(2) | ✓ | ISO 3166-1 alpha-2 |
| 10 | `latitude` | decimal | | Decimal degrees, WGS84 |
| 11 | `longitude` | decimal | | Decimal degrees, WGS84 |
| 12 | `height_agl_ft` | integer | | Height above ground in feet |
| 13 | `height_agl_m` | decimal | | Height above ground in meters |
| 14 | `structure_type` | string | | `Monopole`, `Lattice`, `Guyed`, `Tower`, `Rooftop`, etc. |
| 15 | `asr_number` | string | | FCC ASR registration (US only) |
| 16 | `uls_call_sign` | string | | FCC ULS call sign (US only) |
| 17 | `oe_study_number` | string | | FAA OE study ID (US only) |
| 18 | `frn` | string | | FCC Registration Number (US only) |
| 19 | `lac` | integer | | Location Area Code (GSM/UMTS) or Tracking Area Code (LTE) |
| 20 | `ci` | integer | | Cell Identity (28-bit for LTE) |
| 21 | `enb_id` | integer | | Derived eNB ID (LTE only, `ci >> 8`) |
| 22 | `sector` | integer | | Sector number (1-3 typ., derived from `ci & 0xFF`) |
| 23 | `band` | string | | `B2`, `B12`, `n77`, etc. |
| 24 | `technology` | string | | `GSM`, `UMTS`, `LTE`, `5G-NR` |
| 25 | `status` | string | | `operational`, `planned`, `decommissioned`, `proposed` |
| 26 | `source` | string | ✓ | Enum (see below) |
| 27 | `source_url` | string | | Direct link to underlying record |
| 28 | `last_verified` | ISO date | ✓ | YYYY-MM-DD |
| 29 | `notes` | string | | Free text |

### `source` enum (trust order high → low)

```
FCC_ULS
FCC_ASR
FAA_OE
INTL_REGULATOR
FCC_BDC
CARRIER_COMMITMENT
CELLMAPPER
OPENCELLID
OPERATOR_DECLARED
MANUAL_SEED
```

---

## Example destination `towers` table

A representative roaming-billing schema (adapt to yours):

```sql
towers {
    id               PK
    partner_tadig    FK → partner_operators.tadig_code  -- owner
    carrier_tadig    FK → carriers.tadig_code           -- billing
    cell_id          string
    tower_name       string
    switch_type      string
    owner            string
    latitude         float
    longitude        float
    address          string
    city             string
    state            string
    country          string
    mcc              string
    mnc              string
    lac              string
    bid              string
    pmn              string
    time_zone_utc    int
    time_zone_designation string
    effective_date   date
    disconnect_date  date
    is_active        bool
}
```

### Mapping from output CSV → `towers`

| `towers` column | Output CSV column | Transform |
|---|---|---|
| `partner_tadig` | `tadig` | For a carrier's own towers, owner = carrier |
| `carrier_tadig` | `tadig` | For own towers, billing = owner. For partner towers seen via another op, set to billing op's TADIG. |
| `cell_id` | `ci` | stringify |
| `tower_name` | `site_name` | |
| `switch_type` | derived | From ULS Service code or carrier knowledge (e.g., `Ericsson LTE`, `Nokia LTE`) |
| `owner` | `carrier_name` | |
| `latitude` | `latitude` | |
| `longitude` | `longitude` | |
| `city` | `community` or `city` | |
| `state` | `state` | |
| `country` | `country` | |
| `mcc` | `mcc` | |
| `mnc` | `mnc` | |
| `lac` | `lac` | stringify |
| `bid` | derived | Billing ID; synthesize as `<mcc><mnc><lac_or_enb>` if carrier doesn't provide |
| `pmn` | `tadig` | PMN is the TADIG in this schema |
| `effective_date` | `last_verified` or per-row service date | |
| `is_active` | derived from `status` | `status in ('operational','planned')` → true |

### Lookup key derivation

The audit pipeline uses:
```
lookup_key = f"{mcc}{mnc}|{lac}|{ci}"
```

Always emit this in the notes column if not a separate column:
```
lookup_key=310710|1234|56789
```

---

## TSS-style cellsite master format

Typical header:

```
Effective Date, Cell Site ID, Cell Site Name, Switch Type, Owning Operator,
Create CDR File, Owner, City, State, GSM/UMTS/LTE, BID, PMN, MCC, MNC,
City, State, LAC, Time Zone/UTC, Time Zone Designation
```

Note the duplicate `City, State` pair — the first pair is administrative location, the second is billing/rating location. For most rural carriers they're identical.

### Mapping from output CSV → TSS format

| TSS column | Output CSV column | Transform |
|---|---|---|
| `Effective Date` | `last_verified` | Reformat as M/D/YY |
| `Cell Site ID` | `site_id` | |
| `Cell Site Name` | `site_name` | |
| `Switch Type` | `structure_type` + `technology` | e.g., `Ericsson LTE` |
| `Owning Operator` | `carrier_name` | |
| `Create CDR File` | constant `Yes` | unless the row is partner-owned (then `No`) |
| `Owner` | short form of `carrier_name` | trade name / short label |
| `City` (1st) | `community` | |
| `State` (1st) | `state` | |
| `GSM/UMTS/LTE` | `technology` | |
| `BID` | derived | |
| `PMN` | `tadig` | |
| `MCC` | `mcc` | |
| `MNC` | `mnc` | |
| `City` (2nd) | `community` | typically same as 1st |
| `State` (2nd) | `state` | typically same as 1st |
| `LAC` | `lac` | |
| `Time Zone/UTC` | derived from state/country | Alaska = `-9` (or `-8` with DST), Utah = `-7`, Iowa = `-6`, etc. |
| `Time Zone Designation` | derived | `AKST`, `MST`, `CST`, `EST`, etc. |

When producing the TSS-compatible variant, write to a separate file:
`<YYYYMMDD>_<TADIG>_TSS_CELLSITE_MASTER.csv`

The "full" output CSV remains the primary artifact and carries all provenance data.

---

## Timezone lookup table

For US states, use this mapping for `Time Zone/UTC` and `Time Zone Designation`:

| State | UTC | Designation | DST? |
|---|---|---|---|
| AK | -9 | AKST | Yes |
| WA, OR, CA, NV | -8 | PST | Yes |
| MT, WY, UT, CO, NM, ID, AZ | -7 | MST | Most (AZ = no) |
| ND, SD, NE, KS, OK, TX, MN, IA, MO, AR, LA, WI, IL, MS, AL, TN | -6 | CST | Yes |
| MI, IN, OH, KY, GA, FL, SC, NC, VA, WV, PA, NY, NJ, DE, MD, DC, CT, MA, RI, VT, NH, ME | -5 | EST | Yes |

Use the standard-time offset in the CSV; DST handling is downstream.

---

## `bid` (Billing ID) derivation

If the carrier provides a BID, use it. If not, synthesize as:
```
bid = f"{mcc}{mnc}{lac:0>5}"
```

Some carriers use the LAC alone as the BID; others use the full concatenation. When in doubt, use the concatenated form and document the choice in `notes`.
