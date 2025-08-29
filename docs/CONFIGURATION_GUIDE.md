# CarbonCast Configuration Guide

## Table of Contents
1. [Configuration Overview](#configuration-overview)
2. [First Tier Configuration](#first-tier-configuration)
3. [Second Tier Configuration](#second-tier-configuration)
4. [Weather Processing Configuration](#weather-processing-configuration)
5. [Configuration Scenarios](#configuration-scenarios)
6. [Performance Tuning](#performance-tuning)
7. [Troubleshooting Configuration Issues](#troubleshooting-configuration-issues)

---

## Configuration Overview

CarbonCast uses JSON configuration files to control pipeline behavior. There are three main configuration points:

1. **Weather Processing**: Hardcoded in `src/weather/cleanWeatherData.py`
2. **First Tier**: `src/firstTierConfig.json`
3. **Second Tier**: `src/secondTierConfig.json`

### Configuration Hierarchy

```
Weather Processing
    ↓
First Tier Config
    ↓
Second Tier Config
```

**Important**: Configurations must be consistent across all tiers for proper pipeline operation.

---

## First Tier Configuration

### Configuration File: `src/firstTierConfig.json`

### Global Parameters

| Parameter | Type | Default | Description | Impact |
|-----------|------|---------|-------------|---------|
| `PREDICTION_WINDOW_HOURS` | int | 168 | Forecast horizon in hours | Determines how far ahead to predict |
| `MAX_PREDICTION_WINDOW_HOURS` | int | 168 | Maximum allowed forecast window | Caps the prediction range |
| `TRAINING_WINDOW_HOURS` | int | 24 | Historical input window | Amount of past data used for each prediction |
| `EPOCHS` | list | [100] | Training iterations | Affects model convergence |
| `BATCH_SIZE` | list | [32] | Samples per gradient update | Memory usage and training speed |
| `LEARNING_RATE` | list | [0.001] | Optimizer step size | Convergence speed vs stability |
| `DROPOUT_RATE` | list | [0.2] | Regularization strength | Prevents overfitting |
| `CONV_FILTERS` | list | [[32, 64]] | CNN filter configurations | Feature extraction complexity |
| `CONV_KERNEL_SIZE` | list | [[3, 3]] | Convolution window sizes | Local pattern detection |
| `LSTM_UNITS` | list | [[100, 50]] | LSTM layer sizes | Temporal modeling capacity |
| `DENSE_UNITS` | list | [[50]] | Fully connected layer sizes | Final transformation complexity |

### Region-Specific Parameters

Each region (e.g., "AECI", "TVA") can have custom settings:

```json
"AECI": {
    "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2023.csv",
    "SOURCE_PROD_IN_FILE_NAME": "data/AECI/fuel_forecast/AECI_source_prod_clean.csv",
    "FORECAST_OUT_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA.csv",
    "NUM_FORECAST_FEATURES": 8,
    "NUM_WEATHER_FEATURES": 5,
    "REGION": "AECI",
    "SOURCES": ["coal", "nat_gas", "wind"]
}
```

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| `WEATHER_FORECAST_IN_FILE_NAME` | Path to processed weather data | `"extn/AECI_weather_forecast_2023.csv"` |
| `SOURCE_PROD_IN_FILE_NAME` | Historical generation data path | `"data/AECI/fuel_forecast/AECI_source_prod_clean.csv"` |
| `FORECAST_OUT_FILE_NAME` | Output path for combined forecasts | `"data/AECI/AECI_168hr_forecasts_DA.csv"` |
| `NUM_FORECAST_FEATURES` | Total features (weather + sources) | 8 |
| `NUM_WEATHER_FEATURES` | Number of weather variables | 5 |
| `SOURCES` | List of fuel sources to forecast | `["coal", "nat_gas", "wind"]` |

### Example First Tier Configuration

```json
{
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [150],
    "BATCH_SIZE": [32],
    "LEARNING_RATE": [0.001],
    "DROPOUT_RATE": [0.2],
    "CONV_FILTERS": [[32, 64]],
    "CONV_KERNEL_SIZE": [[3, 3]],
    "LSTM_UNITS": [[100, 50]],
    "DENSE_UNITS": [[50]],
    "LOSS": ["mae"],
    "OPTIMIZER": ["adam"],
    "AECI": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2023.csv",
        "SOURCE_PROD_IN_FILE_NAME": "data/AECI/fuel_forecast/AECI_source_prod_clean.csv",
        "FORECAST_OUT_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA.csv",
        "NUM_FORECAST_FEATURES": 8,
        "NUM_WEATHER_FEATURES": 5,
        "REGION": "AECI",
        "SOURCES": ["coal", "nat_gas", "wind"]
    }
}
```

---

## Second Tier Configuration

### Configuration File: `src/secondTierConfig.json`

### Global Parameters

| Parameter | Type | Default | Description | Impact |
|-----------|------|---------|-------------|---------|
| `TRAINING_WINDOW_HOURS` | int | 168 | Input sequence length | Must match first tier output |
| `PREDICTION_WINDOW_HOURS` | int | 168 | Forecast horizon | Must match first tier |
| `MAX_PREDICTION_WINDOW_HOURS` | int | 168 | Maximum prediction window | Consistency check |
| `NUM_TEST_DAYS` | int | 30 | Days reserved for testing | Max = Total_Days - 17 |
| `NUM_VAL_DAYS` | int | 20 | Days for validation | Minimum 4 days required |
| `EPOCHS` | list | [150] | Training iterations | Model convergence |
| `BATCH_SIZE` | list | [32] | Samples per update | Memory and speed |
| `LEARNING_RATE` | list | [0.001] | Learning step size | Training dynamics |
| `WRITE_CI_FORECASTS_TO_FILE` | string | "True" | Save predictions to disk | Output control |
| `CI_TYPE` | string | "both" | CI calculation type | "direct", "lifecycle", or "both" |

### Model Architecture Parameters

| Parameter | Type | Description | Typical Values |
|-----------|------|-------------|----------------|
| `CNN_FILTERS` | list | CNN layer filter counts | `[[32, 64]]` |
| `CNN_KERNEL_SIZE` | list | Convolution window sizes | `[[3, 3]]` |
| `CNN_POOL_SIZE` | list | Pooling window sizes | `[[2, 2]]` |
| `LSTM_UNITS` | list | LSTM layer dimensions | `[[100, 50]]` |
| `DENSE_UNITS` | list | Dense layer sizes | `[[50, 25]]` |
| `DROPOUT_RATE` | list | Dropout probability | `[0.2]` |

### Region-Specific Parameters

```json
"AECI": {
    "FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA.csv",
    "DIRECT_CI_IN_FILE_NAME": "data/AECI/AECI_direct_emissions.csv",
    "LIFECYCLE_CI_IN_FILE_NAME": "data/AECI/AECI_lifecycle_emissions.csv",
    "DIRECT_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts",
    "LIFECYCLE_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_lifecycle_168hr_CI_forecasts",
    "NUM_FORECAST_FEATURES": 8,
    "REGION": "AECI"
}
```

### Example Second Tier Configuration

```json
{
    "TRAINING_WINDOW_HOURS": 168,
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "NUM_TEST_DAYS": 30,
    "NUM_VAL_DAYS": 20,
    "EPOCHS": [150],
    "BATCH_SIZE": [32],
    "LEARNING_RATE": [0.001],
    "DROPOUT_RATE": [0.2],
    "CNN_FILTERS": [[32, 64]],
    "CNN_KERNEL_SIZE": [[3, 3]],
    "CNN_POOL_SIZE": [[2, 2]],
    "LSTM_UNITS": [[100, 50]],
    "DENSE_UNITS": [[50, 25]],
    "LOSS": ["mae"],
    "OPTIMIZER": ["adam"],
    "WRITE_CI_FORECASTS_TO_FILE": "True",
    "CI_TYPE": "both",
    "AECI": {
        "FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA.csv",
        "DIRECT_CI_IN_FILE_NAME": "data/AECI/AECI_direct_emissions.csv",
        "LIFECYCLE_CI_IN_FILE_NAME": "data/AECI/AECI_lifecycle_emissions.csv",
        "DIRECT_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts",
        "LIFECYCLE_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_lifecycle_168hr_CI_forecasts",
        "NUM_FORECAST_FEATURES": 8,
        "REGION": "AECI"
    }
}
```

---

## Weather Processing Configuration

### Configuration File: `src/weather/cleanWeatherData.py`

The weather processing configuration is hardcoded in the Python file. Key parameter:

```python
PREDICTION_PERIOD_DAYS = 7  # For 168-hour forecasts
# Change to 4 for 96-hour forecasts
```

### Impact of PREDICTION_PERIOD_DAYS

- **7 days**: Processes weather data for 168-hour forecasts
- **4 days**: Processes weather data for 96-hour forecasts
- Must match `PREDICTION_WINDOW_HOURS` in tier configs

---

## Configuring for Different Prediction Windows

### Overview

CarbonCast supports flexible prediction windows from 24 to 168 hours. Each window requires specific configuration adjustments across all pipeline components.

### Generalized Buffer Formula

The buffer days prevent data leakage between training and test sets:

```python
Buffer_Days = (PREDICTION_WINDOW_HOURS - MODEL_SLIDING_WINDOW_LEN) / 24

# For standard 24-hour sliding window:
Buffer_Days = (PREDICTION_WINDOW_HOURS - 24) / 24
```

### Minimum Training Days by Prediction Window

| Prediction Window | Buffer Days | Min Training Days | Recommended Training |
|-------------------|-------------|-------------------|---------------------|
| 24 hours (1 day)  | 0 | 7 days | 14-21 days |
| 48 hours (2 days) | 1 | 8 days | 16-24 days |
| 72 hours (3 days) | 2 | 10 days | 20-30 days |
| 96 hours (4 days) | 3 | 11 days | 22-33 days |
| 120 hours (5 days) | 4 | 12 days | 24-36 days |
| 144 hours (6 days) | 5 | 12 days | 24-36 days |
| 168 hours (7 days) | 6 | 13 days | 26-39 days |

### Generalized Configuration Formula

For any prediction window, calculate the maximum test days using:

```python
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - Buffer_Days

# Alternatively, with buffer incorporated:
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - (PREDICTION_WINDOW_HOURS/24 - 1)
```

### Configuration Examples by Prediction Window

#### 24-Hour (1 Day) Configuration

**Use Case**: Day-ahead energy markets, short-term operational planning

**Weather Processing (`src/weather/cleanWeatherData.py`):**
```python
PREDICTION_PERIOD_DAYS = 1
```

**First Tier (`src/firstTierConfig.json`):**
```json
{
    "PREDICTION_WINDOW_HOURS": 24,
    "MAX_PREDICTION_WINDOW_HOURS": 24,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [80]  // Fewer epochs needed for shorter horizon
}
```

**Second Tier (`src/secondTierConfig.json`):**
```json
{
    "TRAINING_WINDOW_HOURS": 24,
    "PREDICTION_WINDOW_HOURS": 24,
    "MAX_PREDICTION_WINDOW_HOURS": 24,
    "NUM_TEST_DAYS": 89,  // For 100 days: 100 - 7 - 4 - 0 = 89
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [100]
}
```

#### 48-Hour (2 Day) Configuration

**Use Case**: Two-day ahead planning, weekend forecasting

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 2
```

**First Tier:**
```json
{
    "PREDICTION_WINDOW_HOURS": 48,
    "MAX_PREDICTION_WINDOW_HOURS": 48,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [100]
}
```

**Second Tier:**
```json
{
    "TRAINING_WINDOW_HOURS": 48,
    "PREDICTION_WINDOW_HOURS": 48,
    "MAX_PREDICTION_WINDOW_HOURS": 48,
    "NUM_TEST_DAYS": 87,  // For 100 days: 100 - 8 - 4 - 1 = 87
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [120]
}
```

#### 72-Hour (3 Day) Configuration

**Use Case**: Mid-week planning, 3-day weather-dependent operations

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 3
```

**First Tier:**
```json
{
    "PREDICTION_WINDOW_HOURS": 72,
    "MAX_PREDICTION_WINDOW_HOURS": 72,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [120]
}
```

**Second Tier:**
```json
{
    "TRAINING_WINDOW_HOURS": 72,
    "PREDICTION_WINDOW_HOURS": 72,
    "MAX_PREDICTION_WINDOW_HOURS": 72,
    "NUM_TEST_DAYS": 84,  // For 100 days: 100 - 10 - 4 - 2 = 84
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [130]
}
```

#### 96-Hour (4 Day) Configuration

**Use Case**: Extended weekend planning, 4-day forecasts

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 4
```

**First Tier:**
```json
{
    "PREDICTION_WINDOW_HOURS": 96,
    "MAX_PREDICTION_WINDOW_HOURS": 96,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [130]
}
```

**Second Tier:**
```json
{
    "TRAINING_WINDOW_HOURS": 96,
    "PREDICTION_WINDOW_HOURS": 96,
    "MAX_PREDICTION_WINDOW_HOURS": 96,
    "NUM_TEST_DAYS": 82,  // For 100 days: 100 - 11 - 4 - 3 = 82
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [140]
}
```

#### 168-Hour (7 Day) Configuration

**Use Case**: Week-ahead planning, strategic scheduling

**Weather Processing:**
```python
PREDICTION_PERIOD_DAYS = 7
```

**First Tier:**
```json
{
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [150]
}
```

**Second Tier:**
```json
{
    "TRAINING_WINDOW_HOURS": 168,
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "NUM_TEST_DAYS": 170,  // For 187 days: 187 - 13 - 4 = 170
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [150]
}
```

### Quick Reference Table: Maximum Test Days by Data Size and Window

| Dataset Size | 24hr Max Test | 48hr Max Test | 72hr Max Test | 96hr Max Test | 168hr Max Test |
|--------------|---------------|---------------|---------------|---------------|----------------|
| 100 days | 89 | 87 | 84 | 82 | 76* |
| 187 days | 176 | 174 | 171 | 169 | 170 |
| 365 days | 354 | 352 | 349 | 347 | 348 |
| 730 days | 719 | 717 | 714 | 712 | 713 |

*Note: 100 days is below minimum for 168-hour predictions (need 187+ days)

### Performance Characteristics by Window

#### Short-term (24-48 hours)
- **Accuracy**: Highest (MAPE typically 5-8%)
- **Training Speed**: Fastest
- **Memory Usage**: Lowest
- **Min Data Required**: ~30 days
- **Characteristics**: Captures daily patterns, less weather-dependent

#### Medium-term (72-96 hours)
- **Accuracy**: Good (MAPE typically 8-12%)
- **Training Speed**: Moderate
- **Memory Usage**: Moderate
- **Min Data Required**: ~60 days
- **Characteristics**: Balances accuracy and horizon, captures weekly patterns

#### Long-term (120-168 hours)
- **Accuracy**: Moderate (MAPE typically 12-18%)
- **Training Speed**: Slowest
- **Memory Usage**: Highest
- **Min Data Required**: ~90 days
- **Characteristics**: Strategic planning focus, higher uncertainty

---

## Configuration Scenarios

### Scenario 1: 96-Hour Forecasting

For shorter 4-day forecasts with faster training:

**Weather Processing (`src/weather/cleanWeatherData.py`):**
```python
PREDICTION_PERIOD_DAYS = 4
```

**First Tier (`src/firstTierConfig.json`):**
```json
{
    "PREDICTION_WINDOW_HOURS": 96,
    "MAX_PREDICTION_WINDOW_HOURS": 96,
    "TRAINING_WINDOW_HOURS": 24
}
```

**Second Tier (`src/secondTierConfig.json`):**
```json
{
    "TRAINING_WINDOW_HOURS": 96,
    "PREDICTION_WINDOW_HOURS": 96,
    "MAX_PREDICTION_WINDOW_HOURS": 96
}
```

### Scenario 2: Limited Data Configuration (187 Days)

When you have the minimum viable dataset (187 days):

**First Tier:**
```json
{
    "EPOCHS": [200],  // More epochs for limited data
    "BATCH_SIZE": [16],  // Smaller batch size
    "DROPOUT_RATE": [0.3]  // Higher dropout to prevent overfitting
}
```

**Second Tier:**
```json
{
    "NUM_TEST_DAYS": 170,  // Maximum possible for 187 days
    "NUM_VAL_DAYS": 4,     // Minimum required to avoid errors
    "EPOCHS": [200],
    "BATCH_SIZE": [8]
}
```

**Important:** This is the validated maximum configuration for 187 days of data.

### Scenario 3: High-Performance Configuration

For systems with ample memory and compute resources:

**First Tier:**
```json
{
    "BATCH_SIZE": [64],  // Larger batch for faster training
    "CONV_FILTERS": [[64, 128]],  // More filters
    "LSTM_UNITS": [[200, 100]],  // Larger LSTM layers
    "DENSE_UNITS": [[100, 50]]  // Larger dense layers
}
```

**Second Tier:**
```json
{
    "BATCH_SIZE": [64],
    "CNN_FILTERS": [[64, 128]],
    "LSTM_UNITS": [[200, 100]],
    "DENSE_UNITS": [[100, 50]]
}
```

### Scenario 4: Quick Testing Configuration

For rapid prototyping and debugging:

**First Tier:**
```json
{
    "EPOCHS": [10],  // Minimal epochs
    "BATCH_SIZE": [128],  // Large batch for speed
    "SOURCES": ["wind"]  // Single source for speed
}
```

**Second Tier:**
```json
{
    "EPOCHS": [10],
    "NUM_TEST_DAYS": 5,
    "NUM_VAL_DAYS": 3,
    "WRITE_CI_FORECASTS_TO_FILE": "False"  // Skip file writing
}
```

### Scenario 5: Multiple Region Configuration

For processing multiple regions simultaneously:

**First Tier:**
```json
{
    "AECI": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2023.csv",
        "SOURCES": ["coal", "nat_gas", "wind"]
    },
    "TVA": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/TVA_weather_forecast_2023.csv",
        "SOURCES": ["coal", "nat_gas", "nuclear", "hydro"]
    },
    "CISO": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/CISO_weather_forecast_2023.csv",
        "SOURCES": ["nat_gas", "solar", "wind"]
    }
}
```

### Scenario 6: Maximum NUM_TEST_DAYS Configuration

For any dataset size, use this formula to calculate the maximum test days:

**Formula:**
```
NUM_TEST_DAYS_MAX = Total_Forecast_Days - 13 - NUM_VAL_DAYS
```

**Example Configurations:**

**187 Days Dataset (Minimum Viable):**
```json
{
    "NUM_TEST_DAYS": 170,  // Maximum: 187 - 13 - 4
    "NUM_VAL_DAYS": 4      // Minimum required
}
```

**365 Days Dataset:**
```json
{
    "NUM_TEST_DAYS": 348,  // Maximum: 365 - 13 - 4
    "NUM_VAL_DAYS": 4      // Or increase for better validation
}
```

**730 Days Dataset (2 Years):**
```json
{
    "NUM_TEST_DAYS": 693,  // Maximum: 730 - 13 - 24
    "NUM_VAL_DAYS": 24     // More validation for larger dataset
}
```

### Scenario 7: Full Year Forecasting (365 Days)

This scenario covers configuration for generating forecasts for an entire year (e.g., all of 2023).

#### Mathematical Breakdown of Data Requirements

To forecast 365 days continuously, you need to work backwards from your desired output:

```python
# Desired output
NUM_TEST_DAYS = 365  # Full year of forecasts

# Second tier requirements
MIN_TRAINING_DAYS = 13  # CNN-LSTM minimum
MIN_VAL_DAYS = 4        # Array dimension minimum

# Total days needed from first tier
Second_Tier_Requirements = NUM_TEST_DAYS + MIN_TRAINING_DAYS + MIN_VAL_DAYS
                         = 365 + 13 + 4
                         = 382 days

# First tier output (approximately 50% of input)
# The first tier loses about half the input days due to:
# - 24-hour input window at start
# - 168-hour forecast horizon at end
# - Sliding window mechanics

First_Tier_Input_Required = Second_Tier_Requirements × 2
                          = 382 × 2
                          = 764 days minimum

# Recommended: Add 10-20% buffer
Recommended_Input = 800-850 days
```

#### Formula for Input Data Requirements

For any desired forecast period, use this formula:

```
Input_Data_Days ≈ (Desired_Forecast_Days + 17) × 2
```

Where:
- 17 = MIN_TRAINING_DAYS (13) + MIN_VAL_DAYS (4)
- 2 = Approximate conversion factor (first tier outputs ~50% of input)

#### Example: 2023 Full Year Configuration

**Data Requirements:**
- **Input Period**: January 1, 2022 - December 31, 2023 (730 days)
- **Provides**: ~366 days from first tier
- **Supports**: Up to 349 days of test forecasts (366 - 13 - 4)

**Weather Processing ([`src/weather/cleanWeatherData.py`](src/weather/cleanWeatherData.py)):**
```python
PREDICTION_PERIOD_DAYS = 7  # For 168-hour forecasts
```

**First Tier Configuration ([`src/firstTierConfig.json`](src/firstTierConfig.json)):**
```json
{
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "TRAINING_WINDOW_HOURS": 24,
    "EPOCHS": [200],  // More epochs for larger dataset
    "BATCH_SIZE": [32],
    "LEARNING_RATE": [0.001],
    "DROPOUT_RATE": [0.2],
    "CONV_FILTERS": [[32, 64]],
    "CONV_KERNEL_SIZE": [[3, 3]],
    "LSTM_UNITS": [[100, 50]],
    "DENSE_UNITS": [[50]],
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

**Second Tier Configuration ([`src/secondTierConfig.json`](src/secondTierConfig.json)):**
```json
{
    "TRAINING_WINDOW_HOURS": 168,
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "NUM_TEST_DAYS": 349,  // Maximum for 730 days input
    "NUM_VAL_DAYS": 4,
    "EPOCHS": [200],
    "BATCH_SIZE": [32],
    "LEARNING_RATE": [0.001],
    "DROPOUT_RATE": [0.2],
    "CNN_FILTERS": [[32, 64]],
    "CNN_KERNEL_SIZE": [[3, 3]],
    "CNN_POOL_SIZE": [[2, 2]],
    "LSTM_UNITS": [[100, 50]],
    "DENSE_UNITS": [[50, 25]],
    "WRITE_CI_FORECASTS_TO_FILE": "True",
    "AECI": {
        "FORECAST_IN_FILE_NAME": "data/AECI/AECI_168hr_forecasts_DA_full_year.csv",
        "DIRECT_CI_IN_FILE_NAME": "data/AECI/AECI_direct_emissions_2022_2023.csv",
        "LIFECYCLE_CI_IN_FILE_NAME": "data/AECI/AECI_lifecycle_emissions_2022_2023.csv",
        "DIRECT_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_direct_168hr_CI_forecasts_2023",
        "LIFECYCLE_CI_OUT_FILE_NAME": "CI_forecast_data/AECI/AECI_lifecycle_168hr_CI_forecasts_2023",
        "NUM_FORECAST_FEATURES": 8
    }
}
```

**Note:** With 730 days of input, you get approximately 366 days from the first tier, which limits NUM_TEST_DAYS to 349 (366 - 13 - 4). To get a full 365 days of test forecasts, you would need approximately 800 days of input data.

#### Alternative Scenarios for Different Periods

**6 Months (183 Days) Configuration:**
```json
{
    "NUM_TEST_DAYS": 183,
    "NUM_VAL_DAYS": 4
    // Requires: 200 days from first tier
    // Input needed: ~400 days
}
```

**3 Months (91 Days) Configuration:**
```json
{
    "NUM_TEST_DAYS": 91,
    "NUM_VAL_DAYS": 4
    // Requires: 108 days from first tier
    // Input needed: ~216 days
}
```

**1 Month (30 Days) Configuration:**
```json
{
    "NUM_TEST_DAYS": 30,
    "NUM_VAL_DAYS": 4
    // Requires: 47 days from first tier
    // Input needed: ~94 days
}
```

#### Data Flow for Full Year Forecasting

```
Step 1: Historical Data Collection
└─ 730+ days (2+ years of data)
   └─ Weather data (GRIB2)
   └─ Generation data (source production)
   └─ Carbon intensity data

Step 2: First Tier Processing
└─ Input: 730 days
└─ Processing: 722 sliding windows
└─ Output: ~366 days of fuel forecasts

Step 3: Second Tier Split
└─ Available: 366 days
└─ Training: 13 days (minimum)
└─ Validation: 4 days (minimum)
└─ Test: 349 days (maximum)

Step 4: Final Output
└─ 349 × 168 = 58,632 hourly CI forecasts
└─ Coverage: Most of target year
```

#### Expected Outputs

With 2 years of input data (730 days):

1. **First Tier:**
   - Output file: `AECI_168hr_forecasts_DA_full_year.csv`
   - Rows: ~8,784 (366 days × 24 hours)
   - Columns: 8 features (5 weather + 3 fuel types)

2. **Second Tier:**
   - Output file: `AECI_direct_168hr_CI_forecasts_2023_0.csv`
   - Forecast windows: 349
   - Total predictions: 58,632 hourly values
   - Date coverage: ~95% of target year

#### Memory and Performance Considerations

For full year forecasting:

**Memory Requirements:**
```python
# Approximate memory usage
First_Tier_Memory = 366 days × 168 hours × 8 features × 4 bytes
                  ≈ 2 MB per source

Second_Tier_Memory = 366 days × 168 hours × 8 features × 4 bytes
                   ≈ 2 MB for input
                   + Model memory (varies by architecture)

Total_Memory ≈ 10-20 MB for data + 100-500 MB for models
```

**Performance Optimization:**
- Use batch processing for large datasets
- Consider gradient accumulation for memory-constrained systems
- Process in chunks if needed (e.g., quarterly)

**Training Time Estimates:**
- First Tier: 30-60 minutes per source (3-5 hours total)
- Second Tier: 45-90 minutes
- Total Pipeline: 4-7 hours on typical hardware

#### Verification Script

Use this script to verify your configuration can support full year forecasting:

```bash
#!/bin/bash
echo "=== Full Year Forecasting Verification ==="

# Check input data availability
echo "1. Checking input data..."
if [ -f "data/AECI/fuel_forecast/AECI_source_prod_clean.csv" ]; then
    LINES=$(wc -l < data/AECI/fuel_forecast/AECI_source_prod_clean.csv)
    DAYS=$((LINES / 24))
    echo "   Source data: $DAYS days available"
fi

# Calculate maximum forecast days
echo "2. Calculating maximum forecast capacity..."
if [ $DAYS -ge 730 ]; then
    FIRST_TIER_OUTPUT=$((DAYS / 2))
    MAX_TEST=$((FIRST_TIER_OUTPUT - 17))
    echo "   First tier output: ~$FIRST_TIER_OUTPUT days"
    echo "   Maximum NUM_TEST_DAYS: $MAX_TEST"
    
    if [ $MAX_TEST -ge 365 ]; then
        echo "   ✅ Can forecast full year (365 days)"
    else
        echo "   ⚠️  Can forecast $MAX_TEST days (need more input for full year)"
    fi
else
    echo "   ❌ Insufficient data (need 730+ days, have $DAYS)"
fi

echo "=== Verification Complete ==="
```

---

## Performance Tuning

### Memory Optimization

**Reduce memory usage when encountering OOM errors:**

```json
{
    "BATCH_SIZE": [8],  // Smaller batches
    "CNN_FILTERS": [[16, 32]],  // Fewer filters
    "LSTM_UNITS": [[50, 25]],  // Smaller LSTM
    "DENSE_UNITS": [[25]]  // Smaller dense layers
}
```

### Speed Optimization

**Faster training with acceptable accuracy trade-off:**

```json
{
    "EPOCHS": [50],  // Fewer epochs
    "BATCH_SIZE": [128],  // Larger batches
    "LEARNING_RATE": [0.01],  // Higher learning rate
    "DROPOUT_RATE": [0.1]  // Less dropout
}
```

### Accuracy Optimization

**Maximum accuracy (slower training):**

```json
{
    "EPOCHS": [300],  // More epochs
    "BATCH_SIZE": [16],  // Smaller batches
    "LEARNING_RATE": [0.0001],  // Lower learning rate
    "DROPOUT_RATE": [0.3],  // More regularization
    "CNN_FILTERS": [[64, 128, 256]],  // Deeper network
    "LSTM_UNITS": [[200, 100, 50]]  // More LSTM layers
}
```

---

## Troubleshooting Configuration Issues

### Issue: "Feature dimension mismatch"

**Symptom:**
```
ValueError: Expected 8 features, got 5
```

**Solution:**
Ensure `NUM_FORECAST_FEATURES` matches actual feature count:
```json
"NUM_FORECAST_FEATURES": 8,  // 5 weather + 3 sources
"NUM_WEATHER_FEATURES": 5,
"SOURCES": ["coal", "nat_gas", "wind"]  // 3 sources
```

### Issue: "Window size mismatch"

**Symptom:**
```
ValueError: PREDICTION_WINDOW_HOURS mismatch between tiers
```

**Solution:**
Synchronize window parameters across all configs:
- Weather: `PREDICTION_PERIOD_DAYS = 7`
- First Tier: `"PREDICTION_WINDOW_HOURS": 168`
- Second Tier: `"TRAINING_WINDOW_HOURS": 168`

### Issue: "Insufficient data for splits"

**Symptom:**
```
ValueError: Not enough data for train/val/test split
Index 0 is out of bounds for axis 0 with size 0
```

**Solution:**
Use the maximum NUM_TEST_DAYS formula:
```python
# Calculate maximum possible test days
NUM_TEST_DAYS_MAX = Total_Days - 13 - NUM_VAL_DAYS

# Example for 187 days:
NUM_TEST_DAYS_MAX = 187 - 13 - 4 = 170
```

Configuration:
```json
{
    "NUM_TEST_DAYS": 170,  // Maximum for 187 days
    "NUM_VAL_DAYS": 4      // Minimum required (≥4)
}
```

### Issue: "Array dimension error in validation"

**Symptom:**
```
ValueError: cannot reshape array of size 0 into shape (newshape)
IndexError: index 0 is out of bounds for axis 0 with size 0
```

**Solution:**
Ensure NUM_VAL_DAYS is at least 4:
```json
{
    "NUM_VAL_DAYS": 4  // Minimum to avoid array errors
}
```

### Issue: "File not found"

**Symptom:**
```
FileNotFoundError: Weather forecast file not found
```

**Solution:**
Verify file paths are relative to project root:
```json
"WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2023.csv"
// Not: "/absolute/path/to/file.csv"
// Not: "~/relative/path/file.csv"
```

### Issue: "Model not converging"

**Symptom:**
Loss remains high or increases during training

**Solution:**
Adjust learning parameters:
```json
{
    "LEARNING_RATE": [0.0001],  // Lower learning rate
    "EPOCHS": [300],  // More epochs
    "BATCH_SIZE": [16],  // Smaller batches
    "OPTIMIZER": ["adam"]  // Try different optimizer
}
```

### Issue: "Training set too small"

**Symptom:**
```
Warning: Training set has fewer than 312 hours
Model performance may be poor
```

**Solution:**
Ensure at least 13 days for training:
```python
# Check training days available
training_days = Total_Days - NUM_TEST_DAYS - NUM_VAL_DAYS
if training_days < 13:
    print(f"Error: Only {training_days} training days available, need at least 13")
    # Reduce NUM_TEST_DAYS accordingly
```

---

## Configuration Best Practices

### 1. Version Control
Always backup configurations before changes:
```bash
cp src/firstTierConfig.json src/firstTierConfig.json.backup
cp src/secondTierConfig.json src/secondTierConfig.json.backup
```

### 2. Consistency Checks
Ensure parameter alignment:
```python
# All must be equal:
weather_days = 7
first_tier_hours = 168
second_tier_hours = 168
assert weather_days * 24 == first_tier_hours == second_tier_hours
```

### 3. Progressive Testing
Start with minimal configuration:
1. Test with 1 source, 10 epochs
2. Expand to all sources, 10 epochs
3. Increase to full epochs
4. Fine-tune parameters

### 4. Documentation
Document configuration changes:
```json
{
    "_comment": "Modified 2024-01-15: Reduced batch size for M1 Mac",
    "BATCH_SIZE": [8]
}
```

### 5. Region-Specific Tuning
Different regions may need different parameters:
- Solar-heavy regions: More weather features
- Nuclear-heavy regions: Less weather dependence
- Wind-heavy regions: Higher temporal resolution

### 6. Validated Configurations

**Tested and Confirmed Working:**
- 187 days dataset: NUM_TEST_DAYS=170, NUM_VAL_DAYS=4
- Minimum training days: 13 (312+ hours)
- Minimum validation days: 4 (array dimension requirement)

---

## Appendix: Parameter Impact Matrix

| Parameter | Training Time | Memory Usage | Model Accuracy | Overfitting Risk |
|-----------|--------------|--------------|----------------|------------------|
| ↑ EPOCHS | ↑↑ | - | ↑ | ↑ |
| ↑ BATCH_SIZE | ↓ | ↑↑ | ↓ | ↓ |
| ↑ LEARNING_RATE | ↓ | - | ± | ↑ |
| ↑ DROPOUT_RATE | ↑ | - | ± | ↓↓ |
| ↑ CNN_FILTERS | ↑ | ↑ | ↑ | ↑ |
| ↑ LSTM_UNITS | ↑↑ | ↑↑ | ↑ | ↑ |
| ↑ NUM_TEST_DAYS | ↓ | - | - | ↓ |

**Legend:**
- ↑ = Increases
- ↓ = Decreases
- ± = Variable effect
- \- = No significant effect

---

*Configuration Guide Version 2.0 - Last updated for 168-hour forecasting capability*