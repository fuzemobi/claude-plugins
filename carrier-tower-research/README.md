# carrier-tower-research

A Claude Code skill that builds **authoritative cell-tower master lists** for any mobile carrier in the world, from an MCC/MNC pair, a TADIG code, or just a carrier name.

## The problem

There is no single database of cell towers. What exists is scattered across:

- **Regulators** that know where licensed transmitters physically are (exact coordinates) but nothing about what cell IDs they broadcast;
- **Crowdsourced RF platforms** that know what `(LAC, CI)` a phone saw and roughly where — but with accuracy ranging from 50 m to several km;
- **Carrier filings** that name committed sites in prose PDFs;
- **Aggregator websites** that re-package stale copies of all of the above.

If you work with CDR/TAP billing data, coverage analysis, or roaming audits, you eventually need the join that none of these sources provide alone: **`(mcc, mnc, lac, ci)` → a real tower at a real coordinate, with a defensible source.**

This skill teaches Claude the complete research pipeline to build that join.

## What it does

Given a carrier (e.g. `310-410`, `USACG`, or "AT&T Mobility"):

1. **Resolves identity** — MCC/MNC ↔ TADIG ↔ FCC legal entity name (the detail that makes or breaks regulator searches: ULS indexes the registered cooperative/LLC name, not the brand).
2. **Pulls authoritative sources** — US: FCC ULS bulk dumps (per-transmitter coordinates), FCC ASR (registered structures), FAA OE/AAA (recent filings), FCC BDC (coverage validation), ECFS dockets (named site commitments in Alaska Plan / RDOF filings). International: Ofcom, BNetzA, ANFR, ACMA, ISED, and a tiered directory of other regulators.
3. **Layers crowdsourced observations** — OpenCelliD and CellMapper supply the `(lac, ci)` tuples regulators never publish, collapsed sector→tower via `enb_id = ci >> 8`.
4. **Merges in explicit trust order** — an 11-level source hierarchy where a regulator coordinate can never be overwritten by a crowdsourced centroid, and every row carries a `source` tag and `source_url`.
5. **Validates** — join-key completeness, no silent coordinate nulls, and a count sanity check against the carrier's publicly disclosed footprint.
6. **Emits two artifacts** — a provenance-tagged CSV (29-column schema, template included) and a methodology doc listing every query used, so the pull is reproducible.

It also includes a **conformity pass** for enriching an existing production tower list in place (normalize owners, time zones, dates, addresses; make report keys unique; never touch the billing identifiers) — the mode you want when a `towers` table already exists and is half-populated.

## Why the trust order matters

The single most common failure in tower mapping is silently mixing sources of different quality. Concrete examples this skill guards against:

- **Joining on eNodeB ID instead of full cell identity.** eNB ID is *not* unique per tower; one eNB value can map to dozens of sites. The skill mandates full-ECI matching and verification against real CDR location data.
- **LLM-guessed coordinates.** Asking a model to "estimate where this tower is" from its name is how a site in Nome, Alaska lands in Pike Road, Alabama. Placeholders are allowed — but only tagged `MANUAL_SEED` at a town centroid, flagged for follow-up.
- **Trusting single-observation crowdsourced rows.** OpenCelliD rows with fewer than 5 samples can be kilometers off; the skill requires a sample floor and documents the collapse rules.

## Install

```
/plugin marketplace add fuzemobi/claude-plugins
/plugin install carrier-tower-research@fuzemobi-plugins
```

Then just ask: *"build me a tower list for 310-410 in New Mexico"*.

## Prerequisites

- Python 3.9+ (scripts use stdlib + `requests` where noted)
- A free [OpenCelliD](https://opencellid.org) API key in `OPENCELLID_API_KEY` (only for the crowdsourced layer)
- No FCC credentials needed — ULS/ASR bulk dumps are public downloads

## Contents

| Path | What |
|---|---|
| `skills/carrier-tower-research/SKILL.md` | The workflow: identify → pull → merge → conform → validate |
| `references/us_sources.md` | FCC ULS/ASR/OE/BDC/ECFS recipes, `.dat` join keys, awk one-liners, DMS→decimal conversion, frequency→band table |
| `references/intl_sources.md` | Regulator registries for 15+ countries, tiered by data quality |
| `references/crowdsourced.md` | OpenCelliD/CellMapper recipes, sector-collapse rules, quality flags, what NOT to trust |
| `references/schema_mapping.md` | 29-column output schema, example destination DB mapping, legacy TSS-format mapping |
| `scripts/uls_bulk_pull.py` | FCC ULS weekly dump → per-site rows (HD→EN→LO→FR→AN join) |
| `scripts/opencellid_fetch.py` | OpenCelliD → per-sector observations with eNB derivation |
| `scripts/asr_search.py` | FCC ASR advanced search by entity |
| `scripts/merge_sources.py` | Trust-order merge → final CSV |
| `assets/tower_master_template.csv` | The output header row |

## Scope and ethics

Everything this skill queries is **public data**: government licensing records, public regulatory filings, and openly licensed crowdsourced observations (OpenCelliD data is Apache-2.0). It contains no subscriber data, no credentials, and no proprietary carrier information. Respect each source's rate limits and terms (the references note them, e.g. Nominatim's 1 req/sec policy).

## License

MIT
