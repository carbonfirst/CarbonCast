# CarbonCast 168h Comprehensive Runbook

Complete step-by-step guide for running 7-day (168-hour) carbon intensity forecasts from scratch on macOS (Apple Silicon). This runbook includes detailed commands, sample outputs, verification steps, and comprehensive troubleshooting.

## Important Notes
- Run all commands from the repository root directory
- Replace `<REGION>` with your target region code (e.g., AECI, AL, AZPS, BANC)
- Use `micromamba run -n carboncast-310 python ...` to ensure the correct environment in every terminal
- Each step includes verification commands to ensure success before proceeding

## 1. Environment Setup (macOS Prerequisites)

### 1.1 Create and Configure micromamba Environment

```zsh
# Create Python 3.10 environment
micromamba create -n carboncast-310 -c conda-forge -y python=3.10 pip

# Activate environment
micromamba activate carboncast-310

# Verify Python version
python --version
# Expected output: Python 3.10.x
```

### 1.2 Install Python Dependencies

```zsh
# Install from requirements file
pip install -r requirements-macos-arm.txt

# Verify key packages
pip list | grep -E "(tensorflow|numpy|pandas|scikit-learn)"
```

**Expected output:**
```
numpy                     1.21.6
pandas                    1.5.3
scikit-learn              1.2.2
tensorflow-macos          2.9.0
tensorflow-metal          0.5.0
```

### 1.3 Verify TensorFlow Metal (MPS) Support

```zsh
# Test TensorFlow + Metal integration
python - <<'PY'
import tensorflow as tf
import platform
print("TensorFlow version:", tf.__version__)
print("Architecture:", platform.machine())
print("MPS devices:", tf.config.list_physical_devices("GPU"))
print("MPS available:", tf.config.experimental.list_physical_devices("GPU"))
if tf.config.experimental.list_physical_devices("GPU"):
    print("✅ TensorFlow Metal GPU support enabled")
else:
    print("❌ TensorFlow Metal GPU support not available")
PY
```

**Expected output for successful setup:**
```
TensorFlow version: 2.9.0
Architecture: arm64
MPS devices: [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]
MPS available: [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]
✅ TensorFlow Metal GPU support enabled
```

### 1.4 Install and Verify wgrib2

```zsh
# Install wgrib2 via Homebrew
brew install wgrib2

# Verify system-wide installation
which wgrib2
wgrib2 -help | head -n 1

# Verify access within micromamba environment
micromamba run -n carboncast-310 which wgrib2
micromamba run -n carboncast-310 wgrib2 -help | head -n 1
```

**Expected output:**
```
/opt/homebrew/bin/wgrib2
wgrib2 v3.1.1 12/1/2022 www.cpc.ncep.noaa.gov/products/wesley/wgrib2
```

### 1.5 Environment Verification Checklist

```zsh
# Complete environment check
micromamba activate carboncast-310
echo "✅ Environment activated: $CONDA_DEFAULT_ENV"

python -c "import tensorflow as tf; import numpy as np; import pandas as pd; print('✅ Core packages imported successfully')"

which wgrib2 && echo "✅ wgrib2 available"

ls -d 168h_grib2_data/combined/ && echo "✅ GRIB2 data directory found" || echo "❌ GRIB2 data directory missing"
```

## 2. Weather Data Processing

### 2.1 Verify GRIB2 Data Structure

Before processing, verify your GRIB2 data is properly organized:

```zsh
# Check combined data structure for your region (example: AECI)
ls -la 168h_grib2_data/combined/AECI/
```

**Expected structure:**
```
drwxr-xr-x  apcp/
drwxr-xr-x  dswrf/
drwxr-xr-x  tmp_dpt/
drwxr-xr-x  ugrd_vgrd/
```

```zsh
# Verify GRIB2 files exist in each subdirectory
find 168h_grib2_data/combined/AECI/ -name "*.grib2" | wc -l
# Expected: Several hundred files across all subdirectories

# Sample file check (verify wgrib2 can read files)
find 168h_grib2_data/combined/AECI/ugrd_vgrd/ -name "*.grib2" | head -1 | xargs wgrib2 -s | head -5
```

### 2.2 Extract Weather Variables (3-hourly CSVs)

Process each weather variable separately with streaming output for progress monitoring.

**Variable Index Mapping:**
- 0 = Wind (ugrd_vgrd)
- 1 = Temperature/Dewpoint (tmp_dpt)  
- 2 = Solar radiation (dswrf)
- 3 = Precipitation (apcp)

#### 2.2.1 Wind Speed (Index 0)

```zsh
# Terminal 1: Run extraction with streaming
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 0 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Terminal 2: Monitor progress
tail -f extn/AECI_WIND_SPEED.csv
```

**Sample output during processing:**
```
Processing GRIB2 files for wind data...
Found 156 files for 2022
Found 152 files for 2023
Processing file 1/308: AECI_ugrd_vgrd_202207010000_to_202207310000...
...
```

**Expected completion time:** 30-75 minutes depending on data size

#### 2.2.2 Temperature/Dewpoint (Index 1)

```zsh
# Terminal 1: Run extraction
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 1 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Terminal 2: Monitor outputs (two files created)
tail -f extn/AECI_TEMP.csv
tail -f extn/AECI_DPT.csv
```

#### 2.2.3 Solar Radiation (Index 2)

```zsh
# Terminal 1: Run extraction
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 2 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Terminal 2: Monitor progress
tail -f extn/AECI_DSWRF.csv
```

#### 2.2.4 Precipitation (Index 3)

```zsh
# Terminal 1: Run extraction
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 3 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Terminal 2: Monitor progress
tail -f extn/AECI_APCP.csv
```

### 2.3 Verify Weather Extraction Results

```zsh
# Check all expected CSV files were created
ls -la extn/AECI_*.csv
```

**Expected files:**
```
-rw-r--r--  AECI_APCP.csv
-rw-r--r--  AECI_DPT.csv
-rw-r--r--  AECI_DSWRF.csv
-rw-r--r--  AECI_TEMP.csv
-rw-r--r--  AECI_WIND_SPEED.csv
```

```zsh
# Verify file sizes (should be substantial)
wc -l extn/AECI_*.csv
```

**Expected output (approximate):**
```
   5000 extn/AECI_APCP.csv
   5000 extn/AECI_DPT.csv
   5000 extn/AECI_DSWRF.csv
   5000 extn/AECI_TEMP.csv
   5000 extn/AECI_WIND_SPEED.csv
```

```zsh
# Check sample data structure
head -n 3 extn/AECI_WIND_SPEED.csv
```

**Expected format:**
```
time,AECI_WIND_SPEED
2022-07-01 00:00:00,3.456789
2022-07-01 03:00:00,3.234567
```

### 2.4 Clean Weather Data (3-hourly → hourly, 168h horizon)

#### 2.4.1 Configure Weather Cleaning

First, verify the cleaning script is configured for 168h:

```zsh
# Check current configuration
grep "PREDICTION_PERIOD_DAYS" src/weather/cleanWeatherData.py
```

**Expected output:**
```
PREDICTION_PERIOD_DAYS = 7  # For 168-hour forecasts
```

