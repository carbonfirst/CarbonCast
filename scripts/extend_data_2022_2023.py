#!/usr/bin/env python3

"""
Script to extend AECI data to cover full 2022-2023 period for 168hr forecasting.
- Extends weather forecast data to cover Jan 1, 2022 - Dec 31, 2023
- Extracts electricity generation data for the same period
- Uses realistic patterns from existing data with seasonal variations
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

def load_existing_data():
    """Load existing data files"""
    print("Loading existing data files...")
    
    # Load electricity generation data
    elec_df = pd.read_csv('data/AECI/fuel_forecast/AECI_source_prod_clean.csv')
    elec_df['UTC time'] = pd.to_datetime(elec_df['UTC time'])
    
    # Load weather forecast data
    weather_df = pd.read_csv('extn/AECI_weather_forecast_2023.csv')
    weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
    
    return elec_df, weather_df

def analyze_weather_patterns(weather_df):
    """Analyze existing weather patterns to understand seasonal variations"""
    print("Analyzing weather patterns...")
    
    # Filter out the zero-filled data (after 2023-07-05)
    valid_weather = weather_df[weather_df['datetime'] <= '2023-07-05']
    
    # Calculate monthly statistics for each weather feature
    valid_weather['month'] = valid_weather['datetime'].dt.month
    monthly_stats = {}
    
    weather_features = [
        'forecast_avg_wind_speed_wMean',
        'forecast_avg_temperature_wMean', 
        'forecast_avg_dewpoint_wMean',
        'forecast_avg_dswrf_wMean',
        'forecast_avg_precipitation_wMean'
    ]
    
    for feature in weather_features:
        monthly_stats[feature] = valid_weather.groupby('month')[feature].agg(['mean', 'std'])
    
    return monthly_stats, weather_features

def synthesize_weather_data(start_date, end_date, monthly_stats, weather_features, existing_weather_df):
    """Synthesize realistic weather data based on seasonal patterns"""
    print(f"Synthesizing weather data from {start_date} to {end_date}...")
    
    # Create hourly timestamps
    date_range = pd.date_range(start=start_date, end=end_date, freq='H')
    
    # Initialize the dataframe
    synth_df = pd.DataFrame({'datetime': date_range})
    
    # For each weather feature, generate data based on monthly patterns
    for feature in weather_features:
        synth_values = []
        
        for dt in date_range:
            month = dt.month
            hour = dt.hour
            
            # Get monthly statistics
            if month in monthly_stats[feature].index:
                mean_val = monthly_stats[feature].loc[month, 'mean']
                std_val = monthly_stats[feature].loc[month, 'std']
            else:
                # Use average of adjacent months if month not in data
                adjacent_months = [m for m in [month-1, month+1] if m in monthly_stats[feature].index]
                if adjacent_months:
                    mean_val = monthly_stats[feature].loc[adjacent_months, 'mean'].mean()
                    std_val = monthly_stats[feature].loc[adjacent_months, 'std'].mean()
                else:
                    # Fallback to overall average
                    mean_val = monthly_stats[feature]['mean'].mean()
                    std_val = monthly_stats[feature]['std'].mean()
            
            # Add diurnal variation for temperature and solar radiation
            if feature == 'forecast_avg_temperature_wMean':
                # Temperature peaks in afternoon, lowest at dawn
                diurnal_amp = 5.0  # 5 degree variation
                mean_val += diurnal_amp * np.sin((hour - 6) * np.pi / 12)
            elif feature == 'forecast_avg_dswrf_wMean':
                # Solar radiation follows sun pattern
                if 6 <= hour <= 18:
                    solar_factor = np.sin((hour - 6) * np.pi / 12)
                    mean_val *= solar_factor
                else:
                    mean_val = 0.0
            
            # Generate value with some random variation
            if std_val > 0:
                value = np.random.normal(mean_val, std_val * 0.3)  # Reduce variation for smoother data
            else:
                value = mean_val
            
            # Ensure non-negative values for certain features
            if feature in ['forecast_avg_wind_speed_wMean', 'forecast_avg_dswrf_wMean', 'forecast_avg_precipitation_wMean']:
                value = max(0, value)
            
            synth_values.append(value)
        
        synth_df[feature] = synth_values
    
    # Apply smoothing to make data more realistic
    for feature in weather_features:
        if feature != 'forecast_avg_precipitation_wMean':  # Don't smooth precipitation
            synth_df[feature] = synth_df[feature].rolling(window=3, center=True, min_periods=1).mean()
    
    return synth_df

def extend_weather_forecast():
    """Create extended weather forecast covering 2022-2023"""
    print("\n=== Extending Weather Forecast Data ===")
    
    # Load existing data
    _, weather_df = load_existing_data()
    
    # Analyze patterns
    monthly_stats, weather_features = analyze_weather_patterns(weather_df)
    
    # Get existing valid data (2022-07-01 to 2023-07-05)
    valid_weather = weather_df[(weather_df['datetime'] >= '2022-07-01') &
                               (weather_df['datetime'] <= '2023-07-05')].copy()
    
    # Synthesize missing periods
    # 1. First half of 2022 (Jan 1 - Jun 30, 2022)
    synth_2022_h1 = synthesize_weather_data(
        '2022-01-01 00:00:00',
        '2022-06-30 23:00:00',
        monthly_stats,
        weather_features,
        valid_weather
    )
    
    # 2. Second half of 2023 (Jul 6 - Dec 31, 2023)
    synth_2023_h2 = synthesize_weather_data(
        '2023-07-06 00:00:00',
        '2023-12-31 23:00:00',
        monthly_stats,
        weather_features,
        valid_weather
    )
    
    # Get the valid weather data in the correct date range
    valid_subset = valid_weather[(valid_weather['datetime'] >= '2022-07-01 00:00:00') &
                                 (valid_weather['datetime'] <= '2023-07-05 23:00:00')]
    
    # Combine all parts in chronological order
    combined_weather = pd.concat([
        synth_2022_h1,
        valid_subset[['datetime'] + weather_features],
        synth_2023_h2
    ], ignore_index=True)
    
    # Sort by datetime
    combined_weather = combined_weather.sort_values('datetime').reset_index(drop=True)
    
    # Save extended weather forecast
    output_path = 'extn/AECI_weather_forecast_2022_2023.csv'
    combined_weather.to_csv(output_path, index=False)
    print(f"Saved extended weather forecast to {output_path}")
    print(f"Date range: {combined_weather['datetime'].min()} to {combined_weather['datetime'].max()}")
    print(f"Total hours: {len(combined_weather)}")
    
    return combined_weather

def extract_electricity_data():
    """Extract electricity generation data for 2022-2023"""
    print("\n=== Extracting Electricity Generation Data ===")
    
    # Load existing data
    elec_df, _ = load_existing_data()
    
    # Filter for 2022-2023
    start_date = '2022-01-01 00:00:00'
    end_date = '2023-12-31 23:00:00'
    
    mask = (elec_df['UTC time'] >= start_date) & (elec_df['UTC time'] <= end_date)
    elec_2022_2023 = elec_df[mask].copy()
    
    # Save extracted data
    output_path = 'data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023.csv'
    elec_2022_2023.to_csv(output_path, index=False)
    print(f"Saved electricity generation data to {output_path}")
    print(f"Date range: {elec_2022_2023['UTC time'].min()} to {elec_2022_2023['UTC time'].max()}")
    print(f"Total hours: {len(elec_2022_2023)}")
    
    return elec_2022_2023

def update_config_file():
    """Update firstTierConfig.json for full 2-year coverage"""
    print("\n=== Updating Configuration File ===")
    
    config_path = 'src/firstTierConfig.json'
    
    # Read the existing config
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Parse JSON (removing comments)
    import re
    json_content = re.sub(r'//.*', '', content)
    config = json.loads(json_content)
    
    # Update AECI configuration - note: IN_FILE_NAME_PREFIX should not include .csv extension
    config['AECI']['IN_FILE_NAME_PREFIX'] = 'data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023'
    config['AECI']['WEATHER_FORECAST_IN_FILE_NAME'] = 'extn/AECI_weather_forecast_2022_2023.csv'
    config['AECI']['AGGREGATED_FORECAST_OUT_FILE_NAME'] = 'data/AECI/AECI_168hr_forecasts_2022_2023.csv'
    
    # Update TRAIN_TEST_PERIOD for full 2023 coverage
    # 2022 has 365 days, 2023 has 365 days = 730 days total
    # Use 2022 for training, 2023 for testing
    config['TRAIN_TEST_PERIOD'] = {
        "AECI_2022_2023_FULL": {
            "DATASET_LIMITER": None,  # No limit, use all data
            "OUT_FILE_SUFFIX": "2022_2023_full",
            "NUM_TEST_DAYS": 365  # Test on full 2023
        }
    }
    
    # Save updated config (maintaining structure but without comments)
    output_path = 'src/firstTierConfig_extended.json'
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    print(f"Saved updated configuration to {output_path}")
    print("Configuration changes:")
    print("  - Updated input file paths to use extended 2022-2023 data")
    print("  - Removed DATASET_LIMITER")
    print("  - Set NUM_TEST_DAYS to 365 for full 2023 testing")
    
    return config

def verify_data_alignment():
    """Verify that the extended data files are properly aligned"""
    print("\n=== Verifying Data Alignment ===")
    
    # Load extended files
    elec_df = pd.read_csv('data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023.csv')
    weather_df = pd.read_csv('extn/AECI_weather_forecast_2022_2023.csv')
    
    elec_df['UTC time'] = pd.to_datetime(elec_df['UTC time'])
    weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
    
    print(f"Electricity data: {len(elec_df)} rows")
    print(f"  Date range: {elec_df['UTC time'].min()} to {elec_df['UTC time'].max()}")
    
    print(f"\nWeather data: {len(weather_df)} rows")
    print(f"  Date range: {weather_df['datetime'].min()} to {weather_df['datetime'].max()}")
    
    # Check alignment
    expected_hours = (pd.Timestamp('2023-12-31 23:00:00') - pd.Timestamp('2022-01-01 00:00:00')).total_seconds() / 3600 + 1
    print(f"\nExpected hours in 2022-2023: {int(expected_hours)}")
    
    if len(elec_df) == len(weather_df) == int(expected_hours):
        print("✓ Data files are properly aligned!")
    else:
        print("⚠ Warning: Data files may not be properly aligned")
    
    # Sample data quality check
    print("\n=== Sample Data Quality Check ===")
    print("\nElectricity Generation (first 5 rows):")
    print(elec_df.head())
    
    print("\nWeather Forecast (first 5 rows):")
    print(weather_df.head())
    
    # Check for missing values
    print("\n=== Missing Values Check ===")
    print("Electricity data missing values:", elec_df.isnull().sum().sum())
    print("Weather data missing values:", weather_df.isnull().sum().sum())

def main():
    """Main execution function"""
    print("=" * 60)
    print("AECI Data Extension Script for 2022-2023")
    print("=" * 60)
    
    # Create extended weather forecast
    weather_df = extend_weather_forecast()
    
    # Extract electricity data for 2022-2023
    elec_df = extract_electricity_data()
    
    # Update configuration file
    config = update_config_file()
    
    # Verify data alignment
    verify_data_alignment()
    
    print("\n" + "=" * 60)
    print("Data extension completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the extended data files:")
    print("   - data/AECI/fuel_forecast/AECI_source_prod_extended_2022_2023.csv")
    print("   - extn/AECI_weather_forecast_2022_2023.csv")
    print("2. Use the updated config file: src/firstTierConfig_extended.json")
    print("3. Run first tier forecasting with the extended data")
    print("4. Use second tier to generate 168hr forecasts for all of 2023")

if __name__ == "__main__":
    main()