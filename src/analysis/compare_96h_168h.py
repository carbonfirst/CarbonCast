import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def load_ci(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    # Ensure standard column names
    df = df.rename(columns={
        'avg_carbon_intensity_forecast': 'forecast',
        'carbon_intensity_actual': 'actual',
    })
    return df[['datetime', 'actual', 'forecast']].dropna()


def compute_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {'count': 0, 'MAE': np.nan, 'RMSE': np.nan, 'MAPE': np.nan}
    e = df['forecast'] - df['actual']
    mae = np.abs(e).mean()
    rmse = np.sqrt((e**2).mean())
    # MAPE guard against zeros
    mape = (np.abs(e) / df['actual'].replace(0, np.nan)).mean() * 100
    return {'count': int(len(df)), 'MAE': float(mae), 'RMSE': float(rmse), 'MAPE': float(mape)}


def by_day_window(df: pd.DataFrame, start_hour: int, end_hour: int) -> pd.DataFrame:
    # Select window within each 168h/96h horizon per day-ahead bucket
    # Here we simply filter by forecast horizon index if present; otherwise skip
    return df


def per_hour_of_day_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['hour', 'MAPE', 'MAE', 'RMSE'])
    d = df.copy()
    d['hour'] = d['datetime'].dt.hour
    rows = []
    for h, g in d.groupby('hour'):
        m = compute_metrics(g)
        rows.append({'hour': int(h), 'MAPE': m['MAPE'], 'MAE': m['MAE'], 'RMSE': m['RMSE']})
    out = pd.DataFrame(rows).sort_values('hour')
    return out


def per_day_bucket_metrics(df: pd.DataFrame, max_buckets: int = 4) -> pd.DataFrame:
    # Approximate D1..D4 as 24h chunks from each midnight within the dataset.
    if df.empty:
        return pd.DataFrame(columns=['bucket', 'MAPE', 'MAE', 'RMSE'])
    d = df.copy().sort_values('datetime')
    d['date'] = d['datetime'].dt.floor('D')
    rows = []
    for date, g in d.groupby('date'):
        for i in range(max_buckets):
            start = date + pd.Timedelta(hours=24*i)
            end = start + pd.Timedelta(hours=24)
            w = g[(g['datetime'] >= start) & (g['datetime'] < end)]
            if len(w) == 0:
                continue
            m = compute_metrics(w)
            rows.append({'date': str(date.date()), 'bucket': f'D{i+1}', 'MAPE': m['MAPE'], 'MAE': m['MAE'], 'RMSE': m['RMSE']})
    if not rows:
        return pd.DataFrame(columns=['bucket', 'MAPE', 'MAE', 'RMSE'])
    dfb = pd.DataFrame(rows)
    # Average across dates
    return dfb.groupby('bucket')[['MAPE','MAE','RMSE']].mean().reset_index()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--region', default='AECI')
    p.add_argument('--mode', choices=['direct', 'lifecycle'], default='direct')
    p.add_argument('--out', default='data/compare_AECI_96h_vs_168h.txt')
    args = p.parse_args()

    base = Path('.')
    r = args.region
    mode = args.mode

    fn_96 = base / 'CI_forecast_data' / r / f'{r}_{mode}_96hr_CI_forecasts_0.csv'
    fn_168 = base / 'CI_forecast_data' / r / f'{r}_{mode}_168hr_CI_forecasts_0.csv'

    if not fn_96.exists() or not fn_168.exists():
        raise SystemExit(f'Missing inputs: {fn_96.exists()} {fn_168.exists()}')

    d96 = load_ci(fn_96)
    d168 = load_ci(fn_168)

    # Inner join on datetime to compare overlapping hours if present
    merged = d96.merge(d168, on='datetime', suffixes=('_96', '_168'))

    lines = []
    lines.append(f'Region: {r}, Mode: {mode}')

    if not merged.empty:
        # Compute metrics per file individually (on overlap)
        m96_overlap = compute_metrics(merged[['datetime', 'actual_96', 'forecast_96']].rename(columns={'actual_96':'actual', 'forecast_96':'forecast'}))
        m168_overlap = compute_metrics(merged[['datetime', 'actual_168', 'forecast_168']].rename(columns={'actual_168':'actual', 'forecast_168':'forecast'}))
        lines.append('Overall (overlapping hours):')
        lines.append(f'  96h:  count={m96_overlap["count"]}, MAE={m96_overlap["MAE"]:.2f}, RMSE={m96_overlap["RMSE"]:.2f}, MAPE={m96_overlap["MAPE"]:.2f}%')
        lines.append(f'  168h: count={m168_overlap["count"]}, MAE={m168_overlap["MAE"]:.2f}, RMSE={m168_overlap["RMSE"]:.2f}, MAPE={m168_overlap["MAPE"]:.2f}%')
    else:
        lines.append('No overlapping hours between 96h and 168h datasets. Showing per-file metrics over their own periods:')

    # Per-file overall metrics (full available period)
    m96_full = compute_metrics(d96)
    m168_full = compute_metrics(d168)
    lines.append('Overall (full period):')
    lines.append(f'  96h:  count={m96_full["count"]}, MAE={m96_full["MAE"]:.2f}, RMSE={m96_full["RMSE"]:.2f}, MAPE={m96_full["MAPE"]:.2f}%')
    lines.append(f'  168h: count={m168_full["count"]}, MAE={m168_full["MAE"]:.2f}, RMSE={m168_full["RMSE"]:.2f}, MAPE={m168_full["MAPE"]:.2f}%')

    # Hour-of-day profiles
    hod96 = per_hour_of_day_metrics(d96)
    hod168 = per_hour_of_day_metrics(d168)
    if not hod96.empty and not hod168.empty:
        lines.append('Hour-of-day average MAPE:')
        for h in range(24):
            r96 = hod96[hod96['hour']==h]
            r168 = hod168[hod168['hour']==h]
            if not r96.empty and not r168.empty:
                lines.append(f'  {h:02d}: 96h={r96.iloc[0]["MAPE"]:.2f}%  |  168h={r168.iloc[0]["MAPE"]:.2f}%')

    # Day-ahead buckets D1..D4 (approx via calendar day chunks)
    d1_4_96 = per_day_bucket_metrics(d96, max_buckets=4)
    d1_4_168 = per_day_bucket_metrics(d168, max_buckets=4)
    if not d1_4_96.empty and not d1_4_168.empty:
        lines.append('Day-ahead buckets D1..D4 (avg MAPE across days):')
        for b in ['D1','D2','D3','D4']:
            r96 = d1_4_96[d1_4_96['bucket']==b]
            r168 = d1_4_168[d1_4_168['bucket']==b]
            if not r96.empty and not r168.empty:
                lines.append(f'  {b}: 96h={r96.iloc[0]["MAPE"]:.2f}%  |  168h={r168.iloc[0]["MAPE"]:.2f}%')

    out_path = base / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