If not set to 7, edit the file:
```python
PREDICTION_PERIOD_DAYS = 7  # Change from 4 to 7 for 168h forecasts
```

#### 2.4.2 Run Weather Cleaning

```zsh
# Clean and aggregate weather data
micromamba run -n carboncast-310 python src/weather/cleanWeatherData.py US extn/

# Monitor progress
echo "Weather cleaning in progress..."
```

**Expected runtime:** 2-5 minutes

#### 2.4.3 Verify Cleaned Weather Data

```zsh
# Check output files
ls -la extn/AECI_*forecast*.csv extn/AECI_*aggregated*.csv
```

**Expected files:**
```
-rw-r--r--  AECI_aggregated_weather_data_2023.csv
-rw-r--r--  AECI_weather_forecast_2023.csv
```

```zsh
# Verify hourly weather forecast structure
head -n 1 extn/AECI_weather_forecast_2023.csv
wc -l extn/AECI_weather_forecast_2023.csv
```

**Expected columns:**
```
time,forecast_avg_wind_speed_wMean,forecast_avg_temperature_wMean,forecast_avg_dewpoint_wMean,forecast_avg_dswrf_wMean,forecast_avg_precipitation_wMean,[additional_time_features]
```

## 3. First Tier Forecasts (Source Generation)

### 3.1 Configure First Tier for 168h

#### 3.1.1 Update First Tier Configuration

```zsh
# Backup current config
cp src/firstTierConfig.json src/firstTierConfig.json.backup

# Check current configuration
grep -E "(PREDICTION_WINDOW_HOURS|MAX_PREDICTION_WINDOW_HOURS)" src/firstTierConfig.json
```

**Required changes in [`src/firstTierConfig.json`](src/firstTierConfig.json):**
```json
{
  "PREDICTION_WINDOW_HOURS": 168,
  "MAX_PREDICTION_WINDOW_HOURS": 168,
  "AECI": {
    "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2023.csv"
  }
}
```

#### 3.1.2 Verify Input Dependencies

```zsh
# Check clean source production data exists
ls -la data/AECI/fuel_forecast/AECI_source_prod_clean.csv
```

**If file doesn't exist:**
```zsh
# Check for raw source data that needs cleaning
ls -la data/AECI/fuel_forecast/
# Look for files like AECI_source_prod.csv or similar
```

```zsh
# Verify weather forecast file path matches config
ls -la extn/AECI_weather_forecast_2023.csv
```

### 3.2 Run First Tier Forecasts

#### 3.2.1 Create Output Directories

```zsh
# Ensure output directories exist
mkdir -p data/AECI/fuel_forecast
mkdir -p saved_first_tier_models/AECI
```

#### 3.2.2 Execute First Tier Training

```zsh
# Run first tier forecasts
micromamba run -n carboncast-310 python src/firstTierForecasts.py src/firstTierConfig.json
```

**Expected runtime:** 15-45 minutes for 3 source types

**Sample progress output:**
```
Loading configuration for AECI...
Processing source type: coal
Training model for coal generation...
Epoch 1/100: loss=0.1234, val_loss=0.1456
...
Model saved: saved_first_tier_models/AECI/AECI_coal_best_model_ann.h5
Processing source type: nat_gas
...
```

### 3.3 Verify First Tier Results

#### 3.3.1 Check Per-Source Forecast Files

```zsh
# Verify per-source CSV outputs
ls -la data/AECI/fuel_forecast/AECI_ANN_*_iter0.csv
```

**Expected files:**
```
-rw-r--r--  AECI_ANN_coal_iter0.csv
-rw-r--r--  AECI_ANN_nat_gas_iter0.csv
-rw-r--r--  AECI_ANN_wind_iter0.csv
```

#### 3.3.2 Check Saved Models

```zsh
# Verify trained models
ls -la saved_first_tier_models/AECI/
```

**Expected files:**
```
-rw-r--r--  AECI_coal_best_model_ann.h5
-rw-r--r--  AECI_nat_gas_best_model_ann.h5
-rw-r--r--  AECI_wind_best_model_ann.h5
```

#### 3.3.3 Check Combined 168h Forecast Matrix

```zsh
# Verify combined forecast matrix for Tier-2
ls -la data/AECI/AECI_168hr_forecasts_DA.csv
```

```zsh
# Check matrix structure
head -n 1 data/AECI/AECI_168hr_forecasts_DA.csv
wc -l data/AECI/AECI_168hr_forecasts_DA.csv
```

**Expected structure:**
- Columns: Weather features (5) + Source forecasts (3) = 8 total features
- Rows: Multiple forecast windows (typically hundreds to thousands)

## 4. Second Tier Forecasts (Carbon Intensity)

### 4.1 Configure Second Tier for 168h

#### 4.1.1 Update Second Tier Configuration

```zsh
# Backup current config
cp src/secondTierConfig.json src/secondTierConfig.json.backup

# Check current configuration
grep -E "(TRAINING_WINDOW_HOURS|PREDICTION_WINDOW_HOURS|MAX_PREDICTION_WINDOW_HOURS)" src/secondTierConfig.json
```

**Required changes in [`src/secondTierConfig.json`](src/secondTierConfig.json):**
```json
{
  "TRAINING_WINDOW_HOURS": 168,
  "PREDICTION_WINDOW_HOURS": 168,
  "MAX_PREDICTION_WINDOW_HOURS": 168,
  "WRITE_CI_FORECASTS_TO_FILE": "True",
  "AECI": {
    "FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA.csv",
    "NUM_FORECAST_FEATURES": 8
  }
}
```

#### 4.1.2 Train/Test/Validation Split Considerations

For 168h forecasts, you must respect the following constraints:

**Minimum Requirements:**
- **Training Days**: Minimum 13 days (312+ hours) for CNN pattern learning
- **Validation Days**: Minimum 4 days to avoid array dimension errors
- **Maximum Test Days Formula**: `NUM_TEST_DAYS_MAX = Total_Days - 13 - NUM_VAL_DAYS`

**For datasets with 187 days (typical minimum):**
```json
{
  "NUM_TEST_DAYS": 170,  // Maximum possible
  "NUM_VAL_DAYS": 4      // Minimum required
}
```

**For larger datasets (365+ days):**
```json
{
  "NUM_TEST_DAYS": 30,
  "NUM_VAL_DAYS": 20
}

## Why NUM_TEST_DAYS Maximum is 170

### The Practical Calculation

When running 168-hour predictions with standard input data, you'll encounter a hard limit: **NUM_TEST_DAYS cannot exceed 170**. This isn't a configuration choice—it's a mathematical constraint based on available data.

### Understanding the 4488 Row Limit

When you check your first tier output file:

```bash
# Count rows in the forecast file
wc -l data/AECI/AECI_168hr_forecasts_DA.csv
```

You'll see:
```
4488 data/AECI/AECI_168hr_forecasts_DA.csv
```

This translates to exactly **187 days** of forecast data:
```python
4488 rows ÷ 24 hours/day = 187 days
```

### The Data Flow Bottleneck

The complete data pipeline shows where the constraint originates:

1. **Original Data (365 days)** → Provides one year of historical data
2. **First Tier Output (187 days)** → Loses 178 days due to sliding window mechanics
3. **Second Tier Maximum (170 days)** → Further constrained by training/validation requirements

### Why First Tier Only Outputs 187 Days

When the first tier processes 365 days of input data:

```python
# The math behind the constraint
Input_Days = 365
Input_Hours = 365 * 24 = 8,760 hours

