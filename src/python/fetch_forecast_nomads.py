#!/usr/bin/env python3
"""
fetch_forecast_nomads.py — Real-time 168-hour weather forecast via NOAA NOMADS

Fetches a 168-hour (7-day) GFS weather forecast for any [lat, lon] coordinate
directly from NOAA's public NOMADS server. No account or token needed.

Uses wgrib2 to extract values at the exact lat/lon from GRIB2 files.
Saves results to SQLite using the existing repo database schema.

Usage:
  python3 fetch_forecast_nomads.py --lat 37.87 --lon -122.26
  python3 fetch_forecast_nomads.py --lat 37.87 --lon -122.26 --retrain
"""

import os
import sys
import math
import time
import logging
import sqlite3
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

import requests

# ── Path setup ────────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

try:
    from coordinate_utils import REGION_COORDINATES
except ImportError:
    print("ERROR: coordinate_utils.py not found. Run from inside src/python/")
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────

# GFS forecast hours: every 6h up to 168h (7 days)
FORECAST_HOURS = list(range(0, 174, 6))   # [0, 6, 12, ..., 168]

# Weather variables CarbonCast uses as ML features
VARIABLES = ["DSWRF", "UGRD", "VGRD", "TMP", "APCP"]

# NOMADS base URL for GFS 0.25-degree data
NOMADS_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

# Local directories
DEFAULT_DB_PATH      = str(SRC_DIR / "data" / "automation_state.db")
DEFAULT_DOWNLOAD_DIR = str(SRC_DIR / "downloaded_files" / "forecasts")
GRIB2_TEMP_DIR       = str(SRC_DIR / "data" / "grib2_temp")


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    logs_dir = SRC_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(logs_dir / "fetch_forecast_nomads.log")),
        ],
    )
    return logging.getLogger("fetch_forecast_nomads")

logger = setup_logging()


