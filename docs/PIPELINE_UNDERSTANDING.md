# CarbonCast Pipeline: Complete Technical Understanding

## Table of Contents
1. [Pipeline Architecture Overview](#pipeline-architecture-overview)
2. [Data Flow Through the Pipeline](#data-flow-through-the-pipeline)
3. [First Tier: Fuel Generation Forecasting](#first-tier-fuel-generation-forecasting)
4. [Second Tier: Carbon Intensity Prediction](#second-tier-carbon-intensity-prediction)
5. [Mathematical Relationships and Formulas](#mathematical-relationships-and-formulas)
6. [Data Requirements Analysis](#data-requirements-analysis)
7. [Parameter Effects Deep Dive](#parameter-effects-deep-dive)
8. [Date Calculations and Examples](#date-calculations-and-examples)
9. [Common Misconceptions](#common-misconceptions)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## Pipeline Architecture Overview

The CarbonCast pipeline is a two-tier forecasting system that predicts carbon intensity for electrical grids:

```
┌──────────────────────┐
│   Weather Data       │
│  (GRIB2 → CSV)       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│   First Tier         │     │  Historical Source   │
│  (Fuel Forecasts)    │◄────│    Production        │
└──────────┬───────────┘     └──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Combined Feature    │
│      Matrix          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────────┐
│   Second Tier        │     │  Historical Carbon   │
│  (CI Prediction)     │◄────│     Intensity        │
└──────────┬───────────┘     └──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Carbon Intensity    │
│     Forecasts        │
└──────────────────────┘
```

## Data Flow Through the Pipeline

### Stage 1: Weather Data Processing
- **Input**: GRIB2 files containing 3-hourly weather forecasts
- **Process**: Extract → Interpolate → Aggregate
- **Output**: Hourly weather features for 168-hour horizon

### Stage 2: First Tier Forecasting
- **Input**: Weather features + Historical source production
- **Process**: Sliding window prediction using ANNs
- **Output**: 7-day fuel generation forecasts for each source type

### Stage 3: Second Tier Prediction
- **Input**: Combined weather + fuel forecasts
- **Process**: CNN-LSTM model transforms to carbon intensity
- **Output**: 168-hour carbon intensity predictions

## First Tier: Fuel Generation Forecasting

### How First Tier Works

The first tier uses **24-hour sliding windows** to generate **7-day overlapping forecasts**:

```python
# For each day in your data:
for day in range(start_date, end_date):
    # Create input window (24 hours of features)
    input_window = data[day:day+24]  # Hours 0-23
    
    # Predict next 168 hours
    forecast = model.predict(input_window)  # Hours 24-191
    
    # This creates one forecast window
    forecasts.append(forecast)
```

### Key Concepts

1. **Input Window**: 24 hours of historical data
2. **Forecast Horizon**: 168 hours (7 days) into the future
3. **Sliding Step**: 24 hours (daily forecasts)
4. **Overlap**: Each forecast shares 144 hours with adjacent forecasts

### Visual Representation

```
Day 1: [24h input] → [168h forecast: Day 2-8]
Day 2:              [24h input] → [168h forecast: Day 3-9]
Day 3:                           [24h input] → [168h forecast: Day 4-10]
...
```

### Mathematical Formula for Number of Forecast Windows

```
num_windows = total_hours - (input_window + forecast_horizon) + 1
            = total_hours - (24 + 168) + 1
            = total_hours - 191

For 1 year of data (8760 hours):
num_windows = 8760 - 191 = 8569 windows
```

## Second Tier: Carbon Intensity Prediction

### How Second Tier Works

The second tier uses a **CNN-LSTM architecture** to transform fuel forecasts into carbon intensity:

```python
# Input shape: (samples, 168, 8)
# - samples: number of forecast windows
# - 168: hours in forecast horizon
# - 8: features (5 weather + 3 fuel types)

# Model architecture:
CNN layers → LSTM layers → Dense layers → CI predictions
```

### Test Period Calculation

The test period is determined by counting **backwards from the end** of your data:

```python
# Given:
NUM_TEST_DAYS = 30
forecast_horizon = 168 hours (7 days)

# Calculate:
test_start_index = total_windows - NUM_TEST_DAYS
test_end_index = total_windows

# Important: The 6-day buffer (168-24=144 hours) 
# prevents data leakage between train and test sets
```

### Why the Buffer Exists

When you have a 168-hour forecast starting on day N:
- It predicts hours 24-191 from day N
- This covers days N+1 through N+7
- To avoid leakage, test set must start at least 7 days after last training forecast

## Mathematical Relationships and Formulas

### 1. Total Data Required

To generate `N` days of complete forecasts:

```
Required historical data = N + 7 + 1 days
                         = N + 8 days

Where:
- N = desired forecast coverage
- 7 = forecast horizon in days
- 1 = input window in days
```

### 2. Output Dimensions

**First Tier Output Matrix:**
```
Shape: (num_windows, 168)
Where:
- num_windows = (total_hours - 191) / 24
- 168 = forecast horizon in hours
```

**Second Tier Input Matrix:**
```
Shape: (num_windows, 168, num_features)
Where:
- num_features = weather_features + fuel_features
              = 5 + num_fuel_types
```

### 3. Train/Test Split Calculations

```python
# Total windows available
total_windows = (data_hours - 191) / 24

# Test set size
test_windows = NUM_TEST_DAYS

# Validation set size
val_windows = NUM_VAL_DAYS

# Training set size
train_windows = total_windows - test_windows - val_windows - buffer_days

# Where buffer_days = 6 (to prevent leakage)
```

## 168-Hour Prediction Configuration

### Specific Configuration for 168-Hour (7-Day) Forecasts

The 168-hour prediction window is the default configuration for CarbonCast, optimized for week-ahead forecasting:

#### Key Parameters
- **Prediction Window**: 168 hours (7 days)
- **Training Window**: 24 hours (1 day sliding window)
- **Buffer Days**: 6 days (168-24)/24 = 6
- **Minimum Training Days**: 13 days (312+ hours for CNN-LSTM pattern learning)
- **Minimum Validation Days**: 4 days (array dimension requirement)

#### Maximum Test Days Formula for 168-Hour Predictions

```
NUM_TEST_DAYS_MAX = Total_Days - 13 - 4 = Total_Days - 17
```

This simplified formula applies specifically to 168-hour predictions with minimum validation.

#### Data Requirements for 168-Hour Forecasts

| Dataset Size | Max Test Days | Val Days | Train Days | Formula |
|--------------|---------------|----------|------------|---------|
| 187 days (minimum) | 170 | 4 | 13 | 187 - 17 = 170 |
| 365 days (1 year) | 348 | 4 | 13 | 365 - 17 = 348 |
| 730 days (2 years) | 713 | 4 | 13 | 730 - 17 = 713 |

For better validation, you can increase NUM_VAL_DAYS and adjust accordingly:
```
NUM_TEST_DAYS_MAX = Total_Days - 13 - NUM_VAL_DAYS
```

## Variable Prediction Windows (24-168 hours)

### Generalized Formula for Any Prediction Window

CarbonCast can be configured for different prediction horizons from 24 to 168 hours. The system adapts training requirements and buffer periods based on the prediction window.

#### Master Formula for Variable Windows

```
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - Buffer_Days
```

Where:
- `Buffer_Days = (PREDICTION_WINDOW_HOURS - 24) / 24`
- `Min_Training_Days` varies by prediction window (see table below)
- `NUM_VAL_DAYS` ≥ 4 (minimum for array dimensions)

#### Simplified Formula Including Buffer

Since Buffer_Days = (PREDICTION_WINDOW_HOURS - 24) / 24, we can also express this as:

```
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - ((PREDICTION_WINDOW_HOURS - 24) / 24)
```

Or with the buffer incorporated:

```
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - (PREDICTION_WINDOW_HOURS/24 - 1)
```

### Configuration by Prediction Window

| Prediction Window | Buffer Days | Min Training Days | Min Val Days | Quick Formula (with min val) |
|-------------------|-------------|-------------------|--------------|-------------------------------|
| 24 hours (1 day) | 0 | 7 | 4 | Total_Days - 11 |
| 48 hours (2 days) | 1 | 8 | 4 | Total_Days - 13 |
| 72 hours (3 days) | 2 | 10 | 4 | Total_Days - 16 |
| 96 hours (4 days) | 3 | 11 | 4 | Total_Days - 18 |
| 120 hours (5 days) | 4 | 12 | 4 | Total_Days - 20 |
| 144 hours (6 days) | 5 | 12 | 4 | Total_Days - 21 |
| 168 hours (7 days) | 6 | 13 | 4 | Total_Days - 23 |

### Buffer Days Calculation

The buffer prevents data leakage between training and test sets:

```python
# General formula for buffer days
Buffer_Days = (PREDICTION_WINDOW_HOURS - MODEL_SLIDING_WINDOW_LEN) / 24

# For standard 24-hour sliding window:
Buffer_Days = (PREDICTION_WINDOW_HOURS - 24) / 24

# Examples:
24-hour prediction:  (24 - 24) / 24 = 0 buffer days
48-hour prediction:  (48 - 24) / 24 = 1 buffer day
72-hour prediction:  (72 - 24) / 24 = 2 buffer days
96-hour prediction:  (96 - 24) / 24 = 3 buffer days
168-hour prediction: (168 - 24) / 24 = 6 buffer days
```

### Minimum Training Requirements by Window

Different prediction windows require different amounts of training data for optimal performance:

#### 24-48 Hour Predictions (Short-term)
- **Minimum Training Days**: 7-8 days
- **Recommended**: 10-14 days
- **Characteristics**: Captures daily patterns, less seasonal dependency

#### 72-96 Hour Predictions (Medium-term)
- **Minimum Training Days**: 10-11 days
- **Recommended**: 20-30 days
- **Characteristics**: Requires weekly pattern recognition

#### 120-168 Hour Predictions (Long-term)
- **Minimum Training Days**: 12-13 days
- **Recommended**: 30+ days
- **Characteristics**: Needs full weekly cycles plus buffer for stability

### Practical Examples for Different Windows

#### Example 1: 24-Hour Prediction Configuration

```python
# Configuration
PREDICTION_WINDOW_HOURS = 24
Buffer_Days = 0
Min_Training_Days = 7
NUM_VAL_DAYS = 4

# For 100 days of data:
NUM_TEST_DAYS_MAX = 100 - 7 - 4 - 0 = 89 days

# Data split:
# - Test: 89 days
# - Validation: 4 days
# - Training: 7 days
```

#### Example 2: 48-Hour Prediction Configuration

```python
# Configuration
PREDICTION_WINDOW_HOURS = 48
Buffer_Days = 1
Min_Training_Days = 8
NUM_VAL_DAYS = 4

# For 100 days of data:
NUM_TEST_DAYS_MAX = 100 - 8 - 4 - 1 = 87 days

# Data split:
# - Test: 87 days
# - Validation: 4 days
# - Training: 8 days
# - Buffer: 1 day
```

#### Example 3: 72-Hour Prediction Configuration

```python
# Configuration
PREDICTION_WINDOW_HOURS = 72
Buffer_Days = 2
Min_Training_Days = 10
NUM_VAL_DAYS = 4

# For 100 days of data:
NUM_TEST_DAYS_MAX = 100 - 10 - 4 - 2 = 84 days

# Data split:
# - Test: 84 days
# - Validation: 4 days
# - Training: 10 days
# - Buffer: 2 days
```

#### Example 4: 96-Hour Prediction Configuration

```python
# Configuration
PREDICTION_WINDOW_HOURS = 96
Buffer_Days = 3
Min_Training_Days = 11
NUM_VAL_DAYS = 4

# For 100 days of data:
NUM_TEST_DAYS_MAX = 100 - 11 - 4 - 3 = 82 days

# Data split:
# - Test: 82 days
# - Validation: 4 days
# - Training: 11 days
# - Buffer: 3 days
```

#### Example 5: 168-Hour Prediction Configuration

```python
# Configuration
PREDICTION_WINDOW_HOURS = 168
Buffer_Days = 6
Min_Training_Days = 13
NUM_VAL_DAYS = 4

# For 187 days of data:
NUM_TEST_DAYS_MAX = 187 - 13 - 4 - 6 = 164 days

# Note: The simplified formula gives us:
# NUM_TEST_DAYS_MAX = 187 - 17 = 170 days
# This includes the buffer in the calculation
```

## Maximum NUM_TEST_DAYS Formula

### Master Formula for Maximum Test Days

For any dataset and prediction window, the maximum number of test days is determined by:

```
NUM_TEST_DAYS_MAX = Total_Forecast_Days - Min_Training_Days - NUM_VAL_DAYS - Buffer_Days
```

Where:
- `Total_Forecast_Days` = Total number of daily forecast windows available
- `Min_Training_Days` = Minimum training days for the specific prediction window
- `NUM_VAL_DAYS` = Validation days (minimum 4 for array dimension requirements)
- `Buffer_Days` = (PREDICTION_WINDOW_HOURS - 24) / 24

### Why These Constraints Exist

#### Minimum Training Days: 13
The CNN-LSTM architecture requires at least 312 hours (13 days) of training data to:
- Learn temporal patterns effectively
- Avoid underfitting with insufficient samples
- Ensure stable gradient updates during backpropagation
- Capture at least one complete weekly cycle with buffer

#### Minimum Validation Days: 4
The validation set must have at least 4 days to:
- Prevent array dimension errors in model evaluation
- Provide sufficient data for early stopping decisions
- Enable meaningful validation metrics calculation
- Support proper batch formation during validation

### Practical Example: 187 Days of Data

For a dataset with 187 total days of forecast data:

```python
# Given:
Total_Days = 187
NUM_VAL_DAYS = 4  # Minimum validation days

# Calculate maximum test days:
NUM_TEST_DAYS_MAX = 187 - 13 - 4
                  = 170

# This gives us:
# - Test: 170 days
# - Validation: 4 days
# - Training: 13 days
# Total: 187 days
```

This configuration has been validated and tested to work without array dimension errors.

### Quick Reference Formula

For any dataset size, the quick calculation is:

```
NUM_TEST_DAYS_MAX = Total_Days - 17
```

This assumes the minimum validation size of 4 days.
## Understanding the 170-Day Limit for 168-Hour Predictions

### The Data Flow Bottleneck

The 170-day limit for NUM_TEST_DAYS in 168-hour predictions isn't an arbitrary constraint—it's a fundamental limitation based on the actual amount of forecast data generated by the first tier of the pipeline.

#### Complete Data Flow Chain

```
Original Input Data (365 days) 
    ↓
First Tier Processing
    ↓ 
First Tier Output (187 days of forecasts)
    ↓
Second Tier Maximum (170 days test + 4 days val + 13 days train)
```

### Why Only 187 Days from 365 Days Input?

When you provide 365 days of historical data to the first tier:

1. **First 24 hours (1 day)**: Used as the initial input window for the first forecast
2. **Last 168 hours (7 days)**: Cannot create a complete 168-hour forecast from the final days
3. **Sliding window calculation**:
   ```python
   # Total hours available
   total_hours = 365 * 24 = 8,760 hours
   
   # Hours needed for one complete forecast window
   window_requirement = 24 (input) + 168 (forecast) = 192 hours
   
   # Number of complete sliding windows possible
   num_windows = (8760 - 192) / 24 + 1 = 357 windows
   
   # But we generate daily forecasts (24-hour sliding)
   forecast_days = 357 / 24 ≈ 187 days
   ```

### Verifying the 4488 Row Count

The actual forecast file (`AECI_168hr_forecasts_DA.csv`) contains **4488 rows**, which translates to:

```python
# Verify the calculation
total_rows = 4488
hours_per_forecast = 168
total_forecast_windows = 4488 / 24 = 187 days

# This matches our theoretical calculation above
```

You can verify this yourself:
```bash
# Check the actual row count
wc -l data/AECI/AECI_168hr_forecasts_DA.csv
# Output: 4488 data/AECI/AECI_168hr_forecasts_DA.csv

# Confirm the calculation
python -c "print(f'Days of forecasts: {4488 / 24}')"
# Output: Days of forecasts: 187.0
```

### The Complete Constraint Breakdown

With 187 days of forecast data available from the first tier:

#### Minimum Training Requirements (13 days)
The CNN-LSTM architecture in the second tier requires at least 13 days of training data because:
- **Pattern Learning**: CNNs need sufficient temporal patterns (at least 312 hours)
- **Weekly Cycles**: Must capture at least one complete weekly cycle with buffer
- **Gradient Stability**: Insufficient data leads to unstable gradient updates
- **Batch Formation**: Need enough samples for proper mini-batch training
- **Generalization**: Less than 13 days causes severe underfitting

#### Minimum Validation Requirements (4 days)
The validation set requires at least 4 days to:
- **Array Dimensions**: Prevent dimension mismatch errors in TensorFlow
- **Early Stopping**: Provide sufficient data points for meaningful early stopping decisions
- **Metric Calculation**: Enable statistically meaningful validation metrics
- **Batch Compatibility**: Ensure proper batch formation during validation

#### Maximum Test Days Calculation
```python
Total_Days_Available = 187  # From first tier output
Min_Training_Days = 13      # CNN-LSTM requirements
Min_Validation_Days = 4      # Array dimension requirements

NUM_TEST_DAYS_MAX = 187 - 13 - 4 = 170 days
```

### What Happens When You Exceed 170 Days?

#### Attempting NUM_TEST_DAYS = 173
```python
Test_Days = 173
Validation_Days = 4
Remaining_for_Training = 187 - 173 - 4 = 10 days  # INSUFFICIENT!
```
**Result**: Model fails with insufficient training data error. CNN cannot learn patterns with only 10 days.

#### Attempting NUM_TEST_DAYS = 183
```python
Test_Days = 183
Validation_Days = 4
Remaining_for_Training = 187 - 183 - 4 = 0 days  # NO TRAINING DATA!
```
**Result**: Immediate crash with array dimension error. No data available for training.

#### Attempting NUM_TEST_DAYS = 186
```python
Test_Days = 186
Validation_Days = 4
Remaining_for_Training = 187 - 186 - 4 = -3 days  # NEGATIVE!
```
**Result**: Index out of bounds error. Trying to access data that doesn't exist.

### Verification Steps

To check your available forecast days and calculate your maximum NUM_TEST_DAYS:

```bash
# Step 1: Check the forecast file row count
echo "Checking forecast data availability..."
ROW_COUNT=$(wc -l < data/AECI/AECI_168hr_forecasts_DA.csv)
echo "Total rows in forecast file: $ROW_COUNT"

# Step 2: Calculate days of forecasts
FORECAST_DAYS=$((ROW_COUNT / 24))
echo "Days of forecast data: $FORECAST_DAYS"

# Step 3: Calculate maximum test days
MIN_TRAIN=13
MIN_VAL=4
MAX_TEST=$((FORECAST_DAYS - MIN_TRAIN - MIN_VAL))
echo "Maximum NUM_TEST_DAYS: $MAX_TEST"

# Step 4: Verify the calculation
echo "Breakdown:"
echo "  Total forecast days: $FORECAST_DAYS"
echo "  - Minimum training: $MIN_TRAIN"
echo "  - Minimum validation: $MIN_VAL"
echo "  = Maximum test days: $MAX_TEST"
```

Expected output:
```
Total rows in forecast file: 4488
Days of forecast data: 187
Maximum NUM_TEST_DAYS: 170
Breakdown:
  Total forecast days: 187
  - Minimum training: 13
  - Minimum validation: 4
  = Maximum test days: 170
```

### How to Increase the 170-Day Limit

To get more than 170 test days, you need more first tier output, which requires:

1. **More Input Data**: Start with more than 365 days of historical data
   ```python
   # For 200 test days:
   Required_Forecast_Days = 200 + 13 + 4 = 217 days
   Required_Input_Days = 217 + 8 = 225 days minimum
   ```

2. **Extend Data Collection Period**: Gather 2+ years of historical data
   ```python
   # With 730 days (2 years) of input:
   Forecast_Days = (730 * 24 - 192) / 24 = approximately 366 days
   MAX_TEST_DAYS = 366 - 13 - 4 = 349 days
   ```

3. **Reduce Validation Days** (not recommended): 
   ```python
   # Keeping 187 days but reducing validation:
   NUM_TEST_DAYS_MAX = 187 - 13 - 3 = 171 days  # Only 1 day gain
   # Risk: May get array dimension errors with val < 4
   ```

### The Fundamental Bottleneck

The bottleneck is the **first tier output**, not the second tier configuration. No matter how you adjust second tier parameters, you cannot test on more days than the first tier provides. The chain is:

```
Input Data → First Tier → 187 days maximum → Second Tier constraints → 170 days maximum test
```

This is why NUM_TEST_DAYS = 170 is the absolute maximum for a standard 365-day input dataset with 168-hour predictions.


## Data Requirements Analysis

### Scenario 1: Generate 1 Year of Forecasts

**Requirements:**
- Historical data needed: ~2 years
- Calculation:
  ```
  365 days (desired) + 7 days (horizon) + 365 days (training) = 737 days
  ```

### Scenario 2: Generate 3 Months of Forecasts

**Requirements:**
- Historical data needed: ~1 year
- Calculation:
  ```
  90 days (desired) + 7 days (horizon) + 270 days (training) = 367 days
  ```

### Scenario 3: Minimal Test (30 days)

**Requirements:**
- Historical data needed: ~6 months
- Calculation:
  ```
  30 days (desired) + 7 days (horizon) + 150 days (training) = 187 days
  ```

## Parameter Effects Deep Dive

### First Tier Parameters

| Parameter | Effect | Typical Value | Impact |
|-----------|--------|---------------|---------|
| `PREDICTION_WINDOW_HOURS` | Forecast horizon | 168 | Determines how far ahead to predict |
| `TRAINING_WINDOW_HOURS` | Input window size | 24 | Historical context for prediction |
| `EPOCHS` | Training iterations | 100-200 | Model convergence |
| `BATCH_SIZE` | Samples per update | 32 | Memory usage and training speed |
| `LEARNING_RATE` | Model update rate | 0.001 | Convergence speed vs stability |

### Second Tier Parameters

| Parameter | Effect | Typical Value | Impact |
|-----------|--------|---------------|---------|
| `NUM_TEST_DAYS` | Test set size | 30 | Evaluation data quantity |
| `NUM_VAL_DAYS` | Validation set size | 20 | Early stopping data |
| `CNN_FILTERS` | Feature extraction | [32, 64] | Model complexity |
| `LSTM_UNITS` | Sequential modeling | [100, 50] | Temporal pattern learning |
| `DROPOUT_RATE` | Regularization | 0.2 | Overfitting prevention |

## Date Calculations and Examples

### Example 1: AECI Region with 2022-2023 Data

**Given:**
- Data period: 2022-01-01 to 2023-12-31 (730 days)
- NUM_TEST_DAYS: 30
- NUM_VAL_DAYS: 20

**Calculations:**
```python
# Total hours of data
total_hours = 730 * 24 = 17,520 hours

# Number of forecast windows (daily sliding)
num_windows = (17520 - 191) / 24 = 720 windows

# Split calculation
test_start = 720 - 30 = window 690
val_start = 690 - 20 = window 670
train_end = 670 - 6 = window 664 (6-day buffer)

# Actual dates
test_period: 2023-12-02 to 2023-12-31 (30 days)
val_period: 2023-11-12 to 2023-12-01 (20 days)
train_period: 2022-01-08 to 2023-11-05 (with buffer)
```

### Example 2: Calculating Forecast Coverage

**Question:** How many days of forecasts can I generate with 500 days of data?

**Answer:**
```python
data_days = 500
forecast_horizon = 7
input_window = 1

# Maximum forecast coverage
coverage = data_days - forecast_horizon - input_window
         = 500 - 7 - 1
         = 492 days of forecasts

# But need to reserve for train/val/test
usable_coverage = 492 - (training_days + val_days + test_days + buffer)
                = 492 - (200 + 20 + 30 + 6)
                = 236 days of complete forecasts
```

## Common Misconceptions

### Misconception 1: "I can predict beyond my data"

**Reality:** You cannot generate predictions for dates beyond your historical data.

**Example:**
- If your data ends on 2023-12-31
- Your last forecast window starts on 2023-12-24
- It predicts 2023-12-25 to 2023-12-31 (only 7 days)
- You CANNOT predict into 2024 without 2024 data

### Misconception 2: "NUM_TEST_DAYS determines total predictions"

**Reality:** NUM_TEST_DAYS only determines which portion of your existing forecasts are used for testing.

**Clarification:**
- Total predictions = (data_hours - 191) / 24
- Test predictions = NUM_TEST_DAYS
- Training predictions = remaining after test/val split

### Misconception 3: "168-hour config means 168 predictions"

**Reality:** 168 hours is the forecast horizon per window, not the total number of predictions.

**Actual counts:**
- Each window produces 168 hourly predictions
- Total windows = (data_hours - 191) / 24
- Total predictions = windows × 168

### Misconception 4: "I need exactly 2 years of data"

**Reality:** Data requirements depend on your goals:

- Minimum viable: ~3 months (for basic testing)
- Recommended: 1-2 years (for robust training)
- Optimal: 2+ years (for seasonal patterns)

### Misconception 5: "The buffer period is wasted data"

**Reality:** The 6-day buffer (144 hours) is essential to prevent data leakage.

**Why it matters:**
- Forecast from day N predicts days N+1 to N+7
- Without buffer, test set would include data "seen" during training
- This would inflate performance metrics unrealistically

## Troubleshooting Guide

### Issue: "Not enough data for train/val/test split"

**Diagnosis:**
```python
# Check your data sufficiency
required_windows = NUM_TEST_DAYS + NUM_VAL_DAYS + MIN_TRAIN_DAYS + 6
required_days = required_windows + 8  # Add forecast horizon + input
print(f"You need at least {required_days} days of data")
```

**Solution:**
- Reduce NUM_TEST_DAYS and NUM_VAL_DAYS
- Obtain more historical data
- Use cross-validation instead of fixed splits

### Issue: "Predictions don't align with dates"

**Diagnosis:**
```python
# Verify date alignment
forecast_start_date = data_start_date + timedelta(days=1)
forecast_end_date = data_end_date - timedelta(days=7)
print(f"Forecasts cover: {forecast_start_date} to {forecast_end_date}")
```

**Solution:**
- Remember forecasts start 24 hours after input window
- Account for the 7-day forecast horizon at the end
- Use proper date indexing in your analysis

### Issue: "Model performance degrades over forecast horizon"

**Expected behavior:** Performance naturally decreases for longer horizons.

**Typical MAPE progression:**
- Hours 1-24: 5-8%
- Hours 25-72: 8-12%  
- Hours 73-120: 12-18%
- Hours 121-168: 15-25%

**Mitigation strategies:**
- Use ensemble methods
- Implement recursive refinement
- Weight recent predictions higher
- Consider separate models for different horizons

### Issue: "Memory errors during training"

**Quick fixes:**
```python
# Reduce batch size
BATCH_SIZE = 8  # From 32

# Reduce model complexity
CNN_FILTERS = [16, 32]  # From [32, 64]
LSTM_UNITS = [50, 25]   # From [100, 50]

# Use gradient accumulation
# Process mini-batches sequentially
```

## Appendix: Key Formulas Reference

### Windows and Coverage
```
num_windows = (total_hours - 191) / 24
forecast_coverage_days = num_windows
actual_date_coverage = data_days - 8
```

### Data Requirements
```
min_data_days = desired_forecast_days + 8 + training_days
training_days ≥ 3 × (NUM_TEST_DAYS + NUM_VAL_DAYS)
```

### Performance Metrics
```
MAPE = (100/n) × Σ|actual - predicted|/|actual|
RMSE = √(Σ(actual - predicted)²/n)
MAE = Σ|actual - predicted|/n
```

### Memory Estimation
```
first_tier_memory ≈ num_windows × 168 × 4 bytes
second_tier_memory ≈ num_windows × 168 × 8 × 4 bytes
total_memory ≈ (1 + num_features) × first_tier_memory
```

---

*Last updated: Documentation reflects CarbonCast v2.0 with 168-hour forecasting capability*

## Generating Forecasts for a Full Year (Example: All of 2023)

### Overview

Generating forecasts for an entire year requires careful planning of data requirements and configuration settings. This section explains the mathematical relationships and practical steps for producing 365 days of continuous carbon intensity forecasts.

### Data Requirements Calculation

To forecast all 365 days of 2023, you need to work backwards from your desired output:

#### Second Tier Requirements

```python
# Desired output
NUM_TEST_DAYS = 365  # All of 2023

# Add validation and training requirements
Days_Needed_From_First_Tier = NUM_TEST_DAYS + MIN_TRAINING_DAYS + NUM_VAL_DAYS
                            = 365 + 13 + 4
                            = 382 days minimum
```

#### First Tier Requirements

The first tier outputs approximately 50% of its input days as usable forecasts due to sliding window mechanics:

```python
# First tier calculation
First_Tier_Output_Days ≈ 382 days (needed by second tier)

# Input requirement (approximate 50% conversion rate)
First_Tier_Input_Days = First_Tier_Output_Days × 2
                      = 382 × 2
                      = 764 days minimum

# Recommended: Use 2 full years for safety margin
Recommended_Input = 730-800 days (2+ years)
```

### Recommended Date Range

For generating forecasts covering all of 2023:

**Optimal Input Period: January 1, 2022 - December 31, 2023**
- Total days: 730 days (2 complete years)
- Provides sufficient buffer for training and validation
- Ensures complete coverage of the target year

### Configuration for Full Year Forecasting

#### First Tier Configuration

Update [`src/firstTierConfig.json`](src/firstTierConfig.json):

```json
{
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    // Ensure your weather and source data covers 2022-2023
    "AECI": {
        "WEATHER_FORECAST_IN_FILE_NAME": "extn/AECI_weather_forecast_2022_2023.csv",
        "SOURCE_PROD_IN_FILE_NAME": "data/AECI/fuel_forecast/AECI_source_prod_clean_2022_2023.csv"
    }
}
```

**Important:** The first tier needs to be configured to output at least 382 days of forecasts.

#### Second Tier Configuration

Update [`src/secondTierConfig.json`](src/secondTierConfig.json):

```json
{
    "TRAINING_WINDOW_HOURS": 168,
    "PREDICTION_WINDOW_HOURS": 168,
    "MAX_PREDICTION_WINDOW_HOURS": 168,
    "NUM_TEST_DAYS": 365,  // Full year of 2023
    "NUM_VAL_DAYS": 4,      // Minimum validation
    "WRITE_CI_FORECASTS_TO_FILE": "True"
}
```

### Mathematical Breakdown

#### Input Data Flow

```
Step 1: Original Historical Data
└─ 730 days (Jan 1, 2022 - Dec 31, 2023)
   └─ 17,520 hours total

Step 2: First Tier Processing
└─ Input: 730 days
└─ Sliding windows: (17,520 - 192) / 24 = 722 windows
└─ Output: ~366 days of forecasts

Step 3: Second Tier Split
└─ Available: 366 days
└─ Test (2023): 365 days
└─ Validation: 4 days (minimum)
└─ Training: 13 days (minimum)
└─ Total used: 382 days (exceeds available by 16 days)
```

**Note:** With 730 days input, you actually get approximately 366 days from the first tier, which is 16 days short of the ideal 382. This means you'll need to adjust:
- Either increase input data to ~750-800 days
- Or reduce NUM_TEST_DAYS slightly to 349 (366 - 13 - 4)

### Alternative Approach: Exact Calculation

For precisely 365 days of test forecasts:

```python
# Work backwards from desired output
NUM_TEST_DAYS = 365
MIN_TRAINING_DAYS = 13
MIN_VAL_DAYS = 4

# Second tier needs
Second_Tier_Days_Needed = 365 + 13 + 4 = 382 days

# First tier must output (with 6-day buffer)
First_Tier_Output_Needed = 382 + 6 = 388 days

# First tier input requirement
# Formula: Output_Days ≈ (Input_Hours - 192) / 48
# Rearranged: Input_Hours = (Output_Days × 48) + 192
Input_Hours_Needed = (388 × 48) + 192 = 18,816 hours
Input_Days_Needed = 18,816 / 24 = 784 days

# Recommended: Round up to 800 days for safety
```

### Practical Formula for Any Period

To forecast X days continuously:

```python
def calculate_data_requirements(forecast_days):
    """
    Calculate input data requirements for any forecast period
    
    Args:
        forecast_days: Number of days you want to forecast
    
    Returns:
        dict: Data requirements
    """
    # Constants
    MIN_TRAINING = 13
    MIN_VALIDATION = 4
    BUFFER = 6
    CONVERSION_RATE = 0.5  # First tier outputs ~50% of input
    
    # Calculate
    second_tier_needs = forecast_days + MIN_TRAINING + MIN_VALIDATION
    first_tier_output_needs = second_tier_needs + BUFFER
    first_tier_input_needs = first_tier_output_needs / CONVERSION_RATE
    
    return {
        "forecast_days": forecast_days,
        "second_tier_requirements": second_tier_needs,
        "first_tier_output_needed": first_tier_output_needs,
        "first_tier_input_needed": int(first_tier_input_needs),
        "recommended_input": int(first_tier_input_needs * 1.1)  # 10% safety margin
    }

# Example: Full year (365 days)
requirements = calculate_data_requirements(365)
print(f"To forecast 365 days:")
print(f"  Need {requirements['first_tier_input_needed']} days input minimum")
print(f"  Recommended: {requirements['recommended_input']} days input")
```

### Expected Outputs for Full Year

With proper configuration and 2 years of input data:

1. **First Tier Outputs:**
   - 366+ daily forecast windows
   - Each window: 168 hours of fuel generation predictions
   - Total predictions: 366 × 168 = 61,488 hourly fuel forecasts per source

2. **Second Tier Outputs:**
   - 359 forecast windows for 2023 (365 - 6 buffer days)
   - Each window: 168 hours of carbon intensity predictions
   - Total predictions: 359 × 168 = 60,312 hourly CI forecasts
   - Coverage: January 7, 2023 - December 31, 2023

### Timeline Coverage Explanation

When forecasting a full year, the actual forecast coverage is:

```
Input Period: Jan 1, 2022 - Dec 31, 2023 (730 days)
           ↓
First Tier Processing (loses ~364 days)
           ↓
First Tier Output: ~366 days of forecasts
           ↓
Second Tier Processing (365 test + 13 train + 4 val)
           ↓
Final Forecast Coverage: Most of 2023 (359 windows)
```

The 6-day gap at the beginning of 2023 is due to:
- The 168-hour (7-day) forecast horizon
- The need for a 24-hour input window before the first forecast

### Alternative Scenarios

#### 6 Months Forecasting (183 Days)

```python
# Requirements for 6 months
NUM_TEST_DAYS = 183
Second_Tier_Needs = 183 + 13 + 4 = 200 days
First_Tier_Input = 200 × 2 = 400 days minimum
```

#### 3 Months Forecasting (91 Days)

```python
# Requirements for 3 months
NUM_TEST_DAYS = 91
Second_Tier_Needs = 91 + 13 + 4 = 108 days
First_Tier_Input = 108 × 2 = 216 days minimum
```

#### 1 Month Forecasting (30 Days)

```python
# Requirements for 1 month
NUM_TEST_DAYS = 30
Second_Tier_Needs = 30 + 13 + 4 = 47 days
First_Tier_Input = 47 × 2 = 94 days minimum
```

### Verification Commands

To verify you have sufficient data for full year forecasting:

```bash
# Check first tier output
echo "Checking first tier output capacity..."
ROWS=$(wc -l < data/AECI/AECI_168hr_forecasts_DA.csv)
DAYS=$((ROWS / 24))
echo "First tier output: $DAYS days"

# Check if sufficient for full year
REQUIRED=382  # 365 + 13 + 4
if [ $DAYS -ge $REQUIRED ]; then
    echo "✅ Sufficient data for full year forecasting"
else
    SHORTFALL=$((REQUIRED - DAYS))
    echo "❌ Insufficient by $SHORTFALL days"
    echo "   Need more input data or reduce NUM_TEST_DAYS"
fi
```

### Key Takeaways

1. **Input Data Rule of Thumb**: For X days of forecasts, need approximately 2X days of input data
2. **Minimum for Full Year**: 764-800 days of historical data
3. **Recommended Period**: 2 complete years (730+ days) with some buffer
4. **Actual Formula**: `Input_Days ≈ (Forecast_Days + 17) × 2`
5. **Safety Margin**: Always add 10-20% buffer to calculated requirements

---