"""Quick sanity checks ensuring configs point to 168h files for AECI.

Usage (from repo root):
  python3 scripts/verify_168hr_config.py
"""
from pathlib import Path
import sys
import json5 as json

ROOT = Path(__file__).resolve().parents[1]
ft_cfg_path = ROOT / "src" / "firstTierConfig.json"
st_cfg_path = ROOT / "src" / "secondTierConfig.json"

def load(path: Path):
    with path.open() as f:
        return json.load(f)

def main():
    errors = []
    warnings = []
    ft = load(ft_cfg_path)
    st = load(st_cfg_path)

    # Global horizon expectations
    exp_h = 168
    ft_h = ft.get("PREDICTION_WINDOW_HOURS")
    st_h = st.get("PREDICTION_WINDOW_HOURS")
    if ft_h != exp_h:
        errors.append(f"firstTierConfig PREDICTION_WINDOW_HOURS={ft_h} (expected {exp_h})")
    if st_h != exp_h:
        errors.append(f"secondTierConfig PREDICTION_WINDOW_HOURS={st_h} (expected {exp_h})")

    aeci_ft = ft.get("AECI", {})
    aeci_st = st.get("AECI", {})
    ft_agg = aeci_ft.get("AGGREGATED_FORECAST_OUT_FILE_NAME")
    st_in = aeci_st.get("FORECAST_IN_FILE_NAME")
    if not ft_agg:
        errors.append("AECI AGGREGATED_FORECAST_OUT_FILE_NAME missing in firstTierConfig")
    if not st_in:
        errors.append("AECI FORECAST_IN_FILE_NAME missing in secondTierConfig")
    if ft_agg and "168hr" not in ft_agg:
        warnings.append(f"Aggregated forecast output for AECI does not contain '168hr': {ft_agg}")
    if st_in and "168hr" not in st_in:
        warnings.append(f"Second-tier forecast input for AECI does not contain '168hr': {st_in}")
    if ft_agg and st_in and ft_agg != st_in:
        warnings.append(f"First-tier aggregated file ({ft_agg}) != second-tier input ({st_in})")

    # File existence & minimal column checks
    for label, rel in [("first-tier aggregated", ft_agg), ("second-tier input", st_in)]:
        if not rel:
            continue
        p = ROOT / rel
        if not p.exists():
            errors.append(f"{label} file missing: {p}")
        else:
            # Light header check (expect 'datetime' first column)
            try:
                with p.open() as f:
                    header = f.readline().strip().split(',')
                if not header or header[0] != 'datetime':
                    warnings.append(f"{label} file {p} first column not 'datetime' (got {header[0] if header else 'EMPTY'})")
            except Exception as e:
                warnings.append(f"Could not read header of {p}: {e}")

    print("--- 168h Config Verification ---")
    if errors:
        print("FAIL")
        for e in errors:
            print("ERROR:", e)
    else:
        print("PASS (no blocking issues)")
    for w in warnings:
        print("WARN:", w)
    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
