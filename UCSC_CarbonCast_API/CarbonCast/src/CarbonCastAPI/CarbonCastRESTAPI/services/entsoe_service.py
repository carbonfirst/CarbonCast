"""
ENTSO-E (European Network of Transmission System Operators) ingestion.

Pulls actual generation per production type from ENTSO-E for European
control areas and writes hourly rows into EmissionActual using the same
schema as the EIA service. This complements EIA (US) so the daily
ingestion task can keep both regions current.

Requires ENTSOE_API_TOKEN (or legacy ENTSOE_API_KEY) env var. Uses
entsoe-py if available; falls back to a no-op (with logged error) so the
rest of the pipeline keeps running.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ENTSO-E generation type code -> our internal source name.
# Only codes that map onto EIA's source taxonomy are kept; everything else
# is bucketed into "other" so downstream emission factors stay consistent.
ENTSOE_PSR_TYPE_TO_SOURCE = {
    "B01": "biomass",
    "B02": "coal",       # Fossil Brown coal/Lignite
    "B03": "coal",       # Fossil Coal-derived gas -> coal proxy
    "B04": "nat_gas",    # Fossil Gas
    "B05": "coal",       # Fossil Hard coal
    "B06": "oil",        # Fossil Oil
    "B07": "oil",        # Fossil Oil shale
    "B08": "coal",       # Fossil Peat
    "B09": "geothermal",
    "B10": "hydro",      # Hydro Pumped Storage
    "B11": "hydro",      # Hydro Run-of-river
    "B12": "hydro",      # Hydro Water Reservoir
    "B13": "other",      # Marine
    "B14": "nuclear",
    "B15": "other",      # Other renewable
    "B16": "solar",
    "B17": "other",      # Waste
    "B18": "wind",       # Wind Offshore
    "B19": "wind",       # Wind Onshore
    "B20": "other",
    "B25": "other",
}

# Region code (our internal) -> ENTSO-E control area EIC code.
# Trimmed to the regions we already serve in `consts.US_region_codes`.
ENTSOE_AREA_CODES = {
    "AT": "10YAT-APG------L",
    "BE": "10YBE----------2",
    "BG": "10YCA-BULGARIA-R",
    "CH": "10YCH-SWISSGRIDZ",
    "CZ": "10YCZ-CEPS-----N",
    "DE": "10Y1001A1001A83F",
    "DK": "10Y1001A1001A65H",
    "EE": "10Y1001A1001A39I",
    "ES": "10YES-REE------0",
    "FI": "10YFI-1--------U",
    "FR": "10YFR-RTE------C",
    "GB": "10YGB----------A",
    "GR": "10YGR-HTSO-----Y",
    "HR": "10YHR-HEP------M",
    "HU": "10YHU-MAVIR----U",
    "IE": "10YIE-1001A00010",
    "IT": "10YIT-GRTN-----B",
    "LT": "10YLT-1001A0008Q",
    "LV": "10YLV-1001A00074",
    "NL": "10YNL----------L",
    "PL": "10YPL-AREA-----S",
    "PT": "10YPT-REN------W",
    "RS": "10YCS-SERBIATSOV",
    "SE": "10YSE-1--------K",
    "SI": "10YSI-ELES-----O",
    "SK": "10YSK-SEPS-----K",
}

DIRECT_EMISSION_FACTORS = {
    "biomass": 0,
    "coal": 760,
    "geothermal": 0,
    "hydro": 0,
    "nat_gas": 370,
    "nuclear": 0,
    "oil": 406,
    "other": 575,
    "solar": 0,
    "unknown": 575,
    "wind": 0,
}

LIFECYCLE_EMISSION_FACTORS = {
    "biomass": 230,
    "coal": 820,
    "geothermal": 38,
    "hydro": 24,
    "nat_gas": 490,
    "nuclear": 12,
    "oil": 650,
    "other": 700,
    "solar": 45,
    "unknown": 700,
    "wind": 11,
}


def _calculate_carbon_intensity(sources, factors):
    total_generation = 0.0
    total_emissions = 0.0
    for source, generation in sources.items():
        if generation is None:
            continue
        try:
            value = float(generation)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        total_generation += value
        total_emissions += value * factors.get(source, factors["unknown"])
    if total_generation <= 0:
        return None
    return total_emissions / total_generation


def _coerce_datetime(value):
    """Normalize an ENTSO-E pandas Timestamp / datetime into tz-aware UTC."""
    if value is None:
        return None
    if hasattr(value, 'to_pydatetime'):
        value = value.to_pydatetime()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def fetch_and_store_entsoe_data(target_date: str) -> dict:
    """
    Fetch generation per production type for `target_date` (YYYY-MM-DD)
    across all configured ENTSO-E control areas and upsert into
    EmissionActual.
    """
    from CarbonCastRESTAPI.models import EmissionActual

    api_key = os.environ.get("ENTSOE_API_TOKEN", "") or os.environ.get("ENTSOE_API_KEY", "")
    if not api_key:
        logger.warning("ENTSOE_API_TOKEN not set; skipping ENTSO-E ingestion")
        return {
            "status": "waiting_on_credential",
            "inserted": 0,
            "updated": 0,
            "errors": [],
            "regions_ok": 0,
            "regions_failed": 0,
        }

    try:
        import pandas as pd  # noqa: F401  (used by entsoe-py)
        from entsoe import EntsoePandasClient
    except ImportError:
        logger.exception("entsoe-py not installed; skipping ENTSO-E ingestion")
        return {
            "status": "failed",
            "inserted": 0,
            "updated": 0,
            "errors": [{"region": "*", "error": "entsoe-py not installed"}],
            "regions_ok": 0,
            "regions_failed": 1,
        }

    import pandas as pd

    client = EntsoePandasClient(api_key=api_key)
    start = pd.Timestamp(f"{target_date}T00:00", tz="UTC")
    end = start + pd.Timedelta(days=1)

    inserted = 0
    updated = 0
    errors = []
    regions_ok = 0

    for region_code, area_code in ENTSOE_AREA_CODES.items():
        try:
            df = client.query_generation(area_code, start=start, end=end, psr_type=None)
            if df is None or df.empty:
                continue

            # ENTSO-E returns a multi-index column DataFrame (psr_type, direction).
            # Flatten to one column per psr_type using "Actual Aggregated" generation.
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df = df.xs("Actual Aggregated", axis=1, level=-1)
                except KeyError:
                    df = df.droplevel(-1, axis=1)

            # Resample raw resolution (15min/30min/60min) into hourly means in MW.
            df = df.resample("H").mean()

            for ts, row in df.iterrows():
                ts_utc = _coerce_datetime(ts)
                if ts_utc is None:
                    continue

                sources = {}
                for psr, value in row.items():
                    source_name = ENTSOE_PSR_TYPE_TO_SOURCE.get(str(psr), "other")
                    if value is None or (isinstance(value, float) and value != value):
                        continue
                    sources[source_name] = sources.get(source_name, 0.0) + max(float(value), 0.0)

                if not sources:
                    continue

                lifecycle = _calculate_carbon_intensity(sources, LIFECYCLE_EMISSION_FACTORS)
                direct = _calculate_carbon_intensity(sources, DIRECT_EMISSION_FACTORS)

                _, created = EmissionActual.objects.update_or_create(
                    region=region_code,
                    ts=ts_utc,
                    defaults={
                        "lifecycle": lifecycle,
                        "direct": direct,
                        "data": {
                            **sources,
                            "creation_time (UTC)": datetime.utcnow().isoformat(),
                            "version": "entsoe_api",
                            "carbon_intensity_avg_lifecycle": lifecycle,
                            "carbon_intensity_avg_direct": direct,
                            "carbon_intensity_unit": "gCO2eg/kWh",
                            "source": "entsoe",
                        },
                        "source_file": f"entsoe_api_{target_date}",
                    },
                )
                if created:
                    inserted += 1
                else:
                    updated += 1
            regions_ok += 1

        except Exception as exc:
            logger.exception("ENTSO-E fetch failed for %s on %s", region_code, target_date)
            errors.append({"region": region_code, "error": str(exc)[:500]})

    if errors and regions_ok == 0:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "regions_ok": regions_ok,
        "regions_failed": len(errors),
    }
