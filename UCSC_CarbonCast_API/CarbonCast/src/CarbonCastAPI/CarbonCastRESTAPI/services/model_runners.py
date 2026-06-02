"""
Pluggable forecasting model runners.

CarbonCast: 6-month historical lookback, the heavier two-tier neural pipeline.
LiteCast:   1-2 week historical lookback, a lightweight regressor-style baseline.

Both runners share the same interface:
    runner = make_runner(name)
    forecast_rows = runner.run(region, emissions, weather_rows, forecast_start, horizon)

`forecast_rows` is a list of dicts with keys (ts, forecast_type, value, data) ready
to upsert into Forecast96.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, List

logger = logging.getLogger(__name__)

ENERGY_SOURCES = ("coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "other")


@dataclass
class ForecastRow:
    ts: object
    forecast_type: str
    value: float
    data: dict


class BaseModelRunner:
    """Common helpers shared by all model runners."""

    name: str = "base"
    lookback_days: int = 30

    def run(self, region, emissions, weather_rows, forecast_start, horizon):
        raise NotImplementedError

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _average(values):
        numeric = [v for v in (BaseModelRunner._coerce_float(x) for x in values) if v is not None]
        if not numeric:
            return 0.0
        return sum(numeric) / len(numeric)

    @staticmethod
    def _average_source_mix(rows):
        averages = {}
        for source in ENERGY_SOURCES:
            values = [(row.data or {}).get(source) for row in rows]
            averages[source] = BaseModelRunner._average(values)
        return averages

    def _filter_lookback(self, emissions, forecast_start):
        cutoff = forecast_start - timedelta(days=self.lookback_days)
        return [row for row in emissions if row.ts >= cutoff] or list(emissions)


class CarbonCastRunner(BaseModelRunner):
    """
    CarbonCast (heavyweight) — uses up to 6 months of history. The actual ML
    execution path is owned by `services.retraining_service` so that the
    DB-baseline forecast continues to be written even when the legacy ML
    artifacts are unavailable. This runner therefore implements a 6-month
    hourly-average baseline that is suitable as a fallback or a v1 forecast.
    """

    name = "carboncast"
    lookback_days = 180

    def run(self, region, emissions, weather_rows, forecast_start, horizon):
        recent = self._filter_lookback(emissions, forecast_start)
        return _hourly_average_forecast(region, recent, weather_rows, forecast_start, horizon, model_version="carboncast-baseline")


class LiteCastRunner(BaseModelRunner):
    """
    LiteCast (lightweight) — only needs ~2 weeks of history. Cheaper to retrain
    so it doubles as a low-data fallback for new regions and as a quick smoke
    test for the pipeline. Same interface as CarbonCast so the orchestrator
    can swap them transparently.
    """

    name = "litecast"
    lookback_days = 14

    def run(self, region, emissions, weather_rows, forecast_start, horizon):
        recent = self._filter_lookback(emissions, forecast_start)
        return _hourly_average_forecast(region, recent, weather_rows, forecast_start, horizon, model_version="litecast-baseline-v1")


_MODEL_REGISTRY = {
    CarbonCastRunner.name: CarbonCastRunner,
    LiteCastRunner.name: LiteCastRunner,
}


def make_runner(name: str) -> BaseModelRunner:
    cls = _MODEL_REGISTRY.get((name or "").lower(), CarbonCastRunner)
    return cls()


def select_runner_for_region(region: str, emissions) -> BaseModelRunner:
    """
    Pick CarbonCast when there's enough history (>=60 days), LiteCast otherwise.
    Override per region with PIPELINE_MODEL_<REGION>=carboncast|litecast or
    globally with PIPELINE_DEFAULT_MODEL.
    """
    forced = os.environ.get(f"PIPELINE_MODEL_{region.upper()}") or os.environ.get("PIPELINE_DEFAULT_MODEL")
    if forced:
        return make_runner(forced)

    if not emissions:
        return LiteCastRunner()

    earliest = min(row.ts for row in emissions)
    latest = max(row.ts for row in emissions)
    span_days = (latest - earliest).days
    return CarbonCastRunner() if span_days >= 60 else LiteCastRunner()


def _hourly_average_forecast(region, emissions, weather_rows, forecast_start, horizon, model_version) -> List[ForecastRow]:
    """Shared baseline producer that both runners use."""
    if not emissions:
        return []

    rows: List[ForecastRow] = []
    weather_lookup = _weather_lookup(weather_rows)

    for hour_index in range(horizon):
        target = forecast_start + timedelta(hours=hour_index)
        same_hour = [row for row in emissions if row.ts.hour == target.hour] or emissions
        lifecycle = BaseModelRunner._average([row.lifecycle for row in same_hour])
        direct = BaseModelRunner._average([row.direct for row in same_hour])
        source_mix = BaseModelRunner._average_source_mix(same_hour)
        weather_at_target = weather_lookup.get(target)

        common = {
            "version": model_version,
            "model": model_version.split("-", 1)[0],
            "carbon_intensity_unit": "gCO2eg/kWh",
            "weather_aligned": weather_at_target is not None,
            "weather_variables": weather_at_target or {},
        }

        for forecast_type, value in (("lifecycle", lifecycle), ("direct", direct)):
            data = {**common, f"forecasted_avg_carbon_intensity_{forecast_type}": value}
            rows.append(ForecastRow(ts=target, forecast_type=forecast_type, value=value, data=data))

        energy_data = {**common}
        for source in ENERGY_SOURCES:
            energy_data[f"avg_{source}_production_forecast"] = source_mix.get(source, 0.0)
        rows.append(
            ForecastRow(
                ts=target,
                forecast_type="energy",
                value=sum(source_mix.values()),
                data=energy_data,
            )
        )

    return rows


def _weather_lookup(weather_rows: Iterable):
    lookup: dict = {}
    for row in weather_rows or []:
        bucket = lookup.setdefault(row.forecast_target, {})
        bucket[row.variable] = row.value
    return lookup
