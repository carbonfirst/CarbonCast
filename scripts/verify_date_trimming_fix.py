#!/usr/bin/env python3
"""
Script to verify the data trimming fix works correctly
"""

import pandas as pd
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from secondTierForecasts import initialize

def verify_trimming_fix():
    """Verify that the dynamic date trimming works correctly"""
    
    # Test with AECI data
    in_file = "data/AECI/AECI_direct_emissions.csv"
    forecast_file = "data/AECI/AECI_168hr_forecasts_DA.csv"
    start_col = 1
    
    print("=== Verifying Date Trimming Fix ===")
    print(f"Testing with file: {in_file}")
    
    try:
        # Call the initialize function which now has dynamic trimming
        dataset, forecastDataset, dateTime = initialize(in_file, forecast_file, start_col, None)
        
        # Check the results
        first_date = dataset.index[0]
        last_date = dataset.index[-1]
        
        print(f"\nResults after trimming:")
        print(f"Dataset starts from: {first_date}")
        print(f"Dataset ends at: {last_date}")
        print(f"Total data points: {len(dataset)}")
        
        # Verify that it starts from 2022-01-01
        expected_start = pd.Timestamp('2022-01-01 00:00:00')
        
        if first_date.replace(tzinfo=None) == expected_start:
            print("✅ SUCCESS: Dataset now starts from 2022-01-01 00:00:00 as expected!")
        else:
            print(f"❌ ISSUE: Dataset starts from {first_date}, expected 2022-01-01 00:00:00")
            
        # Check data splits with current config (NUM_TEST_DAYS=359, NUM_VAL_DAYS=90)
        # From config: NUM_TEST_DAYS = 359, NUM_VAL_DAYS = 90
        # Expected splits:
        # - Training: 2022-01-01 to around 2022-09-26 (before validation period)
        # - Validation: ~90 days before test period
        # - Test: Last 359 days of available data
        
        total_hours = len(dataset)
        test_hours = 359 * 24
        val_hours = 90 * 24
        train_hours = total_hours - test_hours - val_hours
        
        # Calculate approximate dates for each split
        train_end_idx = train_hours
        val_end_idx = train_hours + val_hours
        
        if train_end_idx > 0 and val_end_idx < len(dataset):
            train_end_date = dataset.index[train_end_idx - 1]
            val_start_date = dataset.index[train_end_idx] 
            val_end_date = dataset.index[val_end_idx - 1]
            test_start_date = dataset.index[val_end_idx]
            
            print(f"\nExpected data splits:")
            print(f"Training: {first_date} to {train_end_date}")
            print(f"Validation: {val_start_date} to {val_end_date}")  
            print(f"Test: {test_start_date} to {last_date}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

if __name__ == "__main__":
    verify_trimming_fix()