# Each forecast needs 24h input + generates 168h output
Window_Requirement = 24 + 168 = 192 hours

# Calculate possible forecast windows
Forecast_Windows = (8760 - 192) / 24 + 1 = 357 windows

# Convert to days (each window is a daily forecast)
Forecast_Days = 357 / 24 = 187 days
```

The "missing" 178 days are consumed by:
- **First day (24 hours)**: Used as initial input window
- **Last 7 days (168 hours)**: Cannot generate complete 168-hour forecast
- **Sliding window overlap**: Each forecast consumes 24 hours of input

### The Complete Constraint Breakdown

With only 187 days of forecast data available:

```
Available: 187 days total
Required:
  - Minimum Training: 13 days (CNN-LSTM pattern learning)
  - Minimum Validation: 4 days (array dimension requirements)
  - Maximum Test: 187 - 13 - 4 = 170 days
```

### What Happens When You Try NUM_TEST_DAYS > 170

#### Example 1: NUM_TEST_DAYS = 173
```python
Test = 173, Val = 4
Training = 187 - 173 - 4 = 10 days
# FAILS: Insufficient training data (need 13 minimum)
# ERROR: "Model cannot learn patterns with only 10 days"
```

#### Example 2: NUM_TEST_DAYS = 180
```python
Test = 180, Val = 4
Training = 187 - 180 - 4 = 3 days
# FAILS: Critically insufficient training data
# ERROR: "CNN-LSTM requires minimum 312 hours (13 days)"
```

#### Example 3: NUM_TEST_DAYS = 186
```python
Test = 186, Val = 4
Training = 187 - 186 - 4 = -3 days
# FAILS: Negative training days!
# ERROR: "Index -3 is out of bounds for axis 0"
```

### How to Verify Your Available Days

Run this verification script to check your actual limits:

```bash
# Check your forecast file
echo "=== Checking NUM_TEST_DAYS Maximum ==="

# Count rows
ROWS=$(wc -l < data/AECI/AECI_168hr_forecasts_DA.csv)
echo "Forecast file rows: $ROWS"

# Calculate days
DAYS=$((ROWS / 24))
echo "Days of forecasts: $DAYS"

# Calculate maximum
MAX_TEST=$((DAYS - 13 - 4))
echo "Maximum NUM_TEST_DAYS: $MAX_TEST"

# Show the breakdown
echo ""
echo "Constraint breakdown:"
echo "  Total forecast days: $DAYS"
echo "  - Min training days: 13"
echo "  - Min validation days: 4"
echo "  = Max test days: $MAX_TEST"
```

Expected output:
```
Forecast file rows: 4488
Days of forecasts: 187
Maximum NUM_TEST_DAYS: 170

Constraint breakdown:
  Total forecast days: 187
  - Min training days: 13
  - Min validation days: 4
  = Max test days: 170
```

### How to Increase This Limit

To get more than 170 test days, you need more first tier output:

#### Option 1: Start with More Input Data
```python
# To get 200 test days:
Required_Forecast_Days = 200 + 13 + 4 = 217 days
Required_Input_Days = 217 + 8 = 225 days minimum

# To get 300 test days:
Required_Forecast_Days = 300 + 13 + 4 = 317 days
Required_Input_Days = 317 + 8 = 325 days minimum
```

#### Option 2: Use 2 Years of Historical Data
```python
# With 730 days (2 years) input:
Input_Hours = 730 * 24 = 17,520 hours
Forecast_Windows = (17520 - 192) / 24 + 1 = 722 windows
Forecast_Days = 722 / 24 ≈ 366 days

# New maximum:
MAX_TEST_DAYS = 366 - 13 - 4 = 349 days
```

#### Option 3: Reduce Prediction Window (Not Recommended for 168h)
If you switch to shorter prediction windows (e.g., 96 hours), you get more forecast days from the same input, but this defeats the purpose of 168-hour predictions.

### The Fundamental Chain

Remember: The bottleneck is the **first tier output**, not the second tier configuration:

```
365 days input → 187 days first tier → 170 days max test
```

No amount of configuration tweaking can overcome this mathematical reality. The only solution is to provide more input data to the first tier.

### Common Errors and Solutions

| NUM_TEST_DAYS | Result | Error Message | Solution |
|---------------|--------|---------------|----------|
| 170 | ✅ Works | None | Maximum valid value |
| 171 | ❌ Fails | "Insufficient training data" | Use 170 or less |
| 175 | ❌ Fails | "Only 8 days for training" | Use 170 or less |
| 180 | ❌ Fails | "Array dimension mismatch" | Use 170 or less |
| 185 | ❌ Fails | "Index out of bounds" | Use 170 or less |

### Quick Reference

For standard 365-day input with 168-hour predictions:
- **First Tier Output**: 187 days (4488 rows)
- **Minimum Training**: 13 days
- **Minimum Validation**: 4 days
- **Maximum Test**: **170 days**

This is a hard mathematical limit, not a configuration preference.

```

**Quick Reference:**
- For any dataset: `NUM_TEST_DAYS_MAX = Total_Days - 17` (assuming NUM_VAL_DAYS=4)
- Never exceed this maximum or you'll get array dimension errors

## Adapting for Other Prediction Windows

### General Formula for Variable Prediction Windows

While this runbook focuses on 168-hour predictions, CarbonCast can be configured for different prediction windows (24, 48, 72, 96, ... up to 168 hours). Here's how to adapt:

#### Universal Buffer Formula

```python
Buffer_Days = (PREDICTION_WINDOW_HOURS - 24) / 24
```

#### Universal Maximum Test Days Formula

```python
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - (PREDICTION_WINDOW_HOURS/24 - 1)
```

### Configuration Table for Different Prediction Windows

| Prediction Window | Buffer Days | Min Training Days | Min Val Days | Quick Formula (min val=4) | Weather Config (days) |
|-------------------|-------------|-------------------|--------------|----------------------------|----------------------|
| 24 hours (1 day)  | 0 | 7 | 4 | Total_Days - 11 | PREDICTION_PERIOD_DAYS = 1 |
| 48 hours (2 days) | 1 | 8 | 4 | Total_Days - 13 | PREDICTION_PERIOD_DAYS = 2 |
| 72 hours (3 days) | 2 | 10 | 4 | Total_Days - 16 | PREDICTION_PERIOD_DAYS = 3 |
| 96 hours (4 days) | 3 | 11 | 4 | Total_Days - 18 | PREDICTION_PERIOD_DAYS = 4 |
| 120 hours (5 days) | 4 | 12 | 4 | Total_Days - 20 | PREDICTION_PERIOD_DAYS = 5 |
| 144 hours (6 days) | 5 | 12 | 4 | Total_Days - 21 | PREDICTION_PERIOD_DAYS = 6 |
| 168 hours (7 days) | 6 | 13 | 4 | Total_Days - 23 | PREDICTION_PERIOD_DAYS = 7 |

