"""
EIA API v2 energy data ingestion service.

Extracted from eiaParser.py and adapted to write directly to the Django ORM.
EIA API v2.1.6+ returns all data values as strings — explicit float() casts are
applied during parsing.
"""

import logging
import os
from datetime import datetime, timedelta

import numpy as np
import requests
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)

EIA_SOURCE_MAP = {
    "OTH": "other",
    "COL": "coal",
    "SUN": "solar",
    "NG": "nat_gas",
    "NUC": "nuclear",
    "WND": "wind",
    "WAT": "hydro",
    "OIL": "oil",
}

DIRECT_EMISSION_FACTORS = {
    "coal": 760,
    "biomass": 0,
    "nat_gas": 370,
    "geothermal": 0,
    "hydro": 0,
    "nuclear": 0,
    "oil": 406,
    "solar": 0,
    "unknown": 575,
    "other": 575,
    "wind": 0,
}

LIFECYCLE_EMISSION_FACTORS = {
    "coal": 820,
    "biomass": 230,
    "nat_gas": 490,
    "geothermal": 38,
    "hydro": 24,
    "nuclear": 12,
    "oil": 650,
    "solar": 45,
    "unknown": 700,
    "other": 700,
    "wind": 11,
}

EIA_BAL_AUTH_LIST = [
    "AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPC",
    "FPL", "GRID", "IPCO", "ISNE", "LDWP", "MISO", "NEVP", "NWMT",
    "NYIS", "PACE", "PACW", "PJM", "PSCO", "PSEI", "SC", "SCEG",
    "SOCO", "SPA", "SRP", "SWPP", "TIDC", "TVA", "WACM", "WALC",
]


def _safe_float(value):
    """EIA API v2.1.6+ returns values as strings. Convert safely."""
    if value is None or value == '':
        return None
    try:
        v = float(value)
        return v if v >= 0 else 0.0
    except (ValueError, TypeError):
        return None


def _calculate_carbon_intensity(sources: dict, factors: dict) -> float | None:
    """Return weighted carbon intensity in gCO2e/kWh for an hourly source mix."""
    total_generation = 0.0
    total_emissions = 0.0

    for source, generation in sources.items():
        if generation is None:
            continue
        try:
            generation_float = float(generation)
        except (TypeError, ValueError):
            continue
        if generation_float <= 0:
            continue
        total_generation += generation_float
        total_emissions += generation_float * factors.get(source, factors["unknown"])

    if total_generation <= 0:
        return None
    return total_emissions / total_generation


def _fetch_eia_page(ba: str, start_date: str, end_date: str, offset: int = 0):
    """Fetch a single page of EIA fuel-type data."""
    api_key = os.environ.get("EIA_API_KEY", "")
    if not api_key:
        raise ValueError("EIA_API_KEY environment variable is not set")

    url = (
        f"https://api.eia.gov/v2/electricity/rto/fuel-type-data/data"
        f"?api_key={api_key}"
        f"&frequency=hourly"
        f"&data[]=value"
        f"&facets[respondent][]={ba}"
        f"&sort[0][column]=period&sort[0][direction]=asc"
        f"&sort[1][column]=fueltype&sort[1][direction]=desc"
        f"&start={start_date}T00&end={end_date}T23"
        f"&offset={offset}&length=5000"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"]["data"]


def _fetch_all_pages(ba: str, start_date: str, end_date: str):
    """Fetch all pages for a BA and date range."""
    all_data = []
    offset = 0
    while True:
        page = _fetch_eia_page(ba, start_date, end_date, offset)
        all_data.extend(page)
        if len(page) < 5000:
            break
        offset += 5000
    return all_data


def _parse_hourly_records(data: list, region: str):
    """
    Parse raw EIA response into per-hour dicts ready for update_or_create.

    Returns a list of dicts with keys: region, ts, data_blob.
    """
    hourly: dict[str, dict] = {}

    for row in data:
        period = row.get("period", "")
        fuel = row.get("fueltype", "")
        value = _safe_float(row.get("value"))

        parts = period.split("T")
        if len(parts) != 2:
            continue
        date_str, hour_str = parts
        ts_str = f"{date_str} {hour_str.zfill(2)}:00:00"

        if ts_str not in hourly:
            hourly[ts_str] = {}

        source_name = EIA_SOURCE_MAP.get(fuel)
        if source_name:
            hourly[ts_str][source_name] = value

    records = []
    for ts_str, sources in sorted(hourly.items()):
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            dt = make_aware(dt)
        except Exception:
            continue

        records.append({
            'region': region,
            'ts': dt,
            'data': sources,
            'lifecycle': _calculate_carbon_intensity(sources, LIFECYCLE_EMISSION_FACTORS),
            'direct': _calculate_carbon_intensity(sources, DIRECT_EMISSION_FACTORS),
        })
    return records


def _interpolate_value(*candidates):
    """Average of non-None values, matching the original cleanElectricityProductionDataFromEIA logic."""
    valid = [c for c in candidates if c is not None and not np.isnan(c)]
    return sum(valid) / len(valid) if valid else 0.0


def fetch_and_store_eia_data(target_date: str) -> dict:
    """
    Fetch energy data for all BAs for the given date and store in EmissionActual.

    Returns summary dict with inserted/updated counts.
    """
    from CarbonCastRESTAPI.models import EmissionActual

    inserted = 0
    updated = 0
    errors = 0

    for ba in EIA_BAL_AUTH_LIST:
        try:
            data = _fetch_all_pages(ba, target_date, target_date)
            records = _parse_hourly_records(data, ba)

            for rec in records:
                _, created = EmissionActual.objects.update_or_create(
                    region=rec['region'],
                    ts=rec['ts'],
                    defaults={
                        'lifecycle': rec['lifecycle'],
                        'direct': rec['direct'],
                        'data': {
                            **rec['data'],
                            'creation_time (UTC)': datetime.utcnow().isoformat(),
                            'version': 'eia_api_v2',
                            'carbon_intensity_avg_lifecycle': rec['lifecycle'],
                            'carbon_intensity_avg_direct': rec['direct'],
                            'carbon_intensity_unit': 'gCO2eg/kWh',
                            'source': 'eia',
                        },
                        'source_file': f'eia_api_{target_date}',
                    },
                )
                if created:
                    inserted += 1
                else:
                    updated += 1

        except Exception:
            logger.exception("Error fetching EIA data for %s on %s", ba, target_date)
            errors += 1

    return {'inserted': inserted, 'updated': updated, 'errors': errors}
