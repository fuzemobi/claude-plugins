#!/usr/bin/env python3
"""
OpenCelliD fetch — pulls the OpenCelliD full DB, filters by MCC/MNC, and emits
per-tower rows in the tower_master CSV format with LAC/CI/eNB-ID derived.

Requires a free API token from https://opencellid.org — set OPENCELLID_API_KEY
or pass --api-key.

Usage:
    python opencellid_fetch.py --mcc 310 --mnc 410 --tadig USACG --carrier-name "AT&T"
    python opencellid_fetch.py --input cell_towers.csv --mcc 310 --mnc 410 --tadig USACG \\
        --carrier-name "AT&T"     # if you already have the full CSV locally
"""
from __future__ import annotations

import argparse
import csv
import gzip
import logging
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DOWNLOAD_URL = "https://opencellid.org/ocid/downloads?token={token}&type=full&file=cell_towers.csv.gz"

# OpenCelliD CSV columns
OC_COLS = [
    "radio", "mcc", "net", "area", "cell", "unit", "lon", "lat",
    "range", "samples", "changeable", "created", "updated", "averageSignal",
]

MIN_SAMPLES = 5


def download_full(token: str, out_path: Path):
    url = DOWNLOAD_URL.format(token=token)
    log.info("downloading OpenCelliD full DB (this can take a few minutes)")
    req = urllib.request.Request(url, headers={"User-Agent": "carrier-tower-research/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(out_path, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    log.info("wrote %s (%d bytes)", out_path, out_path.stat().st_size)


def filter_observations(src_path: Path, mcc: int, mnc: int) -> list[dict]:
    """Stream the OpenCelliD CSV (possibly gzipped), keep matching MCC/MNC."""
    opener = gzip.open if str(src_path).endswith(".gz") else open
    kept = []
    total = 0
    with opener(src_path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, fieldnames=OC_COLS)
        # skip header if present
        first = next(reader, None)
        if first and first.get("mcc", "").isdigit():
            # first row is data (no header)
            rows = [first] + list(reader)
        else:
            rows = reader
        for row in rows:
            total += 1
            try:
                if int(row["mcc"]) != mcc or int(row["net"]) != mnc:
                    continue
                if int(row["samples"] or 0) < MIN_SAMPLES:
                    continue
            except (ValueError, KeyError):
                continue
            kept.append(row)
    log.info("filtered %d rows from %d total (min samples = %d)", len(kept), total, MIN_SAMPLES)
    return kept


def collapse_to_enb(observations: list[dict]) -> list[dict]:
    """
    For LTE: group by (area, cell >> 8), average coords weighted by samples.
    For GSM/UMTS: keep per-cell rows.
    Returns list of tower dicts with lac/ci/enb_id/sector populated.
    """
    lte_groups = defaultdict(list)
    other_rows = []
    for obs in observations:
        radio = obs["radio"].upper()
        if radio in ("LTE", "NR"):
            try:
                lac = int(obs["area"])
                ci = int(obs["cell"])
                enb = ci >> 8
                lte_groups[(radio, lac, enb)].append({
                    "ci": ci,
                    "sector": ci & 0xFF,
                    "lat": float(obs["lat"]),
                    "lon": float(obs["lon"]),
                    "samples": int(obs["samples"]),
                    "created": obs["created"],
                    "updated": obs["updated"],
                })
            except (ValueError, KeyError):
                continue
        else:
            try:
                other_rows.append({
                    "radio": radio,
                    "lac": int(obs["area"]),
                    "ci": int(obs["cell"]),
                    "enb_id": "",
                    "sector": "",
                    "lat": float(obs["lat"]),
                    "lon": float(obs["lon"]),
                    "samples": int(obs["samples"]),
                    "created": obs["created"],
                    "updated": obs["updated"],
                })
            except (ValueError, KeyError):
                continue

    collapsed = []
    for (radio, lac, enb), sectors in lte_groups.items():
        total_samples = sum(s["samples"] for s in sectors)
        w_lat = sum(s["lat"] * s["samples"] for s in sectors) / total_samples
        w_lon = sum(s["lon"] * s["samples"] for s in sectors) / total_samples
        first_ci = min(s["ci"] for s in sectors)
        updated = max(s["updated"] for s in sectors)
        collapsed.append({
            "radio": radio,
            "lac": lac,
            "ci": first_ci,
            "enb_id": enb,
            "sector": ",".join(str(s["sector"]) for s in sorted(sectors, key=lambda x: x["sector"])),
            "lat": round(w_lat, 6),
            "lon": round(w_lon, 6),
            "samples": total_samples,
            "sector_count": len(sectors),
            "updated": updated,
        })
    collapsed.extend([
        {**r, "sector_count": 1} for r in other_rows
    ])
    log.info("collapsed to %d towers (LTE eNB collapsed + GSM/UMTS per-cell)", len(collapsed))
    return collapsed


def emit_rows(towers: list[dict], tadig: str, mcc: int, mnc: int,
              carrier_name: str, out) -> int:
    today = date.today().isoformat()
    fieldnames = [
        "carrier_name", "tadig", "mcc", "mnc", "site_id", "site_name", "community",
        "state", "country", "latitude", "longitude", "height_agl_ft", "height_agl_m",
        "structure_type", "asr_number", "uls_call_sign", "oe_study_number", "frn",
        "lac", "ci", "enb_id", "sector", "band", "technology", "status",
        "source", "source_url", "last_verified", "notes",
    ]
    w = csv.DictWriter(out, fieldnames=fieldnames)
    w.writeheader()
    count = 0
    for i, t in enumerate(sorted(towers, key=lambda x: (x.get("enb_id") or x["ci"])), start=1):
        ident = t.get("enb_id") or t["ci"]
        count += 1
        w.writerow({
            "carrier_name": carrier_name,
            "tadig": tadig,
            "mcc": mcc,
            "mnc": mnc,
            "site_id": f"{tadig}-OC-{i:04d}",
            "site_name": f"OpenCelliD eNB {ident}" if t.get("enb_id") else f"OpenCelliD cell {t['ci']}",
            "community": "",
            "state": "",
            "country": "",
            "latitude": t["lat"],
            "longitude": t["lon"],
            "height_agl_ft": "",
            "height_agl_m": "",
            "structure_type": "",
            "asr_number": "",
            "uls_call_sign": "",
            "oe_study_number": "",
            "frn": "",
            "lac": t["lac"],
            "ci": t["ci"],
            "enb_id": t.get("enb_id", ""),
            "sector": t.get("sector", ""),
            "band": "",
            "technology": t.get("radio", ""),
            "status": "operational",
            "source": "OPENCELLID",
            "source_url": f"https://opencellid.org/#zoom=16&lat={t['lat']}&lon={t['lon']}",
            "last_verified": today,
            "notes": f"samples={t['samples']};sector_count={t.get('sector_count', 1)};updated={t.get('updated', '')}",
        })
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mcc", type=int, required=True)
    ap.add_argument("--mnc", type=int, required=True)
    ap.add_argument("--tadig", required=True)
    ap.add_argument("--carrier-name", required=True)
    ap.add_argument("--input", help="Local cell_towers.csv(.gz) path; skips download")
    ap.add_argument("--api-key", default=os.environ.get("OPENCELLID_API_KEY"),
                    help="OpenCelliD API token (env OPENCELLID_API_KEY)")
    ap.add_argument("--output", default="-", help="Output CSV path (default: stdout)")
    ap.add_argument("--cache-dir", default=None)
    args = ap.parse_args()

    if args.input:
        src = Path(args.input)
    else:
        if not args.api_key:
            ap.error("--input or --api-key (or OPENCELLID_API_KEY env var) required")
        cache = Path(args.cache_dir) if args.cache_dir else Path("/tmp/opencellid_cache")
        cache.mkdir(parents=True, exist_ok=True)
        src = cache / "cell_towers.csv.gz"
        if not src.exists():
            download_full(args.api_key, src)
        else:
            log.info("cache hit: %s", src)

    observations = filter_observations(src, args.mcc, args.mnc)
    if not observations:
        log.warning("no observations for %d-%d; try increasing --min-samples or verify MCC/MNC", args.mcc, args.mnc)
        sys.exit(1)

    towers = collapse_to_enb(observations)

    out = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    try:
        n = emit_rows(towers, args.tadig, args.mcc, args.mnc, args.carrier_name, out)
    finally:
        if args.output != "-":
            out.close()
    log.info("wrote %d rows to %s", n, args.output)


if __name__ == "__main__":
    main()
