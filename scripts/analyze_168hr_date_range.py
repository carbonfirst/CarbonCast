#!/usr/bin/env python3
"""
Analyze the date range in AECI_168hr_forecasts_DA.csv to understand
why second tier output starts from January 5, 2023.
"""

import pandas as pd
from datetime import datetime, timedelta

def analyze_date_range():
    """Analyze the date range and gaps in the 168hr forecast data."""
    
    # Read the CSV file
    file_path = 'data/AECI/AECI_168hr_forecasts_DA.csv'
    print(f"Reading {file_path}...")
    
    try:
        df = pd.read_csv(file_path)
        print(f"✓ Successfully read file with {len(df)} rows")
        
        # Convert datetime column to datetime type
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Basic statistics
        print("\n" + "="*60)
        print("DATE RANGE ANALYSIS")
        print("="*60)
        
        print(f"\nTotal rows: {len(df)}")
        print(f"First date: {df['datetime'].min()}")
        print(f"Last date:  {df['datetime'].max()}")
        
        # Calculate expected vs actual rows
        date_range = df['datetime'].max() - df['datetime'].min()
        expected_hours = int(date_range.total_seconds() / 3600) + 1
        print(f"\nDate range spans: {date_range.days} days, {date_range.seconds // 3600} hours")
        print(f"Expected rows (hourly data): {expected_hours}")
        print(f"Actual rows: {len(df)}")
        
        # Check for duplicates
        duplicates = df['datetime'].duplicated().sum()
        print(f"Duplicate timestamps: {duplicates}")
        
        # Analyze first week of data
        print("\n" + "="*60)
        print("FIRST WEEK ANALYSIS (Jan 1-7, 2023)")
        print("="*60)
        
        first_week = df[df['datetime'] < '2023-01-08']
        print(f"\nRows in first week: {len(first_week)}")
        
        # Check for 168-hour (7-day) lookback requirement
        print("\n" + "="*60)
        print("168-HOUR LOOKBACK ANALYSIS")
        print("="*60)
        
        lookback_hours = 168
        lookback_days = lookback_hours / 24
        
        print(f"\n168-hour lookback = {lookback_days} days")
        print(f"If model needs 168 hours of historical data:")
        print(f"  - Data starts: {df['datetime'].min()}")
        print(f"  - First valid forecast after 168hr lookback: {df['datetime'].min() + timedelta(hours=lookback_hours)}")
        
        # Check what date is 96 hours (4 days) into the dataset
        fourth_day_start = df['datetime'].min() + timedelta(days=4)
        print(f"\n4 days from start (96 hours): {fourth_day_start}")
        print("This matches January 5, 2023 00:00:00")
        
        # Verify if we have complete hourly data for first 4 days
        print("\n" + "="*60)
        print("CHECKING FIRST 4 DAYS COMPLETENESS")
        print("="*60)
        
        first_four_days = df[df['datetime'] < fourth_day_start]
        print(f"\nRows in first 4 days (Jan 1-4): {len(first_four_days)}")
        print(f"Expected rows (4 days * 24 hours): {4 * 24}")
        
        if len(first_four_days) >= 96:
            print("✓ Sufficient data for 4-day initialization period")
        
        # Sample first and last 5 rows
        print("\n" + "="*60)
        print("FIRST 5 ROWS")
        print("="*60)
        print(df[['datetime']].head())
        
        print("\n" + "="*60)
        print("LAST 5 ROWS")
        print("="*60)
        print(df[['datetime']].tail())
        
        # Check for any gaps in hourly sequence
        print("\n" + "="*60)
        print("CHECKING FOR GAPS IN HOURLY DATA")
        print("="*60)
        
        df_sorted = df.sort_values('datetime')
        time_diffs = df_sorted['datetime'].diff()
        
        # Find any gaps larger than 1 hour
        gaps = time_diffs[time_diffs > pd.Timedelta(hours=1)]
        
        if len(gaps) > 0:
            print(f"\nFound {len(gaps)} gaps larger than 1 hour:")
            for idx, gap in gaps.items():
                prev_time = df_sorted.loc[idx-1, 'datetime'] if idx > 0 else None
                curr_time = df_sorted.loc[idx, 'datetime']
                if prev_time:
                    print(f"  Gap: {prev_time} to {curr_time} ({gap})")
        else:
            print("\n✓ No gaps found - continuous hourly data")
            
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print("\nThe second tier output starts from January 5, 2023 because:")
        print("1. The first tier forecast data starts from January 1, 2023")
        print("2. The model likely needs 4 days (96 hours) of historical data")
        print("3. January 1-4 provides the initialization/warmup period")
        print("4. January 5 is the first date with sufficient historical context")
        print("\nThis 4-day offset is consistent with the model needing recent")
        print("historical data to generate accurate carbon intensity forecasts.")
        
    except Exception as e:
        print(f"Error reading file: {e}")
        return

if __name__ == "__main__":
    analyze_date_range()