### Adapting Configuration Files for Different Windows

#### Example: 24-Hour Prediction Configuration

**Weather Processing ([`src/weather/cleanWeatherData.py`](src/weather/cleanWeatherData.py)):**
```python
PREDICTION_PERIOD_DAYS = 1  # For 24-hour forecasts
```

**First Tier ([`src/firstTierConfig.json`](src/firstTierConfig.json)):**
```json
{
  "PREDICTION_WINDOW_HOURS": 24,
  "MAX_PREDICTION_WINDOW_HOURS": 24
}
```

**Second Tier ([`src/secondTierConfig.json`](src/secondTierConfig.json)):**
```json
{
  "TRAINING_WINDOW_HOURS": 24,
  "PREDICTION_WINDOW_HOURS": 24,
  "MAX_PREDICTION_WINDOW_HOURS": 24,
  "NUM_TEST_DAYS": 89,  // For 100 days: 100 - 7 - 4 - 0 = 89
  "NUM_VAL_DAYS": 4
}
```

#### Example: 48-Hour Prediction Configuration

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 2  # For 48-hour forecasts
```

**First Tier:**
```json
{
  "PREDICTION_WINDOW_HOURS": 48,
  "MAX_PREDICTION_WINDOW_HOURS": 48
}
```

**Second Tier:**
```json
{
  "TRAINING_WINDOW_HOURS": 48,
  "PREDICTION_WINDOW_HOURS": 48,
  "MAX_PREDICTION_WINDOW_HOURS": 48,
  "NUM_TEST_DAYS": 87,  // For 100 days: 100 - 8 - 4 - 1 = 87
  "NUM_VAL_DAYS": 4
}
```

#### Example: 72-Hour Prediction Configuration

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 3  # For 72-hour forecasts
```

**First Tier:**
```json
{
  "PREDICTION_WINDOW_HOURS": 72,
  "MAX_PREDICTION_WINDOW_HOURS": 72
}
```

**Second Tier:**
```json
{
  "TRAINING_WINDOW_HOURS": 72,
  "PREDICTION_WINDOW_HOURS": 72,
  "MAX_PREDICTION_WINDOW_HOURS": 72,
  "NUM_TEST_DAYS": 84,  // For 100 days: 100 - 10 - 4 - 2 = 84
  "NUM_VAL_DAYS": 4
}
```

#### Example: 96-Hour Prediction Configuration

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 4  # For 96-hour forecasts
```

**First Tier:**
```json
{
  "PREDICTION_WINDOW_HOURS": 96,
  "MAX_PREDICTION_WINDOW_HOURS": 96
}
```

**Second Tier:**
```json
{
  "TRAINING_WINDOW_HOURS": 96,
  "PREDICTION_WINDOW_HOURS": 96,
  "MAX_PREDICTION_WINDOW_HOURS": 96,
  "NUM_TEST_DAYS": 82,  // For 100 days: 100 - 11 - 4 - 3 = 82
  "NUM_VAL_DAYS": 4
}
```

### Key Differences by Prediction Window

#### Short-term Predictions (24-48 hours)
- **Advantages**: Higher accuracy, less training data needed, faster training
- **Buffer Requirements**: 0-1 buffer days
- **Minimum Training**: 7-8 days
- **Use Cases**: Day-ahead energy markets, operational planning

#### Medium-term Predictions (72-96 hours)
- **Advantages**: Balance of accuracy and horizon, captures weekly patterns
- **Buffer Requirements**: 2-3 buffer days
- **Minimum Training**: 10-11 days
- **Use Cases**: Multi-day planning, weekend forecasting

#### Long-term Predictions (120-168 hours)
- **Advantages**: Week-ahead planning, strategic decisions
- **Buffer Requirements**: 4-6 buffer days
- **Minimum Training**: 12-13 days
- **Use Cases**: Weekly scheduling, maintenance planning, market bidding

### Calculating Data Requirements for Any Window

Use this formula to determine your data requirements:

```python
def calculate_data_requirements(prediction_hours, total_days_available):
    """
    Calculate data split for any prediction window
    
    Args:
        prediction_hours: Prediction window in hours (24-168)
        total_days_available: Total days of historical data
    
    Returns:
        dict: Data split configuration
    """
    # Calculate buffer days
    buffer_days = (prediction_hours - 24) / 24
    
    # Determine minimum training days based on prediction window
    if prediction_hours <= 48:
        min_training_days = 7 + (prediction_hours - 24) / 24
    elif prediction_hours <= 96:
        min_training_days = 10 + (prediction_hours - 72) / 24
    else:
        min_training_days = 12 + (prediction_hours - 120) / 48
    
    # Minimum validation days
    min_val_days = 4
    
    # Calculate maximum test days
    max_test_days = total_days_available - min_training_days - min_val_days - buffer_days
    
    return {
        "prediction_hours": prediction_hours,
        "buffer_days": int(buffer_days),
        "min_training_days": int(min_training_days),
        "min_val_days": min_val_days,
        "max_test_days": int(max_test_days),
        "config": {
            "NUM_TEST_DAYS": int(max_test_days),
            "NUM_VAL_DAYS": min_val_days,
            "PREDICTION_WINDOW_HOURS": prediction_hours,
            "PREDICTION_PERIOD_DAYS": int(prediction_hours / 24)
        }
    }

# Example usage:
# For 72-hour predictions with 100 days of data:
result = calculate_data_requirements(72, 100)
print(f"Maximum test days: {result['max_test_days']}")
print(f"Buffer days needed: {result['buffer_days']}")
print(f"Minimum training days: {result['min_training_days']}")
```


#### 4.1.3 Understanding Test Period Calculation

**How NUM_TEST_DAYS Determines the Test Period:**

The test period is calculated by counting **backwards from the end** of your available data:

```python
# Mathematical formula:
test_start_index = total_forecast_windows - NUM_TEST_DAYS
test_end_index = total_forecast_windows

# Example with 720 total windows and NUM_TEST_DAYS=30:
test_start = 720 - 30 = window 690
# This means the last 30 windows are used for testing
```

**Buffer Period Calculation (Critical for Data Integrity):**

The 6-day buffer (168-24=144 hours) prevents data leakage between training and test sets:

```python
# Buffer calculation:
buffer_hours = PREDICTION_WINDOW_HOURS - TRAINING_WINDOW_HOURS
            = 168 - 24
            = 144 hours (6 days)

# Why this matters:
# - A forecast starting on day N predicts hours 24-191 from day N
# - This covers days N+1 through N+7
# - Without buffer, test data would "leak" into training period
```

#### 4.1.4 Maximum NUM_TEST_DAYS Calculation

**Master Formula:**
```python
NUM_TEST_DAYS_MAX = Total_Forecast_Days - 13 - NUM_VAL_DAYS
```

**Constraint Explanation:**
- **13 days minimum training**: CNN-LSTM architecture requires at least 312 hours for:
  - Learning temporal patterns effectively
  - Avoiding underfitting with insufficient samples
  - Ensuring stable gradient updates
  - Capturing at least one complete weekly cycle

- **4 days minimum validation**: Required to:
  - Prevent array dimension errors in model evaluation
  - Provide sufficient data for early stopping
  - Enable meaningful validation metrics
  - Support proper batch formation

**Example with 187 days of data:**
```python
# Given:
Total_Days = 187
NUM_VAL_DAYS = 4  # Minimum

