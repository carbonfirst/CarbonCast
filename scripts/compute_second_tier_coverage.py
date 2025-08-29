"""Helper to compute feasible and recommended NUM_TEST_DAYS / coverage for second-tier forecasts.

Usage:
  python scripts/compute_second_tier_coverage.py <config_path> <REGION> [--target-coverage-days N]
  python scripts/compute_second_tier_coverage.py src/secondTierConfig.json AECI --target-coverage-days 60

Outputs:
  * Overlap date range between emissions & forecast feature files (after optional START/END bounds)
  * Total available days & hours
  * Current config-derived: NUM_TEST_DAYS, horizonDays (=PREDICTION_WINDOW_HOURS/24), coverageDays (=NUM_TEST_DAYS + horizonDays - 1)
  * Dataset day allocation (train / val / test) and remaining training days
  * Theoretical maximum NUM_TEST_DAYS (leaving zero training days) & a recommended range preserving a training buffer
  * If --target-coverage-days is supplied, prints required NUM_TEST_DAYS to reach it plus feasibility check

Formulae:
  horizonDays = PREDICTION_WINDOW_HOURS/24
  coverageDays = NUM_TEST_DAYS + (horizonDays - 1)
  daysConsumedByValAndTest = NUM_VAL_DAYS + NUM_TEST_DAYS + (horizonDays - 1)
  trainingDays = totalDays - daysConsumedByValAndTest
  theoreticalMaxTestDays = totalDays - NUM_VAL_DAYS - (horizonDays - 1)

Recommended Practice:
  Preserve at least MIN_TRAINING_DAYS (default 30) for model fitting. Adjust via env MIN_TRAINING_DAYS if desired.
"""

from __future__ import annotations

import argparse
import os
import math
import sys
import warnings
from dataclasses import dataclass
from typing import Optional

import pandas as pd

try:
    import json5 as json  # allows comments in config
except Exception:  # pragma: no cover
    import json  # fallback


@dataclass
class CoverageResult:
    region: str
    effective_start: pd.Timestamp
    effective_end: pd.Timestamp
    total_hours: int
    total_days: float
    horizon_days: int
    num_test_days: int
    num_val_days: int
    coverage_days: int
    training_days: float
    theoretical_max_test_days: int
    recommended_max_test_days: int
    recommended_max_coverage_days: int
    capacity_max_test_days: int
    capacity_limited: bool
    min_training_days_target: int

    def to_dict(self):  # convenient serialization
        return {k: getattr(self, k) for k in self.__dataclass_fields__.keys()}


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def compute_effective_overlap(emissions_path: str, forecast_path: str, start_bound: Optional[str], end_bound: Optional[str]):
    # Emissions file has column 'UTC time'; forecast file has 'datetime'
    emissions = pd.read_csv(emissions_path, parse_dates=['UTC time'], index_col='UTC time')
    forecast = pd.read_csv(forecast_path, parse_dates=['datetime'], index_col='datetime')
    emissions_start, emissions_end = emissions.index.min(), emissions.index.max()
    fc_start, fc_end = forecast.index.min(), forecast.index.max()
    overlap_start = max(emissions_start, fc_start)
    overlap_end = min(emissions_end, fc_end)
    if overlap_end < overlap_start:
        raise ValueError(
            f"No temporal overlap between emissions ({emissions_start}..{emissions_end}) and forecast features ({fc_start}..{fc_end})."
        )
    # Apply bounds if present
    if start_bound:
        overlap_start = max(overlap_start, pd.to_datetime(start_bound))
    if end_bound:
        overlap_end = min(overlap_end, pd.to_datetime(end_bound))
    if overlap_end < overlap_start:
        raise ValueError(
            f"START/END bounds clip out overlap completely (effective range {overlap_start}>{overlap_end}). Adjust bounds or remove them."
        )
    return overlap_start, overlap_end


