#!/usr/bin/env python3
"""
Merge multiple tower CSVs by trust order. Higher-trust sources win on coordinate
conflicts; lower-trust sources contribute only missing columns (like LAC/CI).

Usage:
    python merge_sources.py \\
        --input uls.csv,asr.csv,opencellid.csv \\
        --output 20260801_USACG_CELLSITE_MASTER.csv \\
        --tadig USACG \\
        --proximity-m 2000
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TRUST_ORDER = {
    "FCC_ULS": 100,
    "FCC_ASR": 95,
    "FAA_OE": 90,
    "INTL_REGULATOR": 85,
    "FCC_BDC": 70,
    "CARRIER_COMMITMENT": 60,
    "CELLMAPPER": 40,
    "OPENCELLID": 30,
    "OPERATOR_DECLARED": 20,
    "MANUAL_SEED": 10,
}

FIELDNAMES = [
    "carrier_name", "tadig", "mcc", "mnc", "site_id", "site_name", "community",
    "state", "country", "latitude", "longitude", "height_agl_ft", "height_agl_m",
    "structure_type", "asr_number", "uls_call_sign", "oe_study_number", "frn",
    "lac", "ci", "enb_id", "sector", "band", "technology", "status",
    "source", "source_url", "last_verified", "notes",
]

EARTH_R_M = 6_371_000.0


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return float("inf")
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def load_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            # Normalize missing columns
            for k in FIELDNAMES:
                row.setdefault(k, "")
            rows.append(row)
    log.info("%s: %d rows", path, len(rows))
    return rows


def trust(row: dict) -> int:
    return TRUST_ORDER.get(row.get("source", ""), 0)


def merge_row(primary: dict, secondary: dict) -> dict:
    """Primary wins on all populated fields; fill empties from secondary."""
    out = dict(primary)
    for k, v in secondary.items():
        if not out.get(k) and v:
            out[k] = v
    # Keep primary's source; note the merge in notes.
    primary_src = primary.get("source", "")
    secondary_src = secondary.get("source", "")
    if primary_src and secondary_src and primary_src != secondary_src:
        extra = f"merged_from={secondary_src}"
        notes = out.get("notes", "")
        if extra not in notes:
            out["notes"] = f"{notes};{extra}" if notes else extra
    return out


def merge(rows: list[dict], proximity_m: float) -> list[dict]:
    """
    Group rows by nearest-neighbor within proximity_m. Higher-trust row in each
    group becomes the representative; lower-trust rows contribute missing fields
    and observational columns (LAC/CI/eNB).
    """
    # Sort by trust desc so we seed groups with the best source.
    ordered = sorted(rows, key=lambda r: -trust(r))
    groups: list[dict] = []
    for row in ordered:
        lat, lon = row.get("latitude"), row.get("longitude")
        if not lat or not lon:
            # No coords: keep as-is only if it has LAC/CI (observational-only).
            if row.get("lac") or row.get("ci"):
                groups.append(row)
            else:
                log.debug("skipping row with no coords and no LAC/CI: %s", row.get("site_id"))
            continue
        match = None
        for g in groups:
            g_lat, g_lon = g.get("latitude"), g.get("longitude")
            if not g_lat or not g_lon:
                continue
            if haversine_m(lat, lon, g_lat, g_lon) <= proximity_m:
                match = g
                break
        if match:
            # The group was seeded with the higher-trust row, so merge onto it.
            merged = merge_row(match, row)
            # replace in groups
            idx = groups.index(match)
            groups[idx] = merged
        else:
            groups.append(row)
    log.info("merged %d raw rows into %d towers", len(rows), len(groups))
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="Comma-separated list of CSV paths")
    ap.add_argument("--output", required=True)
    ap.add_argument("--tadig", help="Optional TADIG override (applies to all rows)")
    ap.add_argument("--proximity-m", type=float, default=2000.0,
                    help="Merge radius in meters (default 2000)")
    args = ap.parse_args()

    all_rows = []
    for p in args.input.split(","):
        all_rows.extend(load_csv(Path(p.strip())))

    if args.tadig:
        for r in all_rows:
            if not r.get("tadig"):
                r["tadig"] = args.tadig

    merged = merge(all_rows, args.proximity_m)

    # Re-number site_ids sequentially so the output is clean.
    by_city = {}
    for r in merged:
        if r.get("source", "").startswith(("FCC_ULS", "FCC_ASR", "INTL_")):
            # Preserve site_id from authoritative sources.
            continue
        city = (r.get("community") or r.get("city") or "UNK")[:3].upper().replace(" ", "")
        by_city[city] = by_city.get(city, 0) + 1
        r["site_id"] = f"{r.get('tadig', 'UNK')}-{city}-{by_city[city]:02d}"

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for r in merged:
            w.writerow(r)
    log.info("wrote %d rows to %s", len(merged), out_path)

    # Summary by source.
    by_source = {}
    for r in merged:
        by_source[r.get("source", "UNKNOWN")] = by_source.get(r.get("source", "UNKNOWN"), 0) + 1
    log.info("summary by source: %s", by_source)


if __name__ == "__main__":
    main()