# Calculate:
NUM_TEST_DAYS_MAX = 187 - 13 - 4 = 170

# Result:
# Test: 170 days (maximum possible)
# Validation: 4 days (minimum required)
# Training: 13 days (minimum required)
```

#### 4.1.5 Data Requirements for Full Year Forecasts

**To generate 1 full year (365 days) of forecasts:**

```python
# Required historical data calculation:
required_days = forecast_days + horizon_days + training_days
              = 365 + 7 + 365  # minimum
              = 737 days (~2 years)

# Mathematical formula for output dimensions:
num_forecast_windows = (total_hours - 191) / 24
                     = (737 * 24 - 191) / 24
                     = 729 windows

# Each window produces:
predictions_per_window = 168 hours
total_predictions = 729 * 168 = 122,472 hourly predictions
```

### 4.2 Run Second Tier Forecasts

#### 4.2.1 Direct Carbon Intensity Model

```zsh
# Train direct CI model
micromamba run -n carboncast-310 python src/secondTierForecasts.py src/secondTierConfig.json -d
```

**Expected runtime:** 20-60 minutes

**Sample progress output:**
```
Loading forecast data for AECI...
Data shape: (150, 8) - 150 forecast windows, 8 features
Train/Val/Test split: 110/20/20
Training direct CI model...
Epoch 1/150: loss=0.0456, val_loss=0.0523, MAPE=12.34%
...
Best model saved with validation MAPE: 8.45%
```

#### 4.2.2 Lifecycle Carbon Intensity Model (Optional)

```zsh
# Train lifecycle CI model
micromamba run -n carboncast-310 python src/secondTierForecasts.py src/secondTierConfig.json -l
```

### 4.3 Verify Second Tier Results

#### 4.3.1 Check CI Forecast Outputs

```zsh
# Verify CI forecast files
ls -la CI_forecast_data/AECI/
```

**Expected files:**
```
-rw-r--r--  AECI_direct_168hr_CI_forecasts_0.csv
-rw-r--r--  AECI_lifecycle_168hr_CI_forecasts_0.csv  (if -l used)
```

#### 4.3.2 Check Model Performance

```zsh
# Check MAPE results
cat data/AECI/AECI_MAPE_iter0.txt
```

**Expected performance for 168h forecasts:**
```
Direct CI Model MAPE: 8.45%
Lifecycle CI Model MAPE: 9.23%
```

**Good performance benchmarks:**
- MAPE < 10%: Excellent
- MAPE 10-15%: Good
- MAPE 15-20%: Acceptable
- MAPE > 20%: Needs investigation

#### 4.3.3 Check Saved Models

```zsh
# Verify saved second tier models
ls -la saved_second_tier_models/direct/AECI/
```

**Expected files:**
```
-rw-r--r--  AECI.h5
-rw-r--r--  AECI_scaler_max.txt
-rw-r--r--  AECI_scaler_min.txt
```

## 5. Sample Outputs and Verification

### 5.1 Complete Pipeline Verification

```zsh
# Run complete verification check
echo "=== CarbonCast 168h Pipeline Verification ==="

echo "1. Environment Check:"
micromamba run -n carboncast-310 python -c "import tensorflow as tf; print(f'✅ TensorFlow {tf.__version__} ready')"

echo "2. Weather Data:"
ls extn/AECI_*.csv | wc -l | xargs echo "  CSV files created:"
wc -l extn/AECI_weather_forecast_2023.csv | xargs echo "  Hourly forecast rows:"

echo "3. First Tier:"
ls data/AECI/fuel_forecast/AECI_ANN_*_iter0.csv | wc -l | xargs echo "  Source forecasts:"
ls -la data/AECI/AECI_168hr_forecasts_DA.csv | awk '{print "  Combined matrix: " $5 " bytes"}'

echo "4. Second Tier:"
ls CI_forecast_data/AECI/*168hr*.csv | wc -l | xargs echo "  CI forecasts:"
if [ -f data/AECI/AECI_MAPE_iter0.txt ]; then
  echo "  MAPE results:"
  cat data/AECI/AECI_MAPE_iter0.txt | head -3
fi

echo "=== Verification Complete ==="
```

### 5.2 Sample Output Inspection

#### 5.2.1 Weather Forecast Format

```zsh
# Inspect weather forecast structure
echo "Weather forecast sample (first 3 rows):"
head -n 3 extn/AECI_weather_forecast_2023.csv | column -t -s','
```

#### 5.2.2 First Tier Source Forecasts

```zsh
# Inspect source forecast format
echo "Coal generation forecast sample:"
head -n 3 data/AECI/fuel_forecast/AECI_ANN_coal_iter0.csv | column -t -s','
```

#### 5.2.3 CI Forecast Output

```zsh
# Inspect CI forecast format
echo "Direct CI forecast sample:"
head -n 3 CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts_0.csv | column -t -s','
```

**Expected CI forecast columns:**
```
time                  predicted_CI    actual_CI    hour_of_forecast
2023-01-01 00:00:00  450.23          448.56       1
2023-01-01 01:00:00  445.67          443.21       2
2023-01-01 02:00:00  441.89          439.45       3
```

## 6. Comprehensive Troubleshooting

### 6.1 Environment Issues

#### 6.1.1 TensorFlow Metal Problems

**Problem:** TensorFlow not using Metal GPU acceleration
```zsh
# Check MPS availability
python -c "import tensorflow as tf; print('MPS available:', len(tf.config.list_physical_devices('GPU')) > 0)"
```

**Solution:**
```zsh
# Reinstall TensorFlow Metal
pip uninstall tensorflow-macos tensorflow-metal
pip install tensorflow-macos==2.9.0 tensorflow-metal==0.5.0
```

#### 6.1.2 wgrib2 Not Found

**Problem:** `wgrib2: command not found` within micromamba environment

**Solution:**
```zsh
# Ensure wgrib2 is in system PATH
echo $PATH | grep -q "/opt/homebrew/bin" || export PATH="/opt/homebrew/bin:$PATH"

# Test access
micromamba run -n carboncast-310 which wgrib2

# If still not found, create symlink
micromamba run -n carboncast-310 ln -sf /opt/homebrew/bin/wgrib2 $CONDA_PREFIX/bin/wgrib2
```

### 6.2 Weather Data Processing Issues

#### 6.2.1 GRIB2 Files Not Found

**Problem:** `FileNotFoundError` during weather extraction

**Diagnostic:**
```zsh
# Check GRIB2 file structure
find 168h_grib2_data/combined/AECI/ -name "*.grib2" | head -5
ls -la 168h_grib2_data/combined/AECI/*/
```

**Solution:**
- Verify GRIB2 data was properly downloaded and organized
- Check that combined folders exist and contain .grib2 files
- Ensure region name matches exactly (case-sensitive)

#### 6.2.2 Infinite Loop in Weather Processing

**Problem:** Weather extraction appears stuck or running infinitely

**Diagnostic:**
```zsh
# Check if files are being created
watch "ls -la extn/AECI_*.csv"

