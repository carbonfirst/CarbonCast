#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime

# map Taiwan Power fuel types to source types
energy_mapping = {
    'NUCLEAR': 'nuclear',
    'COAL': 'coal',
    'IPPCOAL': 'coal',
    'LNG': 'nat_gas',
    'IPPLNG': 'nat_gas',
    'COGEN': 'nat_gas',
    'OIL': 'oil',
    'DIESEL': 'oil',
    'HYDRO': 'hydro',
    'WIND': 'wind',
    'SOLAR': 'solar',
    'OTHERRENEWABLEENERGY': 'other'
}

def parse_power_generation(val):
    """
    Try to parse the power generation value as a float.
    Some rows might contain non-numeric strings (like "-" or "N/A"). Return np.nan if cannot parse.
    """
    try:
        return float(val)
    except:
        return np.nan

def main(input_csv: str, output_csv: str):
    df = pd.read_csv(input_csv)

    # Remove rows that are subtotals
    df = df[~df["Unit Name"].str.contains("Subtotal", na=False)]

    # Create column 'utc_hour' that is the Timestamp truncated to the hour and converted to UTC timezone
    df['utc_hour'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M", utc=True).dt.floor('h')

    df['fuel'] = df['Energy Type'].map(energy_mapping)
    df = df[df['fuel'].notnull()]

    df['Power Generation (MW)'] = df['Power Generation (MW)'].apply(parse_power_generation)
    # Drop non-parsable rows like "N/A" or "-"
    df = df.dropna(subset=["Power Generation (MW)"])

    grouped = df.groupby(['utc_hour', 'fuel'])["Power Generation (MW)"].mean().reset_index()
    pivoted = grouped.pivot(index='utc_hour', columns='fuel', values='Power Generation (MW)')

    fuel_order = ['coal', 'nat_gas', 'nuclear', 'oil', 'hydro', 'solar', 'wind', 'other']
    for col in fuel_order:
        if col not in pivoted.columns:
            pivoted[col] = 0.0

    pivoted = pivoted[fuel_order]

    pivoted = pivoted.reset_index().rename(columns={'utc_hour': 'UTC time'})
    pivoted['UTC time'] = pivoted['UTC time'].dt.strftime("%Y-%m-%d %H:%M:%S")

    # Save to csv.
    pivoted.to_csv(output_csv, index=False)
    print(f"Aggregated hourly CSV saved to {output_csv}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Aggregate 10-min power generation data to hourly averages.")
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    args = parser.parse_args()

    main(args.input_csv, args.output_csv)
