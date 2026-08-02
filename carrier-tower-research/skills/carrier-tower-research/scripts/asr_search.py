#!/usr/bin/env python3
"""
FCC ASR advanced search — queries the ASR system for a given entity name and
emits per-structure rows in the tower_master CSV format.

Uses the ASR weekly dump (r_tower.zip) which is the reliable programmatic path.
The HTML advanced search form at wireless2.fcc.gov is also available for manual
use but isn't easily scrapable.

Usage:
    python asr_search.py --entity "AT&T Mobility" --state NM --tadig USACG --mcc 310 --mnc 410
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import tempfile
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

csv.field_size_limit(sys.maxsize)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ASR_DUMP_URL = "https://data.fcc.gov/download/pub/uls/complete/r_tower.zip"

# r_tower.zip contents (primary files we need):
#   RA.dat  — structure registrations (lat/lon, height, owner, type)
#   EN.dat  — entity/owner records

RA_COLS = {
    "record_type": 0,
    "content_indicator": 1,
    "file_number": 2,
    "registration_number": 3,
    "unique_system_identifier": 4,
    "application_purpose": 5,
    "previous_purpose": 6,
    "input_source_code": 7,
    "status_code": 8,
    "date_entered": 9,
    "date_received": 10,
    "date_issued": 11,
    "date_constructed": 12,
    "date_dismantled": 13,
    "date_action": 14,
    "archive_flag_code": 15,
    "version": 16,
    "signature_first_name": 17,
    "signature_middle_initial": 18,
    "signature_last_name": 19,
    "signature_suffix": 20,
    "signature_title": 21,
    "invalid_signature_flag": 22,
    "structure_street_address": 23,
    "structure_city": 24,
    "structure_state_code": 25,
    "county_code": 26,
    "zip_code": 27,
    "height_of_structure": 28,
    "ground_elevation": 29,
    "overall_height_above_ground": 30,
    "overall_height_amsl": 31,
    "structure_type": 32,
    "date_faa_determination_issued": 33,
    "faa_study_number": 34,
    "faa_circular_number": 35,
    "specification_option": 36,
    "painting_and_lighting": 37,
    "mark_light_code": 38,
    "mark_light_other": 39,
    "faa_emi_flag": 40,
    "nepa_flag": 41,
    "date_signed": 42,
    "signature_last_or_entity_name": 43,
    "latitude_degrees": 44,
    "latitude_minutes": 45,
    "latitude_seconds": 46,
    "latitude_direction": 47,
    "latitude_total_seconds": 48,
    "longitude_degrees": 49,
    "longitude_minutes": 50,
    "longitude_seconds": 51,
    "longitude_direction": 52,
    "longitude_total_seconds": 53,
}

EN_COLS = {
    "record_type": 0,
    "content_indicator": 1,
    "file_number": 2,
    "registration_number": 3,
    "unique_system_identifier": 4,
    "contact_type_code": 5,
    "entity_type_code": 6,
    "reserved_7": 7,
    "licensee_id": 8,
    "entity_name": 9,
    "first_name": 10,
    "mi": 11,
    "last_name": 12,
    "suffix": 13,
    "phone": 14,
    "fax": 15,
    "internet_address": 16,
    "street_address": 17,
    "po_box": 18,
    "city": 19,
    "state": 20,
    "zip_code": 21,
    "attention_line": 22,
}


def dms_to_decimal(deg: str, mn: str, sec: str, direction: str) -> float | None:
    try:
        d = float(deg or 0)
        m = float(mn or 0)
        s = float(sec or 0)
        val = d + m / 60.0 + s / 3600.0
        if direction.upper() in ("S", "W"):
            val = -val
        return round(val, 6)
    except (ValueError, TypeError):
        return None


def download(url: str, cache_dir: Path) -> Path:
    name = url.rsplit("/", 1)[-1]
    path = cache_dir / name
    if path.exists():
        log.info("cache hit: %s", path)
        return path
    log.info("downloading %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "carrier-tower-research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    log.info("wrote %s (%d bytes)", path, path.stat().st_size)
    return path


def read_dat(zip_path: Path, dat_name: str):
    with zipfile.ZipFile(zip_path) as z:
        try:
            with z.open(dat_name) as f:
                reader = csv.reader(
                    io.TextIOWrapper(f, encoding="latin-1", errors="replace"),
                    delimiter="|",
                )
                for row in reader:
                    yield row
        except KeyError:
            log.warning("%s not in %s", dat_name, zip_path)
            return


def match_registrations(zip_path: Path, entity_pat: str, state: str | None) -> set[str]:
    """Return set of registration_numbers whose EN record matches."""
    matched = set()
    pat = entity_pat.upper()
    for row in read_dat(zip_path, "EN.dat"):
        if len(row) <= EN_COLS["state"]:
            continue
        name = row[EN_COLS["entity_name"]].upper()
        if pat not in name:
            continue
        reg = row[EN_COLS["registration_number"]]
        if reg:
            matched.add(reg)
    log.info("matched %d registrations in EN.dat", len(matched))
    return matched


def load_structures(zip_path: Path, reg_numbers: set[str], state: str | None) -> list[dict]:
    out = []
    for row in read_dat(zip_path, "RA.dat"):
        if len(row) <= RA_COLS["longitude_direction"]:
            continue
        reg = row[RA_COLS["registration_number"]]
        if reg not in reg_numbers:
            continue
        status = row[RA_COLS["status_code"]]
        if status != "C":
            continue
        if state and row[RA_COLS["structure_state_code"]] != state:
            continue
        lat = dms_to_decimal(
            row[RA_COLS["latitude_degrees"]], row[RA_COLS["latitude_minutes"]],
            row[RA_COLS["latitude_seconds"]], row[RA_COLS["latitude_direction"]],
        )
        lon = dms_to_decimal(
            row[RA_COLS["longitude_degrees"]], row[RA_COLS["longitude_minutes"]],
            row[RA_COLS["longitude_seconds"]], row[RA_COLS["longitude_direction"]],
        )
        if lat is None or lon is None:
            continue
        try:
            height_m = float(row[RA_COLS["overall_height_above_ground"]] or 0)
        except ValueError:
            height_m = 0
        out.append({
            "registration_number": reg,
            "address": row[RA_COLS["structure_street_address"]],
            "city": row[RA_COLS["structure_city"]],
            "state": row[RA_COLS["structure_state_code"]],
            "latitude": lat,
            "longitude": lon,
            "structure_type": row[RA_COLS["structure_type"]],
            "height_agl_m": height_m,
            "height_agl_ft": round(height_m * 3.28084, 1) if height_m else "",
            "owner_name": row[RA_COLS["signature_last_or_entity_name"]],
            "faa_study": row[RA_COLS["faa_study_number"]],
        })
    log.info("loaded %d constructed structures", len(out))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", required=True)
    ap.add_argument("--state", help="2-letter state code to filter (optional)")
    ap.add_argument("--tadig", required=True)
    ap.add_argument("--mcc", required=True)
    ap.add_argument("--mnc", required=True)
    ap.add_argument("--output", default="-")
    ap.add_argument("--cache-dir", default=None)
    args = ap.parse_args()

    cache = Path(args.cache_dir) if args.cache_dir else Path(tempfile.gettempdir()) / "asr_cache"
    cache.mkdir(parents=True, exist_ok=True)
    zip_path = download(ASR_DUMP_URL, cache)

    regs = match_registrations(zip_path, args.entity, args.state)
    if not regs:
        log.warning("no registrations matched entity '%s'", args.entity)
        sys.exit(1)
    structures = load_structures(zip_path, regs, args.state)
    if not structures:
        log.warning("no constructed structures found")
        sys.exit(1)

    today = date.today().isoformat()
    fieldnames = [
        "carrier_name", "tadig", "mcc", "mnc", "site_id", "site_name", "community",
        "state", "country", "latitude", "longitude", "height_agl_ft", "height_agl_m",
        "structure_type", "asr_number", "uls_call_sign", "oe_study_number", "frn",
        "lac", "ci", "enb_id", "sector", "band", "technology", "status",
        "source", "source_url", "last_verified", "notes",
    ]
    out = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    try:
        w = csv.DictWriter(out, fieldnames=fieldnames)
        w.writeheader()
        n = 0
        for i, s in enumerate(structures, start=1):
            city3 = (s["city"] or "UNK")[:3].upper().replace(" ", "")
            w.writerow({
                "carrier_name": args.entity,
                "tadig": args.tadig,
                "mcc": args.mcc,
                "mnc": args.mnc,
                "site_id": f"{args.tadig}-{city3}-ASR{i:02d}",
                "site_name": s["address"] or s["city"],
                "community": s["city"],
                "state": s["state"],
                "country": "US",
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "height_agl_ft": s["height_agl_ft"],
                "height_agl_m": s["height_agl_m"],
                "structure_type": s["structure_type"],
                "asr_number": s["registration_number"],
                "uls_call_sign": "",
                "oe_study_number": s["faa_study"],
                "frn": "",
                "lac": "",
                "ci": "",
                "enb_id": "",
                "sector": "",
                "band": "",
                "technology": "",
                "status": "operational",
                "source": "FCC_ASR",
                "source_url": f"https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey={s['registration_number']}",
                "last_verified": today,
                "notes": f"owner_name={s['owner_name']}",
            })
            n += 1
    finally:
        if args.output != "-":
            out.close()
    log.info("wrote %d rows to %s", n, args.output)


if __name__ == "__main__":
    main()