# Monitor system resources
top -o CPU | grep python
```

**Solution:**
```zsh
# Kill stuck process
pkill -f separateWeatherByRegion.py

# Restart with single file debug
python src/weather/separateWeatherByRegion.py US 0 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022 \
  --out extn/ \
  --stream
```

#### 6.2.3 Empty or Corrupted Weather CSVs

**Problem:** CSV files created but contain only headers or NaN values

**Diagnostic:**
```zsh
# Check file contents
wc -l extn/AECI_*.csv
head -n 10 extn/AECI_WIND_SPEED.csv
tail -n 10 extn/AECI_WIND_SPEED.csv
```

**Solution:**
```zsh
# Remove corrupted files and restart
rm extn/AECI_*.csv

# Verify GRIB2 file integrity
wgrib2 -s $(find 168h_grib2_data/combined/AECI/ugrd_vgrd/ -name "*.grib2" | head -1) | head -5
```

### 6.3 First Tier Issues

#### 6.3.1 Missing Source Production Data

**Problem:** `FileNotFoundError: data/AECI/fuel_forecast/AECI_source_prod_clean.csv`

**Solution:**
```zsh
# Check for raw source data
ls -la data/AECI/fuel_forecast/

# If raw data exists, clean it first
# If no source data exists, you need to obtain historical generation data for AECI
```

#### 6.3.2 Configuration Mismatch Errors

**Problem:** Weather forecast file path not found or feature count mismatch

**Diagnostic:**
```zsh
# Verify paths in config match actual files
grep "WEATHER_FORECAST_IN_FILE_NAME" src/firstTierConfig.json
ls -la extn/AECI_weather_forecast_2023.csv
```

**Solution:**
```zsh
# Update config paths to match actual file locations
# Ensure weather file was created successfully in previous step
```

#### 6.3.3 Memory Issues During Training

**Problem:** Out of memory errors during first tier training

**Solution:**
```zsh
# Reduce batch size in firstTierConfig.json
"BATCH_SIZE": [5]  # Reduce from default 32

# Monitor memory usage
top -o MEM | grep python
```

### 6.4 Second Tier Issues

#### 6.4.1 "Index 0 is out of bounds" Error

**Problem:** Scaling error during second tier training

**Diagnostic:**
```zsh
# Check forecast matrix dimensions
head -n 1 data/AECI/AECI_168hr_forecasts_DA.csv
wc -l data/AECI/AECI_168hr_forecasts_DA.csv
```

**Solution:**
```zsh
# Reduce test/validation split for small datasets
# Edit secondTierConfig.json:
"NUM_TEST_DAYS": 10,  # Reduce from 30
"NUM_VAL_DAYS": 8     # Reduce from 20
```

#### 6.4.2 High MAPE Values (> 20%)

**Problem:** Poor model performance

**Diagnostic Solutions:**
1. **Check data quality:**
   ```zsh
   # Look for NaN or infinite values
   python -c "import pandas as pd; df=pd.read_csv('data/AECI/AECI_168hr_forecasts_DA.csv'); print('NaN count:', df.isnull().sum().sum()); print('Inf count:', np.isinf(df.select_dtypes(include=[np.number])).sum().sum())"
   ```

2. **Verify feature scaling:**
   ```zsh
   # Check if features have reasonable ranges
   python -c "import pandas as pd; df=pd.read_csv('data/AECI/AECI_168hr_forecasts_DA.csv'); print(df.describe())"
   ```

3. **Increase training data:**
   - Use more historical years
   - Reduce test/validation splits

#### 6.4.3 Model Convergence Issues

**Problem:** Model not converging or loss not decreasing

**Solution:**
```zsh
# Remove previous model to retrain
rm -f saved_second_tier_models/direct/AECI/AECI.h5

# Adjust learning parameters in config:
"EPOCHS": [200],      # Increase from 150
"LEARNING_RATE": [0.001]  # Reduce from 0.01
```

### 6.5 Performance and Resource Issues

#### 6.5.1 Slow Processing on Apple Silicon

**Optimization tips:**
```zsh
# Verify Metal GPU is being used
python -c "
import tensorflow as tf
print('GPU devices:', tf.config.list_physical_devices('GPU'))
with tf.device('/GPU:0'):
    print('GPU execution test passed')
"