def compute_coverage(config: dict, region: str, target_coverage: Optional[int] = None, min_training_days: int = 30) -> CoverageResult:
    # Shared config values
    num_test_days = int(config['NUM_TEST_DAYS'])
    num_val_days = int(config['NUM_VAL_DAYS'])
    horizon_hours = int(config['PREDICTION_WINDOW_HOURS'])
    horizon_days = horizon_hours // 24
    train_window_hours = int(config['TRAINING_WINDOW_HOURS'])
    region_cfg = config[region]
    # Use direct paths irrespective of cef type (files exist either way)
    emissions_path = region_cfg.get('DIRECT_CEF_IN_FILE_NAME') or region_cfg.get('LIFECYCLE_CEF_IN_FILE_NAME')
    forecast_path = region_cfg['FORECAST_IN_FILE_NAME']
    start_bound = config.get('START_DATE')
    end_bound = config.get('END_DATE')
    effective_start, effective_end = compute_effective_overlap(emissions_path, forecast_path, start_bound, end_bound)
    total_hours = int((effective_end - effective_start).total_seconds() // 3600) + 1  # inclusive
    total_days = total_hours / 24.0
    coverage_days = num_test_days + (horizon_days - 1)
    days_consumed = num_val_days + num_test_days + (horizon_days - 1)
    training_days = total_days - days_consumed
    theoretical_max_test_days = int(math.floor(total_days - num_val_days - (horizon_days - 1)))
    recommended_max_test_days = max(0, theoretical_max_test_days - min_training_days)
    recommended_max_coverage_days = recommended_max_test_days + (horizon_days - 1)
    # Capacity: weather feature rows must cover (val + test) * horizon_days blocks
    forecast_rows = len(pd.read_csv(forecast_path))
    total_feature_blocks = forecast_rows // horizon_hours
    # Ensure at least one training block remains: trainBlocks = total - val - test >= 1
    capacity_max_test_days = max(0, total_feature_blocks - num_val_days - 1)
    capacity_limited = num_test_days > capacity_max_test_days
    if capacity_limited:
        warnings.warn(
            f"NUM_TEST_DAYS={num_test_days} exceeds feature capacity ({forecast_rows} rows => max {capacity_max_test_days}). Reduce or regenerate feature file."
        )
    if capacity_max_test_days < recommended_max_test_days:
        recommended_max_test_days = capacity_max_test_days
        recommended_max_coverage_days = recommended_max_test_days + (horizon_days - 1)

    # Sanity checks
    if training_days < (train_window_hours / 24):
        warnings.warn(
            f"Training days ({training_days:.2f}) < training window days ({train_window_hours/24:.2f}). Increase overlap or reduce NUM_TEST_DAYS/NUM_VAL_DAYS."
        )

    if target_coverage is not None:
        required_test_days = target_coverage - (horizon_days - 1)
        feasible = required_test_days <= theoretical_max_test_days
        print(f"Target coverage days: {target_coverage}")
        print(f"Required NUM_TEST_DAYS: {required_test_days}")
        print(f"Feasible: {'YES' if feasible else 'NO (exceeds theoretical max)'}")
        if feasible and required_test_days > recommended_max_test_days:
            print(
                f"WARNING: Achieving this leaves < {min_training_days} training days (recommended). Proceed with caution."
            )

    return CoverageResult(
        region=region,
        effective_start=effective_start,
        effective_end=effective_end,
        total_hours=total_hours,
        total_days=total_days,
        horizon_days=horizon_days,
        num_test_days=num_test_days,
        num_val_days=num_val_days,
        coverage_days=coverage_days,
        training_days=training_days,
        theoretical_max_test_days=theoretical_max_test_days,
        recommended_max_test_days=recommended_max_test_days,
    recommended_max_coverage_days=recommended_max_coverage_days,
    capacity_max_test_days=capacity_max_test_days,
    capacity_limited=capacity_limited,
        min_training_days_target=min_training_days,
    )


def print_report(result: CoverageResult):
    print("=== Second Tier Coverage Report ===")
    print(f"Region: {result.region}")
    print(f"Effective overlap: {result.effective_start} -> {result.effective_end}")
    print(f"Total hours: {result.total_hours}  (~{result.total_days:.2f} days)")
    print(f"Config: NUM_TEST_DAYS={result.num_test_days}, NUM_VAL_DAYS={result.num_val_days}, horizonDays={result.horizon_days}")
    print(f"Current coverageDays (unique calendar days spanned by forecasts): {result.coverage_days}")
    print(f"Training days remaining: {result.training_days:.2f}")
    print(f"Theoretical max NUM_TEST_DAYS (zero training days left): {result.theoretical_max_test_days}")
    print(
        f"Recommended max NUM_TEST_DAYS (training >= {result.min_training_days_target} days & within capacity): {result.recommended_max_test_days}"
    )
    print(
        f"Recommended max coverage days: {result.recommended_max_coverage_days} (NUM_TEST_DAYS + horizonDays - 1)"
    )
    print(f"Forecast feature capacity max NUM_TEST_DAYS: {result.capacity_max_test_days}")
    if result.capacity_limited:
        print("WARNING: Current NUM_TEST_DAYS exceeds feature capacity; adjust NUM_TEST_DAYS or regenerate longer 168h feature file.")
    print("Formula reminder: coverageDays = NUM_TEST_DAYS + (horizonDays - 1)")
    print("To reach target coverageDays X: set NUM_TEST_DAYS = X - (horizonDays - 1)")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Compute feasible NUM_TEST_DAYS / coverage for second-tier forecasts.")
    p.add_argument('config', help='Path to secondTierConfig.json')
    p.add_argument('region', help='Region key present in config (e.g., AECI)')
    p.add_argument('--target-coverage-days', type=int, help='Optional desired coverage days to evaluate feasibility')
    p.add_argument('--min-training-days', type=int, default=int(os.getenv('MIN_TRAINING_DAYS', 30)), help='Minimum training days to preserve for recommended max calculation (default 30)')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.region not in cfg:
        print(f"Region {args.region} not found in config.", file=sys.stderr)
        return 2
    result = compute_coverage(cfg, args.region, args.target_coverage_days, args.min_training_days)
    print_report(result)
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
