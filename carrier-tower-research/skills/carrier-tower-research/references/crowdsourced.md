# Crowdsourced Sources

Crowdsourced platforms are the only practical way to get `(lac, ci, enb_id)` observations tied to coordinates. Regulators give you where the tower IS; crowdsourced gives you what cell ID it broadcasts. You need both to join CDRs to towers.

---

## OpenCelliD — primary crowdsourced source

Free, downloadable, well-structured CSV. Apache 2.0 licensed data.

### Access

1. Register free account: https://opencellid.org
2. Download full DB or per-country extract via API key.
3. Or use the snapshot mirrors (updated daily).

### CSV schema

```
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
```

| Column | Meaning | Master column |
|---|---|---|
| `radio` | `GSM`, `UMTS`, `LTE`, `NR` | `technology` |
| `mcc` | Mobile Country Code | `mcc` |
| `net` | Mobile Network Code (MNC) | `mnc` |
| `area` | Location Area Code (LAC) or Tracking Area Code (TAC) | `lac` |
| `cell` | Cell ID — 28-bit for LTE | `ci` |
| `lon`, `lat` | weighted centroid of observations | `longitude`, `latitude` |
| `range` | estimated cell range in meters | (metadata) |
| `samples` | number of observations | quality filter |
| `averageSignal` | average RSSI | (metadata) |

### Filtering recipe

For a given MCC/MNC:
```bash
awk -F, '$2==310 && $3==410 && $10>=5' cell_towers.csv > observed_310410.csv
```

`samples >= 5` is the minimum I trust. Below that, coords can be off by km.

### Deriving `enb_id`

For LTE:
```
enb_id = cell >> 8
sector = cell & 0xFF
```

This collapses sector-level rows (e.g., CI 263681, 263682, 263683) onto a single eNB ID (1030 in that example = eNB with 3 sectors).

### Script

Use `scripts/opencellid_fetch.py` which handles the download, filter, and enb_id derivation.

---

## CellMapper — higher-fidelity but manual

Free tier available. Per-sector triangulation with PCI, band, and observed signal.

### Access

1. Register at https://www.cellmapper.net
2. Map viewer: `https://www.cellmapper.net/map?MCC=<MCC>&MNC=<MNC>`
3. Export requires a paid contributor account or negotiation with the site owner.

### Data quality

CellMapper's tower locations are triangulated from many observations and typically tighter than OpenCelliD's weighted centroid — within ~50m for well-surveyed areas. Sparse in rural areas (including most of Alaska).

### When to use

- When OpenCelliD has a tower with <5 samples, check CellMapper for better data.
- When you need **band and PCI** per sector — CellMapper has these, OpenCelliD doesn't reliably.
- As a visual cross-check for merged master data.

### Export format

CSV with columns: `latitude,longitude,altitude,MCC,MNC,LAC,CID,signal,type,subtype,ARFCN,PSC`.

The `subtype` column distinguishes LTE band (e.g., `B12`, `B13`, `B66`). `PSC` is the physical cell ID (PCI) for LTE.

---

## Mozilla Location Service — legacy

Discontinued in 2023 but historical dumps still circulate. Useful only for historical cell data from ~2015-2022. Don't use for current mapping.

---

## Merge strategy

Both OpenCelliD and CellMapper produce observation-level data. Collapse to tower-level before merging with regulator data:

### Collapse rule for LTE

Group observations by `(mcc, mnc, enb_id)` where `enb_id = ci >> 8`.
- **Coordinates:** weighted average by `samples` (OpenCelliD) or simple mean (CellMapper).
- **Sectors:** retain as separate rows in the master OR collapse into a single tower row with a count of sectors.
- **Band:** take the union of observed bands (a tower often broadcasts multiple).

### Collapse rule for GSM/UMTS

Group by `(mcc, mnc, lac, ci)` directly — no enb_id derivation.

### Merging with regulator data

1. Start with regulator rows (ULS/ASR/intl). These have tight coords but no LAC/CI.
2. For each crowdsourced observation, find the nearest regulator row within **2 km**.
3. If a match exists: append the LAC/CI/eNB-ID/band/PCI columns to that regulator row. The regulator row keeps its `source=FCC_ULS` (etc.) tag.
4. If no regulator row within 2 km: add the crowdsourced observation as a new row with `source=OPENCELLID` (or `CELLMAPPER`).
5. If multiple crowdsourced observations collapse to the same eNB but match different regulator rows: flag for manual review.

The 2 km threshold works for rural/suburban. Urban dense deployments may need 500m.

---

## Quality flags to apply

Set the `notes` column with data-quality hints:

- `crowdsourced_only` — no regulator match found
- `sample_count_low` — OpenCelliD samples <10, treat coords as approximate
- `enb_matched_regulator=<ASR#|ULS call sign>` — high-confidence tower-to-site tie
- `multi_band` — eNB observed on multiple bands
- `sector_count=<N>` — derived from distinct `ci` values on same `enb_id`

---

## What NOT to trust

- **`opencellid.org` rows with `samples=1`** — single observation, coords can be anywhere within the cell's reach.
- **CellMapper "predicted" tower locations** — unmarked predictions can drift by km; only trust "confirmed" status.
- **Any data from aggregators** like `opencellid.com` (note the `.com` — commercial scraper), `cellidfinder.com`, `mylnikov.org`. These are re-packaged OpenCelliD data and may be stale.
- **Google's Geolocation API results** — rate-limited, ToS-restricted, and results are anonymized to cell sector centroids.