# Monitor GPU usage
sudo powermetrics --samplers gpu_power -a --hide-cpu-duty-cycle -n 10
```

#### 6.5.2 Disk Space Issues

**Monitor disk usage:**
```zsh
# Check space usage by component
du -sh 168h_grib2_data/
du -sh extn/
du -sh data/
du -sh saved_*_models/
du -sh CI_forecast_data/
```

**Cleanup temporary files:**
```zsh
# Remove intermediate files if space is limited
rm -f extn/*aggregated*.csv  # Keep only weather_forecast files
```

## 7. Quick End-to-End Test

### 7.1 Smoke Test (Single Region)

```zsh
#!/bin/bash
echo "=== CarbonCast 168h Smoke Test ==="

# 1. Environment verification
echo "Step 1: Environment check"
micromamba activate carboncast-310
python -c "import tensorflow as tf; print('✅ TensorFlow ready:', tf.__version__)"

# 2. Quick weather extraction (wind only)
echo "Step 2: Weather extraction (wind only)"
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 0 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2023 \
  --out extn/ \
  --stream

# 3. Weather cleaning
echo "Step 3: Weather cleaning"
micromamba run -n carboncast-310 python src/weather/cleanWeatherData.py US extn/

# 4. First tier
echo "Step 4: First tier forecasts"
micromamba run -n carboncast-310 python src/firstTierForecasts.py src/firstTierConfig.json

# 5. Second tier (direct only)
echo "Step 5: Second tier CI forecasts"
micromamba run -n carboncast-310 python src/secondTierForecasts.py src/secondTierConfig.json -d

# 6. Verification
echo "Step 6: Results verification"
ls CI_forecast_data/AECI/*direct*168hr*.csv && echo "✅ CI forecasts created" || echo "❌ CI forecasts missing"

echo "=== Smoke Test Complete ==="
```

### 7.2 Performance Benchmarks

**Expected runtimes by component (AECI region, 2 years data):**

| Component | Expected Time | Notes |
|-----------|---------------|--------|
| Environment setup | 5-10 minutes | One-time setup |
| GRIB2 extraction (all variables) | 2-5 hours | Can run in parallel |
| Weather cleaning | 2-5 minutes | Fast processing |
| First tier training | 15-45 minutes | 3 source types |
| Second tier training | 20-60 minutes | Direct CI model |
| **Total pipeline** | **3-6 hours** | Varies by hardware |

**Hardware-specific performance:**
- **M1 Mac (8GB RAM):** Use smaller batch sizes, expect longer runtimes
- **M1 Pro/Max (16GB+ RAM):** Can use default settings
- **Intel Mac:** Install x86 TensorFlow, significantly slower

## 8. Key File Locations Reference

### 8.1 Input Data Paths
```
168h_grib2_data/combined/<REGION>/    # GRIB2 weather data
├── apcp/                             # Precipitation files
├── dswrf/                            # Solar radiation files  
├── tmp_dpt/                          # Temperature/dewpoint files
└── ugrd_vgrd/                        # Wind component files

data/<REGION>/fuel_forecast/          # Historical generation data
└── <REGION>_source_prod_clean.csv    # Clean source production data
```

### 8.2 Intermediate Outputs
```
extn/                                 # Weather processing outputs
├── <REGION>_WIND_SPEED.csv          # 3-hourly wind data
├── <REGION>_TEMP.csv                # 3-hourly temperature
├── <REGION>_DPT.csv                 # 3-hourly dewpoint
├── <REGION>_DSWRF.csv               # 3-hourly solar radiation
├── <REGION>_APCP.csv                # 3-hourly precipitation
├── <REGION>_aggregated_weather_data_2023.csv  # Intermediate
└── <REGION>_weather_forecast_2023.csv         # Hourly weather features
```

### 8.3 First Tier Outputs
```
data/<REGION>/fuel_forecast/          # Per-source forecasts
├── <REGION>_ANN_coal_iter0.csv      # Coal generation forecasts
├── <REGION>_ANN_nat_gas_iter0.csv   # Natural gas forecasts  
└── <REGION>_ANN_wind_iter0.csv      # Wind generation forecasts

data/<REGION>/                        # Combined forecasts
└── <REGION>_168hr_forecasts_DA.csv  # Feature matrix for Tier-2

saved_first_tier_models/<REGION>/     # Trained models
├── <REGION>_coal_best_model_ann.h5  # Coal model
├── <REGION>_nat_gas_best_model_ann.h5  # Gas model
└── <REGION>_wind_best_model_ann.h5  # Wind model
```

### 8.4 Second Tier Outputs
```
CI_forecast_data/<REGION>/            # Carbon intensity forecasts
├── <REGION>_direct_168hr_CI_forecasts_0.csv     # Direct CI model
└── <REGION>_lifecycle_168hr_CI_forecasts_0.csv  # Lifecycle CI model

saved_second_tier_models/direct/<REGION>/        # Trained CI models
├── <REGION>.h5                      # TensorFlow model
├── <REGION>_scaler_min.txt          # Feature scaling parameters
└── <REGION>_scaler_max.txt

data/<REGION>/                        # Performance metrics
└── <REGION>_MAPE_iter0.txt          # Model accuracy results
```

## 9. Configuration Summary

### 9.1 Critical Configuration Changes for 168h

**[`src/weather/cleanWeatherData.py`](src/weather/cleanWeatherData.py:101):**
```python
PREDICTION_PERIOD_DAYS = 7  # Changed from 4 for 168h forecasts
```

**[`src/firstTierConfig.json`](src/firstTierConfig.json):**
```json
{
  "PREDICTION_WINDOW_HOURS": 168,
  "MAX_PREDICTION_WINDOW_HOURS": 168,
  "<REGION>": {
    "WEATHER_FORECAST_IN_FILE_NAME": "extn/<REGION>_weather_forecast_2023.csv"
  }
}
```

**[`src/secondTierConfig.json`](src/secondTierConfig.json):**
```json
{
  "TRAINING_WINDOW_HOURS": 168,
  "PREDICTION_WINDOW_HOURS": 168,
  "MAX_PREDICTION_WINDOW_HOURS": 168,
  "WRITE_CI_FORECASTS_TO_FILE": "True",
  "<REGION>": {
    "FORECAST_IN_FILE_NAME": "data/<REGION>/<REGION>_168hr_forecasts_DA.csv",
    "NUM_FORECAST_FEATURES": 8
  }
}
```

## How to Generate Forecasts for All of 2023

### Overview

This section provides practical steps to configure CarbonCast for generating carbon intensity forecasts for the entire year of 2023. This requires approximately 2 years of historical data (January 2022 - December 2023).

### Data Requirements

To generate forecasts for all 365 days of 2023:

#### Input Data Needed
- **Historical Period**: January 1, 2022 - December 31, 2023
- **Total Days**: ~730-800 days (2+ years)
- **Minimum Required**: 764 days

#### Mathematical Breakdown
```python
# Working backwards from desired output
Desired_Forecast_Days = 365  # All of 2023
Min_Training_Days = 13       # CNN-LSTM requirement
Min_Validation_Days = 4      # Array dimension requirement

# Second tier needs from first tier
Second_Tier_Input_Days = 365 + 13 + 4 = 382 days

# First tier output (approximately 50% of input)
First_Tier_Input_Days = 382 × 2 = 764 days minimum

# Recommended: 2 full years with buffer
Recommended_Input = 730-800 days
```

### Step-by-Step Configuration

#### Step 1: Prepare Data for 2022-2023

Ensure you have GRIB2 weather data and historical generation data for the full period:

```bash
# Verify GRIB2 data covers 2022-2023
ls -la 168h_grib2_data/combined/AECI/ugrd_vgrd/ | grep -E "2022|2023" | wc -l
# Should show files for both years

# Verify historical generation data
head -1 data/AECI/fuel_forecast/AECI_source_prod_clean.csv
tail -1 data/AECI/fuel_forecast/AECI_source_prod_clean.csv
# Should show dates from Jan 2022 to Dec 2023
```

#### Step 2: Extract Weather Data for Both Years

Process weather data for the complete 2-year period:

```bash
# Extract all weather variables for 2022-2023
# Wind (Index 0)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 0 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Temperature/Dewpoint (Index 1)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 1 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Solar Radiation (Index 2)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 2 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream

# Precipitation (Index 3)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py US 3 \
  --base 168h_grib2_data/combined/AECI \
  --regions AECI \
  --years 2022,2023 \
  --out extn/ \
  --stream
```

#### Step 3: Clean Weather Data

Process the extracted weather data:

```bash
# Clean and aggregate weather data
micromamba run -n carboncast-310 python src/weather/cleanWeatherData.py US extn/

# Verify output files
ls -la extn/AECI_weather_forecast*.csv
# Should see files for both 2022 and 2023
```

#### Step 4: Configure First Tier for Extended Output

Update [`src/firstTierConfig.json`](src/firstTierConfig.json) to process the full dataset:

```json
{
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [150],
    "BATCH_SIZE": [32],
    "AECI": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2022_2023.csv",
        "SOURCE_PROD_IN_FILE_NAME": "data/AECI/fuel_forecast/AECI_source_prod_clean_2022_2023.csv",
        "FORECAST_OUT_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA_full_year.csv",
        "NUM_FORECAST_FEATURES": 8,
        "NUM_WEATHER_FEATURES": 5,
        "SOURCES": ["coal", "nat_gas", "wind"]
    }
}
```

**Note**: Ensure the first tier is configured to process all available data and output at least 382 days.

#### Step 5: Run First Tier with Extended Data

```bash
# Run first tier forecasts
micromamba run -n carboncast-310 python src/firstTierForecasts.py src/firstTierConfig.json

# Verify output size
wc -l data/AECI/AECI_168hr_forecasts_DA_full_year.csv
# Should show approximately 9,168 rows (382 days × 24 hours)
```

#### Step 6: Configure Second Tier for Full Year

Update [`src/secondTierConfig.json`](src/secondTierConfig.json):

```json
{
    "TRAINING_WINDOW_HOURS": 168,
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "NUM_TEST_DAYS": 365,  // Full year of 2023
    "NUM_VAL_DAYS": 4,      // Minimum validation
    "EPOCHS": [200],        // More epochs for larger dataset
    "BATCH_SIZE": [32],
    "WRITE_CI_FORECASTS_TO_FILE": "True",
    "AECI": {
        "FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA_full_year.csv",
        "DIRECT_CI_IN_FILE_NAME": "data/AECI/AECI_direct_emissions.csv",
        "LIFECYCLE_CI_IN_FILE_NAME": "data/AECI/AECI_lifecycle_emissions.csv",
        "DIRECT_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts_2023",
        "LIFECYCLE_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_lifecycle_168hr_CI_forecasts_2023",
        "NUM_FORECAST_FEATURES": 8
    }
}
```

#### Step 7: Run Second Tier for Full Year

```bash
# Train and generate direct CI forecasts for 2023
micromamba run -n carboncast-310 python src/secondTierForecasts.py src/secondTierConfig.json -d

# Optional: Train lifecycle CI model
micromamba run -n carboncast-310 python src/secondTierForecasts.py src/secondTierConfig.json -l
```

### Verification Steps

#### Check Data Sufficiency

```bash
# Verify first tier output is sufficient
echo "=== Checking Data Sufficiency for Full Year ==="

# Count first tier output days
ROWS=$(wc -l < data/AECI/AECI_168hr_forecasts_DA_full_year.csv)
DAYS=$((ROWS / 24))
echo "First tier output: $DAYS days"

# Check against requirements
REQUIRED=382  # 365 + 13 + 4
if [ $DAYS -ge $REQUIRED ]; then
    echo "✅ Sufficient data for full year forecasting"
    echo "   Can forecast 365 days with $((DAYS - 17)) days maximum"
else
    SHORTFALL=$((REQUIRED - DAYS))
    echo "❌ Insufficient by $SHORTFALL days"
    echo "   Maximum NUM_TEST_DAYS: $((DAYS - 17))"
fi
```

#### Verify Output Coverage

```bash
# Check CI forecast coverage
echo "=== Verifying 2023 Forecast Coverage ==="

# Count forecast windows
FORECAST_FILE="CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts_2023_0.csv"
if [ -f "$FORECAST_FILE" ]; then
    WINDOWS=$(tail -n +2 "$FORECAST_FILE" | cut -d',' -f4 | sort -u | wc -l)
    echo "Forecast windows generated: $WINDOWS"
    echo "Coverage: $WINDOWS days of 2023"
    
    # Check date range
    FIRST_DATE=$(head -2 "$FORECAST_FILE" | tail -1 | cut -d',' -f1)
    LAST_DATE=$(tail -1 "$FORECAST_FILE" | cut -d',' -f1)
    echo "Date range: $FIRST_DATE to $LAST_DATE"
else
    echo "❌ Forecast file not found"
fi
```

### Expected Outputs

With 2 years of input data (730 days), you should get:

1. **First Tier Output:**
   - Approximately 366 days of forecasts
   - File: `AECI_168hr_forecasts_DA_full_year.csv`
   - Rows: ~8,784 (366 × 24)

2. **Second Tier Output:**
   - 359 forecast windows covering most of 2023
   - File: `AECI_direct_168hr_CI_forecasts_2023_0.csv`
   - Total predictions: 60,312 hourly CI values (359 × 168)
   - Coverage: January 7 - December 31, 2023

### Troubleshooting Full Year Forecasting

#### Issue: "Insufficient first tier output"

**Problem:** First tier doesn't generate enough days for full year
```
First tier output: 350 days
Required: 382 days
Shortfall: 32 days
```

**Solution:**
1. Extend input data period:
   ```bash
   # Use 2.5 years instead of 2
   --years 2021,2022,2023
   ```

2. Or reduce NUM_TEST_DAYS:
   ```json
   "NUM_TEST_DAYS": 333  // 350 - 13 - 4
   ```

#### Issue: "Memory errors with large dataset"

**Problem:** Out of memory when processing 2+ years

**Solution:**
1. Reduce batch size:
   ```json
   "BATCH_SIZE": [8]  // From 32
   ```

2. Process in chunks:
   ```bash
   # Process one year at a time, then combine
   ```

3. Use gradient accumulation:
   ```json
   "GRADIENT_ACCUMULATION_STEPS": 4
   ```

#### Issue: "Configuration mismatch"

**Problem:** File paths don't match between tiers

**Solution:**
Ensure consistency:
```json
// First Tier output:
"FORECAST_OUT_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA_full_year.csv"

// Must match Second Tier input:
"FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA_full_year.csv"
```

### Alternative Configurations

#### Configuration for 6 Months (H1 2023)

```json
// Second Tier
{
    "NUM_TEST_DAYS": 181,  // Jan-Jun 2023
    "NUM_VAL_DAYS": 4,
    // Requires: 181 + 13 + 4 = 198 days from first tier
    // Input needed: ~400 days
}
```

#### Configuration for Q1 2023 (3 Months)

```json
// Second Tier
{
    "NUM_TEST_DAYS": 90,  // Jan-Mar 2023
    "NUM_VAL_DAYS": 4,
    // Requires: 90 + 13 + 4 = 107 days from first tier
    // Input needed: ~220 days
}
```

### Quick Reference Formula

For any desired forecast period:

```python
# Calculate required input data
def calculate_input_requirements(forecast_days):
    """
    Calculate input data requirements for desired forecast period
    
    Args:
        forecast_days: Number of days to forecast (e.g., 365 for full year)
    
    Returns:
        dict: Input requirements
    """
    # Constants
    MIN_TRAINING = 13
    MIN_VALIDATION = 4
    
    # Second tier needs
    second_tier_days = forecast_days + MIN_TRAINING + MIN_VALIDATION
    
    # First tier input (approximate 50% conversion)
    first_tier_input = second_tier_days * 2
    
    # Add 10% safety margin
    recommended_input = int(first_tier_input * 1.1)
    
    return {
        "forecast_days": forecast_days,
        "second_tier_needs": second_tier_days,
        "minimum_input_days": first_tier_input,
        "recommended_input_days": recommended_input
    }

# Example: Full year
result = calculate_input_requirements(365)
print(f"To forecast 365 days:")
print(f"  Minimum input: {result['minimum_input_days']} days")
print(f"  Recommended: {result['recommended_input_days']} days")
```

### Summary

To generate forecasts for all of 2023:
1. **Collect** 730-800 days of historical data (Jan 2022 - Dec 2023)
2. **Process** weather data for the full 2-year period
3. **Configure** first tier to output 382+ days
4. **Set** NUM_TEST_DAYS = 365 in second tier
5. **Run** both tiers with extended configurations
6. **Verify** output covers the desired period

Key Formula: **Input_Data_Days ≈ (Desired_Forecast_Days + 17) × 2**
