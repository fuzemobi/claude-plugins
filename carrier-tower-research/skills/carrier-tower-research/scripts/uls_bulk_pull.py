#!/usr/bin/env python3
"""
FCC ULS bulk pull — filters the weekly ULS dump for a given licensee and emits
per-site rows in the tower_master CSV format.

Usage:
    python uls_bulk_pull.py --entity "AT&T Mobility" --tadig USACG --mcc 310 --mnc 410
    python uls_bulk_pull.py --frn 0001234567 --tadig USACG --mcc 310 --mnc 410
    python uls_bulk_pull.py --entity "New Cingular Wireless" --service cell,market --tadig USACG --mcc 310 --mnc 410

Services (one or more, comma-separated):
    cell      — l_cell.zip (Part 22 Cellular)
    market    — l_market.zip (700MHz, PCS, AWS, H-block — where modern LTE licenses live)
    micro     — l_micro.zip (microwave backhaul)
    LMpriv    — l_LMpriv.zip (Private Land Mobile)
    paging    — l_paging.zip
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

ULS_BASE = "https://data.fcc.gov/download/pub/uls/complete"
SERVICE_URLS = {
    "cell": f"{ULS_BASE}/l_cell.zip",
    "market": f"{ULS_BASE}/l_market.zip",
    "micro": f"{ULS_BASE}/l_micro.zip",
    "LMpriv": f"{ULS_BASE}/l_LMpriv.zip",
    "paging": f"{ULS_BASE}/l_paging.zip",
    "coast": f"{ULS_BASE}/l_coast.zip",
}

# Pipe-delimited column positions (0-indexed) for the relevant ULS files.
# Source: FCC ULS public access data dictionary
# https://www.fcc.gov/wireless/data/public-access-files-database-downloads

HD_COLS = {
    "record_type": 0, "unique_system_id": 1, "uls_file_number": 2, "ebf_number": 3,
    "call_sign": 4, "license_status": 5, "radio_service_code": 6, "grant_date": 7,
    "expired_date": 8, "cancellation_date": 9,
}
EN_COLS = {
    "record_type": 0, "unique_system_id": 1, "uls_file_number": 2, "ebf_number": 3,
    "call_sign": 4, "entity_type": 5, "licensee_id": 6, "entity_name": 7,
    "first_name": 8, "mi": 9, "last_name": 10, "suffix": 11, "phone": 12,
    "fax": 13, "email": 14, "street_address": 15, "city": 16, "state": 17,
    "zip_code": 18, "po_box": 19, "attention_line": 20, "sgin": 21, "frn": 22,
}
LO_COLS = {
    "record_type": 0, "unique_system_id": 1, "uls_file_number": 2, "ebf_number": 3,
    "call_sign": 4, "location_action_performed": 5, "location_type_code": 6,
    "location_class_code": 7, "location_number": 8, "site_status": 9,
    "corresponding_fixed_location": 10, "location_address": 11,
    "location_city": 12, "location_county": 13, "location_state": 14,
    "radius_of_operation": 15, "area_of_operation_code": 16,
    "clearance_indicator": 17, "ground_elevation": 18,
    "lat_degrees": 19, "lat_minutes": 20, "lat_seconds": 21, "lat_direction": 22,
    "long_degrees": 23, "long_minutes": 24, "long_seconds": 25, "long_direction": 26,
    "max_lat_degrees": 27, "max_lat_minutes": 28, "max_lat_seconds": 29, "max_lat_direction": 30,
    "max_long_degrees": 31, "max_long_minutes": 32, "max_long_seconds": 33, "max_long_direction": 34,
    "nepa": 35, "quiet_zone_notification_date": 36,
    "tower_registration_number": 37, "height_of_support_structure": 38,
    "overall_height_of_structure": 39, "structure_type": 40,
    "airport_id": 41, "location_name": 42, "units_hand_held": 43, "units_mobile": 44,
    "units_temp_fixed": 45, "units_aircraft": 46, "units_itinerant": 47,
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


def download_zip(url: str, cache_dir: Path) -> Path:
    """Download ULS zip to cache_dir. Returns path to downloaded file."""
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
    """Yield rows (list of str) from <dat_name> inside zip_path. Pipe-delimited."""
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


def load_entities(zip_path: Path, entity_pat: str | None, frn: str | None) -> set[str]:
    """Return set of unique_system_id whose EN record matches the filter."""
    matched = set()
    pat = entity_pat.upper() if entity_pat else None
    for row in read_dat(zip_path, "EN.dat"):
        if len(row) <= EN_COLS["frn"]:
            continue
        usid = row[EN_COLS["unique_system_id"]]
        name = row[EN_COLS["entity_name"]].upper()
        row_frn = row[EN_COLS["frn"]]
        if frn and row_frn == frn:
            matched.add(usid)
        elif pat and pat in name:
            matched.add(usid)
    log.info("matched %d entities", len(matched))
    return matched


def load_active_licenses(zip_path: Path, usids: set[str]) -> dict[str, dict]:
    """Return {unique_system_id: {call_sign, status, service}} for active licenses."""
    out = {}
    for row in read_dat(zip_path, "HD.dat"):
        if len(row) <= HD_COLS["radio_service_code"]:
            continue
        usid = row[HD_COLS["unique_system_id"]]
        if usid not in usids:
            continue
        status = row[HD_COLS["license_status"]]
        if status != "A":
            continue
        out[usid] = {
            "call_sign": row[HD_COLS["call_sign"]],
            "status": status,
            "service": row[HD_COLS["radio_service_code"]],
        }
    log.info("active licenses: %d", len(out))
    return out


def load_locations(zip_path: Path, usids: set[str]) -> list[dict]:
    """Return list of location dicts for the given unique_system_ids."""
    out = []
    for row in read_dat(zip_path, "LO.dat"):
        if len(row) <= LO_COLS["structure_type"]:
            continue
        usid = row[LO_COLS["unique_system_id"]]
        if usid not in usids:
            continue
        lat = dms_to_decimal(
            row[LO_COLS["lat_degrees"]], row[LO_COLS["lat_minutes"]],
            row[LO_COLS["lat_seconds"]], row[LO_COLS["lat_direction"]],
        )
        lon = dms_to_decimal(
            row[LO_COLS["long_degrees"]], row[LO_COLS["long_minutes"]],
            row[LO_COLS["long_seconds"]], row[LO_COLS["long_direction"]],
        )
        if lat is None or lon is None:
            continue
        try:
            height_m = float(row[LO_COLS["overall_height_of_structure"]] or 0)
        except ValueError:
            height_m = 0
        out.append({
            "usid": usid,
            "location_number": row[LO_COLS["location_number"]],
            "address": row[LO_COLS["location_address"]],
            "city": row[LO_COLS["location_city"]],
            "state": row[LO_COLS["location_state"]],
            "latitude": lat,
            "longitude": lon,
            "structure_type": row[LO_COLS["structure_type"]],
            "height_agl_m": height_m,
            "height_agl_ft": round(height_m * 3.28084, 1) if height_m else "",
            "asr_number": row[LO_COLS["tower_registration_number"]],
        })
    log.info("locations: %d", len(out))
    return out


def process_service(
    service: str, entity: str | None, frn: str | None, cache_dir: Path,
    tadig: str, mcc: str, mnc: str, entity_frn: dict[str, str],
) -> list[dict]:
    url = SERVICE_URLS.get(service)
    if not url:
        log.warning("unknown service: %s", service)
        return []
    zip_path = download_zip(url, cache_dir)
    usids = load_entities(zip_path, entity, frn)
    if not usids:
        log.warning("no entities matched in %s", service)
        return []

    # Capture FRN from matched entities for output.
    for row in read_dat(zip_path, "EN.dat"):
        if len(row) <= EN_COLS["frn"]:
            continue
        usid = row[EN_COLS["unique_system_id"]]
        if usid in usids:
            entity_frn[usid] = row[EN_COLS["frn"]]

    hd = load_active_licenses(zip_path, usids)
    if not hd:
        return []
    locations = load_locations(zip_path, set(hd.keys()))

    today = date.today().isoformat()
    site_num = 0
    rows = []
    for loc in locations:
        usid = loc["usid"]
        hd_row = hd.get(usid, {})
        site_num += 1
        city3 = (loc["city"] or "UNK")[:3].upper().replace(" ", "")
        rows.append({
            "carrier_name": entity or f"FRN {frn}",
            "tadig": tadig,
            "mcc": mcc,
            "mnc": mnc,
            "site_id": f"{tadig}-{city3}-{site_num:02d}",
            "site_name": loc["address"] or loc["city"],
            "community": loc["city"],
            "state": loc["state"],
            "country": "US",
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "height_agl_ft": loc["height_agl_ft"],
            "height_agl_m": loc["height_agl_m"],
            "structure_type": loc["structure_type"],
            "asr_number": loc["asr_number"] or "",
            "uls_call_sign": hd_row.get("call_sign", ""),
            "oe_study_number": "",
            "frn": entity_frn.get(usid, ""),
            "lac": "",
            "ci": "",
            "enb_id": "",
            "sector": "",
            "band": "",
            "technology": "LTE" if service == "market" else "",
            "status": "operational",
            "source": "FCC_ULS",
            "source_url": f"https://wireless2.fcc.gov/UlsApp/UlsSearch/license.jsp?licKey={usid}",
            "last_verified": today,
            "notes": f"uls_service={service};location_num={loc['location_number']}",
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", help="Licensee entity name substring (case-insensitive)")
    ap.add_argument("--frn", help="FRN (preferred over --entity when known)")
    ap.add_argument("--tadig", required=True, help="Output TADIG code (e.g., USACG)")
    ap.add_argument("--mcc", required=True, help="Output MCC")
    ap.add_argument("--mnc", required=True, help="Output MNC")
    ap.add_argument("--service", default="market,cell,micro",
                    help="Comma-separated ULS services to pull (default: market,cell,micro)")
    ap.add_argument("--output", default="-", help="Output CSV path (default: stdout)")
    ap.add_argument("--cache-dir", default=None, help="Cache directory for downloaded zips")
    args = ap.parse_args()

    if not args.entity and not args.frn:
        ap.error("must provide --entity or --frn")

    cache = Path(args.cache_dir) if args.cache_dir else Path(tempfile.gettempdir()) / "uls_cache"
    cache.mkdir(parents=True, exist_ok=True)

    all_rows = []
    entity_frn = {}
    for svc in args.service.split(","):
        svc = svc.strip()
        if not svc:
            continue
        log.info("=== service: %s ===", svc)
        rows = process_service(svc, args.entity, args.frn, cache, args.tadig,
                               args.mcc, args.mnc, entity_frn)
        all_rows.extend(rows)

    if not all_rows:
        log.warning("no rows produced; try different --entity or verify FRN")
        sys.exit(1)

    fieldnames = list(all_rows[0].keys())
    out = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    try:
        w = csv.DictWriter(out, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    finally:
        if args.output != "-":
            out.close()
    log.info("wrote %d rows to %s", len(all_rows), args.output)


if __name__ == "__main__":
    main()