# ── Helpers ───────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_latest_gfs_cycle() -> Tuple[str, str]:
    """
    GFS runs at 00, 06, 12, 18 UTC every day.
    Data takes ~4 hours to appear on NOMADS after the run starts.
    We back off one cycle to guarantee the data is available.

    Returns:
        (date_str like '20260315', cycle like '06')
    """
    now = utcnow()
    cycle_hour = (now.hour // 6) * 6
    if (now.hour - cycle_hour) < 4:
        cycle_hour -= 6
    cycle_hour = cycle_hour % 24
    # If we backed off past midnight, use yesterday's date
    if cycle_hour < 0:
        cycle_hour += 24
        now = now - timedelta(days=1)
    date_str = now.strftime("%Y%m%d")
    return date_str, f"{cycle_hour:02d}"


def build_nomads_url(date_str: str, cycle: str, fhour: int, variable: str) -> str:
    """
    Build a NOMADS filter URL that downloads only the variable we need.
    The filter API returns a small subset of the full GRIB2 file.
    """
    fhour_str = f"f{fhour:03d}"
    filename  = f"gfs.t{cycle}z.pgrb2.0p25.{fhour_str}"
    url = (
        f"{NOMADS_BASE}"
        f"?dir=%2Fgfs.{date_str}%2F{cycle}%2Fatmos"
        f"&file={filename}"
        f"&var_{variable}=on"
        f"&all_lev=on"
    )
    return url


def download_grib2(url: str, filepath: str, retries: int = 3) -> bool:
    """
    Download a GRIB2 file from NOMADS with retry logic.
    Returns True if successful, False if all retries failed.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            # NOMADS returns an HTML error page for missing files
            if b"<html" in resp.content[:200].lower():
                logger.warning(f"    Got HTML page — file not ready yet.")
                return False
            if len(resp.content) < 100:
                logger.warning(f"    Response too small ({len(resp.content)} bytes) — skipping.")
                return False
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
        except requests.RequestException as e:
            logger.warning(f"    Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(5)
    return False


def extract_value_with_wgrib2(filepath: str, lat: float, lon: float) -> Optional[float]:
    """
    Use wgrib2 to extract the weather value at a specific lat/lon point.

    wgrib2 output looks like:
        1:0:lon=237.750000,lat=37.750000,val=305.12

    GFS uses 0-360 longitude (not -180 to 180), so we convert.
    """
    lon_gfs = lon % 360  # convert -122.26 → 237.74

    try:
        cmd    = ["wgrib2", filepath, "-lon", str(lon_gfs), str(lat)]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
        for line in output.strip().splitlines():
            if "val=" in line:
                value = line.split("val=")[-1].strip()
                if value.lower() == "nan":
                    return None
                return float(value)
    except subprocess.CalledProcessError as e:
        logger.warning(f"    wgrib2 error: {e}")
    except FileNotFoundError:
        logger.error(
            "wgrib2 not found. Install it with:\n"
            "  sudo apt-get install -y gcc gfortran make wget\n"
            "  wget https://www.ftp.cpc.ncep.noaa.gov/wd51we/wgrib2/wgrib2.tgz\n"
            "  tar -xzf wgrib2.tgz && cd grib2\n"
            "  export CC=gcc FC=gfortran && make\n"
            "  sudo cp wgrib2/wgrib2 /usr/local/bin/wgrib2"
        )
        sys.exit(1)
    return None


# ── Step 1: Map [lat, lon] to nearest region ──────────────────────────────────

def find_region_for_coordinates(lat: float, lon: float) -> Tuple[str, tuple]:
    """
    Find the best matching region bounding box for a given lat/lon point.
    Uses REGION_COORDINATES from coordinate_utils.py.
    """
    best_region   = None
    best_distance = float("inf")
    best_bbox     = None

    for region, (nlat, slat, wlon, elon) in REGION_COORDINATES.items():
        if slat <= lat <= nlat and wlon <= lon <= elon:
            cx = (nlat + slat) / 2
            cy = (wlon + elon) / 2
            d  = math.sqrt((lat - cx) ** 2 + (lon - cy) ** 2)
            if d < best_distance:
                best_distance = d
                best_region   = region
                best_bbox     = (nlat, slat, wlon, elon)

    if best_region is None:
        logger.warning("Point outside all regions — using nearest centre.")
        for region, (nlat, slat, wlon, elon) in REGION_COORDINATES.items():
            cx = (nlat + slat) / 2
            cy = (wlon + elon) / 2
            d  = math.sqrt((lat - cx) ** 2 + (lon - cy) ** 2)
            if d < best_distance:
                best_distance = d
                best_region   = region
                best_bbox     = (nlat, slat, wlon, elon)

    logger.info(
        f"Mapped lat={lat}, lon={lon} → region='{best_region}' "
        f"bbox={best_bbox}  distance={best_distance:.2f}°"
    )
    return best_region, best_bbox


# ── Step 2: Fetch 168h of data from NOMADS ───────────────────────────────────

def fetch_from_nomads(lat: float, lon: float) -> List[dict]:
    """
    Download 168 hours of GFS forecast data for a lat/lon point from NOMADS.

    For each forecast hour (0, 6, 12, ..., 168) and each variable
    (DSWRF, UGRD, VGRD, TMP, APCP):
      1. Download the GRIB2 file for that hour/variable from NOMADS
      2. Extract the value at lat/lon using wgrib2
      3. Delete the GRIB2 file to save disk space
      4. Append result to records list

    Returns:
        List of dicts with keys: forecast_hour, variable, value, lat, lon,
                                 cycle_date, cycle_hour, fetched_at
    """
    Path(GRIB2_TEMP_DIR).mkdir(parents=True, exist_ok=True)

    date_str, cycle = get_latest_gfs_cycle()
    fetched_at      = utcnow().isoformat()

    logger.info(f"GFS cycle: {date_str} {cycle}z")
    logger.info(f"Forecast hours: {FORECAST_HOURS[0]}h to {FORECAST_HOURS[-1]}h")
    logger.info(f"Variables: {VARIABLES}")

    records = []
    total   = len(FORECAST_HOURS) * len(VARIABLES)
    done    = 0

    for fhour in FORECAST_HOURS:
        for var in VARIABLES:
            done += 1
            logger.info(f"[{done}/{total}] hour={fhour:03d}h  var={var}")

            url      = build_nomads_url(date_str, cycle, fhour, var)
            filepath = str(Path(GRIB2_TEMP_DIR) / f"{var}_{fhour:03d}.grib2")

            # Download
            if not download_grib2(url, filepath):
                logger.warning(f"    Skipping — download failed.")
                continue

            # Extract value at our location
            value = extract_value_with_wgrib2(filepath, lat, lon)

            # Clean up immediately to save disk space
            try:
                os.remove(filepath)
            except OSError:
                pass

            if value is None:
                logger.warning(f"    Could not extract value.")
                continue

            logger.info(f"    Value: {value:.4f}")
            records.append({
                "forecast_hour": fhour,
                "variable":      var,
                "value":         value,
                "lat":           lat,
                "lon":           lon,
                "cycle_date":    date_str,
                "cycle_hour":    cycle,
                "fetched_at":    fetched_at,
            })

    logger.info(f"Fetched {len(records)}/{total} records successfully.")
    return records


# ── Step 3: Save to SQLite ────────────────────────────────────────────────────

def save_to_database(db_path: str, region: str, records: List[dict]) -> None:
    """
    Save forecast records to SQLite.

    Creates a 'weather_forecasts' table if it doesn't exist.
    Uses INSERT OR IGNORE so re-runs don't create duplicates.
    Also saves a summary row to rda_requests for tracking.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(db_path) as conn:

            # Create forecasts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_forecasts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat           REAL    NOT NULL,
                    lon           REAL    NOT NULL,
                    region        TEXT    NOT NULL,
                    cycle_date    TEXT    NOT NULL,
                    cycle_hour    TEXT    NOT NULL,
                    forecast_hour INTEGER NOT NULL,
                    variable      TEXT    NOT NULL,
                    value         REAL,
                    fetched_at    TEXT    NOT NULL,
                    UNIQUE(lat, lon, cycle_date, cycle_hour, forecast_hour, variable)
                )
            """)

            # Insert records
            conn.executemany("""
                INSERT OR IGNORE INTO weather_forecasts
                    (lat, lon, region, cycle_date, cycle_hour,
                     forecast_hour, variable, value, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    r["lat"], r["lon"], region,
                    r["cycle_date"], r["cycle_hour"],
                    r["forecast_hour"], r["variable"],
                    r["value"], r["fetched_at"],
                )
                for r in records
            ])

            conn.commit()

        logger.info(f"Saved {len(records)} records to {db_path}")

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")


