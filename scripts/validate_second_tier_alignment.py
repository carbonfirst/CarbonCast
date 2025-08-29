"""Validate alignment between emissions (second tier CEF input) and forecast feature file.

Run:
  python scripts/validate_second_tier_alignment.py src/secondTierConfig.json AECI -d

Outputs:
  - Date ranges (emissions vs forecast features)
  - Expected expanded test window start/end
  - Warnings if forecast features end before emissions test window end
"""
import sys
from pathlib import Path
import json5 as json
import pandas as pd

def main():
    if len(sys.argv) < 4:
        print("Usage: python validate_second_tier_alignment.py <config> <REGION> <-d|-l>")
        sys.exit(1)
    cfg_path = Path(sys.argv[1])
    region = sys.argv[2]
    cef_flag = sys.argv[3]
    cfg = json.load(cfg_path.open())

    pred_h = cfg["PREDICTION_WINDOW_HOURS"]
    buffer_hours = pred_h - 24
    num_test_days = cfg["NUM_TEST_DAYS"]
    expanded_test_days = num_test_days + buffer_hours//24
    init_drop = int(cfg.get("INITIAL_HOURS_TO_DROP", 8760))
    final_drop = int(cfg.get("FINAL_HOURS_TO_DROP", 72))

    r_cfg = cfg[region]
    emissions_file = r_cfg["DIRECT_CEF_IN_FILE_NAME"] if cef_flag == "-d" else r_cfg["LIFECYCLE_CEF_IN_FILE_NAME"]
    forecast_file = r_cfg["FORECAST_IN_FILE_NAME"]

    df_e = pd.read_csv(emissions_file, parse_dates=['UTC time'])
    raw_start, raw_end = df_e['UTC time'].min(), df_e['UTC time'].max()
    trimmed = df_e.iloc[init_drop:]
    if final_drop > 0:
        trimmed = trimmed.iloc[:-final_drop]
    trim_start, trim_end = trimmed['UTC time'].min(), trimmed['UTC time'].max()

    df_f = pd.read_csv(forecast_file, parse_dates=['datetime'])
    f_start, f_end = df_f['datetime'].min(), df_f['datetime'].max()

    # Expected test window
    exp_test_end = trim_end
    exp_test_start = trim_end - pd.Timedelta(days=expanded_test_days) + pd.Timedelta(hours=1)
    # Align to hour boundary start
    exp_test_start = exp_test_start.replace(minute=0, second=0, microsecond=0)

    print("--- Alignment Report (", region, cef_flag, ") ---")
    print(f"Raw emissions:        {raw_start} -> {raw_end}")
    print(f"Trimmed emissions:    {trim_start} -> {trim_end} (drop first {init_drop}h, last {final_drop}h)")
    print(f"Forecast features:    {f_start} -> {f_end}")
    print(f"PREDICTION_WINDOW_HOURS={pred_h} BUFFER_HOURS={buffer_hours} NUM_TEST_DAYS={num_test_days} => expanded_test_days={expanded_test_days}")
    print(f"Expected test window: {exp_test_start} -> {exp_test_end}")
    if f_end < exp_test_end:
        print(f"WARN: Forecast features end {f_end} before emissions test window end {exp_test_end}. Late test days use stale features.")
    if f_start > exp_test_start:
        print(f"WARN: Forecast features start {f_start} after expected test window start {exp_test_start}. Early test days use stale history only.")
    if trim_end < raw_end:
        print("INFO: Final hours were trimmed; adjust FINAL_HOURS_TO_DROP to include them if needed.")

if __name__ == "__main__":
    main()
