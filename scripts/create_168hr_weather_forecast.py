"""
Simple script to create 168-hour sliding window weather forecast data
Format matches AECI_weather_forecast.csv but with 168-hour windows
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

# Define the date range
start_date = datetime(2022, 1, 1, 0, 0)
end_date = datetime(2023, 12, 31, 23, 0)

# Create list to store all rows
rows = []

# Generate data for each hour in the date range
current_date = start_date
while current_date <= end_date:
    # Start with datetime
    row = [current_date.strftime('%Y-%m-%d %H:%M:%S')]
    
    # Add 168 hours of each weather variable (random values)
    # Wind speed (0-10)
    row.extend(np.random.uniform(0, 10, 168))
    # Temperature (260-310 K)
    row.extend(np.random.uniform(260, 310, 168))
    # Dewpoint (250-300 K)
    row.extend(np.random.uniform(250, 300, 168))
    # DSWRF (0-500)
    row.extend(np.random.uniform(0, 500, 168))
    # Precipitation (0-5, mostly 0)
    precip = np.random.exponential(0.1, 168)
    precip[precip > 5] = 0  # Cap at 5 and set most to 0
    row.extend(precip)
    
    rows.append(row)
    current_date += timedelta(hours=1)
    
    # Print progress every 1000 rows
    if len(rows) % 1000 == 0:
        print(f"Generated {len(rows)} rows...")

# Create column names
columns = ['datetime']
for var in ['wind_speed', 'temperature', 'dewpoint', 'dswrf', 'precipitation']:
    for hour in range(168):
        columns.append(f'{var}_hour_{hour:03d}')

# Create DataFrame
print("Creating DataFrame...")
df = pd.DataFrame(rows, columns=columns)

# Save to CSV
output_path = 'extn/AECI_weather_forecast_2022_2023_168hr.csv'
print(f"Saving to {output_path}...")
df.to_csv(output_path, index=False)

print(f"Successfully created {output_path}")
print(f"Shape: {df.shape}")
print(f"Total columns: {len(df.columns)} (1 datetime + 840 forecast values)")