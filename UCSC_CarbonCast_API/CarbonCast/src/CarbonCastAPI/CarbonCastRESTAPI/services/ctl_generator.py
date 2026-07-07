"""
Generates weekly .ctl control files for the RDA automation tool.

Reads region bounding boxes from the automation tool's automation_config.json
and writes .ctl files with dates covering the next 7 days.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Product vocabulary mirrors the automation tool's proven control files
# (control_files/CISO_*.ctl) and NCAR's ds084.1 metadata:
# - Instantaneous fields (TMP/DPT, U GRD/V GRD) exist as
#   "Analysis" + "N-hour Forecast" products every 3 hours.
# - Flux/accumulation fields are NOT plain forecasts: DSWRF only exists as
#   "N-hour Average (initial+A to initial+B)" and A PCP as
#   "N-hour Accumulation (...)" products. Requesting "3-hour Forecast" for
#   them makes NCAR's subset job fail server-side with status Error.
# - Param names contain spaces on the API side: "U GRD", "A PCP".


def _forecast_products(horizon_hours=168, step=3):
    products = ['Analysis']
    products += [f'{h}-hour Forecast' for h in range(step, horizon_hours + 1, step)]
    return '/'.join(products)


def _interval_products(kind, horizon_hours=168):
    """DSWRF/APCP product list: alternating 3h and 6h windows, e.g.
    '3-hour Average (initial+0 to initial+3)/6-hour Average (initial+0 to initial+6)/...'
    """
    products = []
    for start in range(0, horizon_hours, 6):
        products.append(f'3-hour {kind} (initial+{start} to initial+{start + 3})')
        products.append(f'6-hour {kind} (initial+{start} to initial+{start + 6})')
    return '/'.join(products)


WEATHER_VARIABLES = {
    'temp': {'param': 'TMP/DPT', 'level': 'HTGL:2',
             'products': _forecast_products()},
    'wind': {'param': 'U GRD/V GRD', 'level': 'HTGL:10',
             'products': _forecast_products()},
    'dswrf': {'param': 'DSWRF', 'level': 'SFC:0',
              'products': _interval_products('Average')},
    'rain': {'param': 'A PCP', 'level': 'SFC:0',
             'products': _interval_products('Accumulation')},
}


def _load_regions():
    """Load region bounding boxes from the automation tool config if available."""
    config_path = os.environ.get('RDA_CONFIG_PATH', '')
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        return config.get('regions', {})

    # Fallback: a minimal set of key regions
    return {
        'CISO': {'nlat': 42.0, 'slat': 32.0, 'wlon': -124.75, 'elon': -113.5},
        'PJM': {'nlat': 42.0, 'slat': 36.5, 'wlon': -83.5, 'elon': -74.0},
        'MISO': {'nlat': 49.0, 'slat': 29.0, 'wlon': -104.0, 'elon': -82.0},
        'ERCO': {'nlat': 36.5, 'slat': 25.8, 'wlon': -106.65, 'elon': -93.5},
        'ISNE': {'nlat': 47.5, 'slat': 40.5, 'wlon': -73.75, 'elon': -66.9},
    }


def generate_weekly_ctl_files(output_dir: str):
    """Write .ctl files covering recent GFS init cycles for all regions/variables.

    ds084.1 is an *archive* of past model runs: datetype=init date ranges in
    the future match nothing (the old today/+7d window returned empty
    requests). Instead request the last 2 days of init cycles — each cycle
    carries forecast products out to 168h, so yesterday's 00Z run already
    covers the whole coming week.
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=2)).strftime('%Y%m%d0000')
    end = now.strftime('%Y%m%d%H00')
    date_line = f"{start}/to/{end}"

    regions = _load_regions()
    files_written = 0

    for region_code, bbox in regions.items():
        # automation_config.json stores each region's bounding box as
        # "coordinates": [nlat, slat, wlon, elon]; the built-in fallback
        # uses explicit nlat/slat/wlon/elon keys.
        coords = bbox.get('coordinates') if isinstance(bbox, dict) else None
        if coords and len(coords) == 4:
            nlat, slat, wlon, elon = coords
        else:
            nlat = bbox.get('nlat', bbox.get('n_lat', 0))
            slat = bbox.get('slat', bbox.get('s_lat', 0))
            wlon = bbox.get('wlon', bbox.get('w_lon', 0))
            elon = bbox.get('elon', bbox.get('e_lon', 0))

        for var_name, var_cfg in WEATHER_VARIABLES.items():
            filename = f"{region_code}_{var_name}_control.ctl"
            filepath = os.path.join(output_dir, filename)
            content = (
                f"dataset=ds084.1\n"
                f"date={date_line}\n"
                f"datetype=init\n"
                f"param={var_cfg['param']}\n"
                f"level={var_cfg['level']}\n"
                f"nlat={nlat}\n"
                f"slat={slat}\n"
                f"wlon={wlon}\n"
                f"elon={elon}\n"
                f"product={var_cfg['products']}\n"
            )
            with open(filepath, 'w') as f:
                f.write(content)
            files_written += 1

    logger.info("Wrote %d control files to %s", files_written, output_dir)
    return files_written