# ── Step 4: Print summary ─────────────────────────────────────────────────────

def print_summary(records: List[dict]) -> None:
    """Print a clean table of results — this is what you show the mentor."""
    if not records:
        print("\nNo records fetched.")
        return

    print(f"\n{'='*55}")
    print(f"  168-hour forecast — {len(records)} data points fetched")
    print(f"  lat={records[0]['lat']}  lon={records[0]['lon']}")
    print(f"  GFS cycle: {records[0]['cycle_date']} {records[0]['cycle_hour']}z")
    print(f"{'='*55}")
    print(f"  {'Hour':>5}  {'Variable':<8}  {'Value':>14}")
    print(f"  {'-'*5}  {'-'*8}  {'-'*14}")
    for r in records[:20]:
        print(f"  {r['forecast_hour']:>5}  {r['variable']:<8}  {r['value']:>14.4f}")
    if len(records) > 20:
        print(f"  ... and {len(records) - 20} more rows in database")
    print(f"{'='*55}\n")


# ── Optional retraining ───────────────────────────────────────────────────────

def trigger_retraining(download_dir: str) -> None:
    candidates = [
        SRC_DIR / "retrain_model.py",
        SRC_DIR / "train_model.py",
    ]
    script = next((p for p in candidates if p.exists()), None)
    if script:
        logger.info(f"Running retraining: {script}")
        try:
            r = subprocess.run(
                [sys.executable, str(script), "--data-dir", download_dir],
                capture_output=True, text=True, timeout=3600,
            )
            if r.returncode == 0:
                logger.info("Retraining completed.")
            else:
                logger.error(f"Retraining failed:\n{r.stderr[-500:]}")
        except Exception as e:
            logger.error(f"Could not run retraining: {e}")
    else:
        logger.info(
            f"No retraining script found. "
            f"Create {SRC_DIR / 'retrain_model.py'} to enable auto-retraining."
        )


# ── Main pipeline ─────────────────────────────────────────────────────────────

def fetch_forecast(
    lat: float,
    lon: float,
    db_path: str      = DEFAULT_DB_PATH,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
    retrain: bool     = False,
) -> bool:
    """
    End-to-end 168-hour GFS forecast fetch for a given [lat, lon].

    1. Maps [lat, lon] to nearest known grid region
    2. Downloads 168h of GFS data from NOAA NOMADS (no auth needed)
    3. Extracts values at the exact lat/lon using wgrib2
    4. Saves all records to SQLite
    5. Prints a summary table
    6. Optionally triggers model retraining

    Returns True if at least some data was fetched, False on total failure.
    """
    logger.info("=" * 60)
    logger.info("fetch_forecast_nomads: starting")
    logger.info(f"  lat={lat}  lon={lon}  retrain={retrain}")
    logger.info("=" * 60)

    # 1 — region
    region, _ = find_region_for_coordinates(lat, lon)

    # 2+3 — fetch from NOMADS
    records = fetch_from_nomads(lat, lon)

    if not records:
        logger.error("No records fetched — pipeline failed.")
        return False

    # 4 — save to SQLite
    save_to_database(db_path, region, records)

    # 5 — print summary
    print_summary(records)

    # 6 — optional retrain
    if retrain:
        trigger_retraining(download_dir)

    logger.info("fetch_forecast_nomads: done")
    return True


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch 168-hour GFS weather forecast for [lat, lon] "
            "from NOAA NOMADS (no account needed) and save to SQLite."
        )
    )
    parser.add_argument("--lat",          type=float, required=True,
                        help="Latitude  (e.g. 37.87)")
    parser.add_argument("--lon",          type=float, required=True,
                        help="Longitude (e.g. -122.26)")
    parser.add_argument("--db-path",      type=str, default=DEFAULT_DB_PATH)
    parser.add_argument("--download-dir", type=str, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--retrain",      action="store_true",
                        help="Trigger model retraining after download")
    args = parser.parse_args()

    ok = fetch_forecast(
        lat=args.lat, lon=args.lon,
        db_path=args.db_path, download_dir=args.download_dir,
        retrain=args.retrain,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
