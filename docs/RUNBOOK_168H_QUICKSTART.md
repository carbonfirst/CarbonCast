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

For 168h forecasts, consider adjusting split parameters based on your data size:

**For datasets with limited windows (< 100):**
```json
{
  "NUM_TEST_DAYS": 12,
  "NUM_VAL_DAYS": 10
}
```

**For larger datasets (> 200 windows):**
```json
{
  "NUM_TEST_DAYS": 30,
  "NUM_VAL_DAYS": 20
}
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