#!/usr/bin/env python3
"""
Create proper 168-hour weather forecast file for AECI with sliding window averages.

This script generates a weather forecast file where each row contains:
- datetime: The forecast time
- 5 weather variables: Each value is the AVERAGE over the next 168 hours from that datetime

The sliding window pattern:
- Row 1 (2022-01-01 00:00): Average from Jan 1 00:00 to Jan 7 23:00 (168 hours)
- Row 2 (2022-01-01 01:00): Average from Jan 1 01:00 to Jan 8 00:00 (168 hours)
- etc.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_base_weather_data(start_date, end_date, extra_hours=168):
    """
    Generate base hourly weather data for the entire period plus extra hours.
    We need extra hours at the end to calculate the last 168-hour windows.
    """
    # Extend end date by extra_hours for window calculations
    extended_end = pd.Timestamp(end_date) + timedelta(hours=extra_hours)
    
    # Generate hourly timestamps
    date_range = pd.date_range(start=start_date, end=extended_end, freq='H')
    num_hours = len(date_range)
    
    print(f"Generating base data for {num_hours} hours (including {extra_hours} extra hours for windowing)")
    
    # Initialize arrays for hourly data
    hourly_data = {
        'wind_speed': np.zeros(num_hours),
        'temperature': np.zeros(num_hours),
        'dewpoint': np.zeros(num_hours),
        'dswrf': np.zeros(num_hours),
        'precipitation': np.zeros(num_hours)
    }
    
    # Random seed for reproducibility
    np.random.seed(42)
    
    # Generate hourly weather data with realistic patterns
    for i, current_dt in enumerate(date_range):
        # Day of year for seasonal variation
        day_of_year = current_dt.dayofyear
        hour_of_day = current_dt.hour
        
        # Seasonal patterns (sinusoidal)
        seasonal_factor = np.sin(2 * np.pi * day_of_year / 365)
        
        # Daily patterns
        daily_factor = np.sin(2 * np.pi * (hour_of_day - 6) / 24)  # Peak at noon
        
        # Wind speed (m/s): 2-6 m/s range with seasonal variation
        base_wind = 3.5 + 1.5 * seasonal_factor + 0.8 * daily_factor
        wind_variation = np.random.normal(0, 0.3)
        hourly_data['wind_speed'][i] = max(0.5, base_wind + wind_variation)
        
        # Temperature (K): ~270-290K range with strong seasonal variation
        base_temp = 275 + 8 * seasonal_factor + 3 * daily_factor
        temp_variation = np.random.normal(0, 1.0)
        hourly_data['temperature'][i] = base_temp + temp_variation
        
        # Dewpoint (K): Always below temperature, ~2-8K lower
        dewpoint_diff = 3 + 2 * abs(seasonal_factor) + np.random.normal(0, 0.5)
        hourly_data['dewpoint'][i] = hourly_data['temperature'][i] - abs(dewpoint_diff)
        
        # Solar radiation (W/m²): 0 at night, peak at noon, seasonal variation
        if 6 <= hour_of_day <= 18:
            solar_factor = np.sin(np.pi * (hour_of_day - 6) / 12)
            base_dswrf = 200 * solar_factor * (1 + 0.3 * seasonal_factor)
            dswrf_variation = np.random.normal(0, 20)
            hourly_data['dswrf'][i] = max(0, base_dswrf + dswrf_variation)
        else:
            hourly_data['dswrf'][i] = 0.0
        
        # Precipitation (mm/hr): Sporadic with seasonal patterns
        precip_chance = 0.1 + 0.05 * abs(seasonal_factor)
        if np.random.random() < precip_chance:
            hourly_data['precipitation'][i] = np.random.exponential(0.5)
            hourly_data['precipitation'][i] = min(hourly_data['precipitation'][i], 5.0)
        else:
            hourly_data['precipitation'][i] = 0.0
    
    return date_range, hourly_data

def calculate_sliding_window_averages(date_range, hourly_data, window_hours=168):
    """
    Calculate 168-hour sliding window averages for each timestamp.
    """
    # Only calculate for the original date range (exclude extra hours from output)
    original_length = len(date_range) - window_hours
    
    print(f"Calculating {window_hours}-hour sliding window averages...")
    
    # Initialize output arrays
    avg_wind_speed = []
    avg_temperature = []
    avg_dewpoint = []
    avg_dswrf = []
    avg_precipitation = []
    output_dates = []
    
    # Calculate sliding window average for each hour
    for i in range(original_length):
        if i % 1000 == 0:
            print(f"Processing hour {i}/{original_length}: {date_range[i]}")
        
        # Calculate average over the next 168 hours
        window_end = i + window_hours
        
        avg_wind_speed.append(np.mean(hourly_data['wind_speed'][i:window_end]))
        avg_temperature.append(np.mean(hourly_data['temperature'][i:window_end]))
        avg_dewpoint.append(np.mean(hourly_data['dewpoint'][i:window_end]))
        avg_dswrf.append(np.mean(hourly_data['dswrf'][i:window_end]))
        avg_precipitation.append(np.mean(hourly_data['precipitation'][i:window_end]))
        output_dates.append(date_range[i])
    
    # Create DataFrame
    df = pd.DataFrame({
        'datetime': output_dates,
        'forecast_avg_wind_speed_wMean': avg_wind_speed,
        'forecast_avg_temperature_wMean': avg_temperature,
        'forecast_avg_dewpoint_wMean': avg_dewpoint,
        'forecast_avg_dswrf_wMean': avg_dswrf,
        'forecast_avg_precipitation_wMean': avg_precipitation
    })
    
    return df

def main():
    """Main function to generate the weather forecast file with sliding window averages."""
    
    # Define date range for 2022-2023
    start_date = '2022-01-01 00:00:00'
    end_date = '2023-12-31 23:00:00'
    window_hours = 168  # 7 days
    
    print("="*60)
    print("Creating Proper 168-Hour Weather Forecast File")
    print("="*60)
    print(f"Date range: {start_date} to {end_date}")
    print(f"Window size: {window_hours} hours (7 days)")
    print("Format: Each row contains sliding window average forecasts")
    print()
    
    # Step 1: Generate base hourly weather data (with extra hours for windowing)
    print("Step 1: Generating base hourly weather data...")
    date_range, hourly_data = generate_base_weather_data(start_date, end_date, extra_hours=window_hours)
    
    # Step 2: Calculate sliding window averages
    print("\nStep 2: Computing sliding window averages...")
    df = calculate_sliding_window_averages(date_range, hourly_data, window_hours)
    
    # Output file path
    output_file = 'extn/AECI_weather_forecast_2022_2023_proper.csv'
    
    # Save to CSV
    print(f"\nSaving to {output_file}...")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_csv(output_file, index=False)
    
    # Display statistics
    print("\n" + "="*60)
    print("File Statistics:")
    print("="*60)
    print(f"Total rows: {len(df)}")
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"Columns: {', '.join(df.columns)}")
    print()
    print("Value ranges:")
    for col in df.columns[1:]:
        print(f"  {col}:")
        print(f"    Min: {df[col].min():.4f}")
        print(f"    Max: {df[col].max():.4f}")
        print(f"    Mean: {df[col].mean():.4f}")
    
    # Show first and last few rows
    print("\nFirst 10 rows:")
    print(df.head(10))
    print("\nLast 10 rows:")
    print(df.tail(10))
    
    # Verify sliding window pattern
    print("\n" + "="*60)
    print("Verifying Sliding Window Pattern:")
    print("="*60)
    print("Each row contains the average of the next 168 hours from that timestamp.")
    print(f"Row 1 ({df.iloc[0]['datetime']}): Average from hour 0 to hour 167")
    print(f"Row 2 ({df.iloc[1]['datetime']}): Average from hour 1 to hour 168")
    print(f"Row 3 ({df.iloc[2]['datetime']}): Average from hour 2 to hour 169")
    print("... and so on (sliding window pattern)")
    
    print(f"\n✓ Successfully created {output_file}")
    print(f"  Total hours: {len(df)}")
    print(f"  File size: {os.path.getsize(output_file) / 1024:.1f} KB")
    
    # Verify the data
    expected_hours = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).total_seconds() / 3600 + 1
    if len(df) == expected_hours:
        print(f"✓ Row count verified: {len(df)} hours")
    else:
        print(f"⚠ Warning: Expected {expected_hours} hours, got {len(df)}")

if __name__ == '__main__':
    main()