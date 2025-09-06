#!/usr/bin/env python3

"""
Summary of the 2022-2023 Extended Data Setup for AECI
"""

import pandas as pd
import json
import os

def print_header(title):
    print("\n" + "=" * 60)
    print(title.center(60))
    print("=" * 60)

def main():
    print_header("AECI 2022-2023 EXTENDED DATA SETUP SUMMARY")
    
    # 1. Check data files
    print_header("1. DATA FILES CREATED")
    
    files = {
        "Electricity Generation": "data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023.csv",
        "Weather Forecast": "extn/AECI_weather_forecast_2022_2023.csv"
    }
    
    for name, path in files.items():
        if os.path.exists(path):
            df = pd.read_csv(path, nrows=5)
            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
            row_count = len(pd.read_csv(path))
            print(f"\n✓ {name}:")
            print(f"  Path: {path}")
            print(f"  Size: {file_size:.1f} MB")
            print(f"  Rows: {row_count:,}")
            print(f"  Columns: {list(df.columns)}")
            
            # Show date range
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                full_df = pd.read_csv(path)
                full_df['datetime'] = pd.to_datetime(full_df['datetime'])
                print(f"  Date range: {full_df['datetime'].min()} to {full_df['datetime'].max()}")
            elif 'UTC time' in df.columns:
                df['UTC time'] = pd.to_datetime(df['UTC time'])
                full_df = pd.read_csv(path)
                full_df['UTC time'] = pd.to_datetime(full_df['UTC time'])
                print(f"  Date range: {full_df['UTC time'].min()} to {full_df['UTC time'].max()}")
        else:
            print(f"\n✗ {name}: NOT FOUND at {path}")
    
    # 2. Configuration Changes
    print_header("2. CONFIGURATION UPDATES IN firstTierConfig.json")
    
    print("""
The following changes have been made to src/firstTierConfig.json:

AECI Section:
  - IN_FILE_NAME_PREFIX: Changed to "data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023"
  - WEATHER_FORECAST_IN_FILE_NAME: Changed to "extn/AECI_weather_forecast_2022_2023.csv"
  - AGGREGATED_FORECAST_OUT_FILE_NAME: Changed to "data/AECI/AECI_168hr_forecasts_2022_2023.csv"

TRAIN_TEST_PERIOD Section:
  - Replaced AECI_2023_H1 with AECI_2022_2023_FULL
  - DATASET_LIMITER: Set to null (use all data)
  - OUT_FILE_SUFFIX: "2022_2023_full"
  - NUM_TEST_DAYS: 365 (full year of 2023)
""")
    
    # 3. How to run
    print_header("3. HOW TO RUN FIRST TIER FORECASTING")
    
    print("""
To generate 168-hour forecasts for all of 2023 using 2022 as training data:

1. Make sure you're in the CarbonCast directory
2. Run the first tier forecasting:
   
   python src/firstTierForecasts.py
   
   This will:
   - Train models on 2022 data
   - Generate 168-hour forecasts for all of 2023
   - Save results to: data/AECI/AECI_168hr_forecasts_2022_2023.csv

3. The output file will contain:
   - datetime: Forecast timestamps
   - Coal, Natural Gas, Wind: Hourly generation forecasts (MW)
   - Weather features: Temperature, wind speed, etc.
   - Covering: Jan 1, 2023 00:00 - Dec 31, 2023 23:00
""")
    
    # 4. Next steps
    print_header("4. NEXT STEPS")
    
    print("""
After running first tier forecasting:

1. The output file (AECI_168hr_forecasts_2022_2023.csv) can be used by the 
   second tier to generate carbon intensity forecasts for all of 2023

2. Update secondTierConfig.json to point to the new forecast file

3. Run second tier forecasting to get 168-hour carbon intensity forecasts

Benefits:
- Full year coverage for 2023
- 168-hour forecast horizon (7 days)
- Uses 2022 as training data
- Ready for second tier carbon intensity forecasting
""")
    
    # 5. Verification
    print_header("5. DATA VERIFICATION")
    
    # Check alignment
    if os.path.exists(files["Electricity Generation"]) and os.path.exists(files["Weather Forecast"]):
        elec_df = pd.read_csv(files["Electricity Generation"])
        weather_df = pd.read_csv(files["Weather Forecast"])
        
        if len(elec_df) == len(weather_df):
            print(f"✓ Data files are aligned: {len(elec_df):,} rows each")
        else:
            print(f"✗ Data mismatch! Electricity: {len(elec_df):,} rows, Weather: {len(weather_df):,} rows")
        
        # Check for 2 years of data
        expected_hours = 365 * 24 * 2  # 2 years
        if len(elec_df) == expected_hours:
            print(f"✓ Correct number of hours for 2 years: {expected_hours:,}")
        else:
            print(f"⚠ Expected {expected_hours:,} hours, found {len(elec_df):,}")
    
    print("\n" + "=" * 60)
    print("Setup Complete!".center(60))
    print("=" * 60)

if __name__ == "__main__":
    main()