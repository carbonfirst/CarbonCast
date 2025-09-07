# CarbonCast Pipeline Understanding

Simple explanation of how CarbonCast generates 168-hour carbon intensity forecasts.

## 🔄 Pipeline Overview

CarbonCast uses a **two-tier forecasting system**:

```
Weather Data (GRIB2) → First Tier → Second Tier → Carbon Intensity Forecasts
```

### **First Tier**: Fuel Generation Forecasting
- **Input**: Weather features + Historical source production
- **Output**: 7-day fuel generation forecasts for each energy source
- **Method**: 24-hour sliding windows to predict next 168 hours

### **Second Tier**: Carbon Intensity Prediction  
- **Input**: Weather features + Fuel forecasts (combined)
- **Output**: 168-hour carbon intensity predictions
- **Method**: CNN-LSTM model

## 📊 Data Requirements

### Simple Rule of Thumb
```
Input Data Needed ≈ (Desired Forecast Days + 17) × 2
```

**Examples:**
- **30 days of forecasts**: Need ~100 days of input data
- **365 days of forecasts**: Need ~750 days of input data

### Maximum Test Days Formula

**For 168-hour (7-day) forecasts:**
```
NUM_TEST_DAYS_MAX = Total_Days - 17
```

**For other prediction windows:**
```
NUM_TEST_DAYS_MAX = Total_Days - (prediction_days + 13)
```

**Validation check:**
```
Val days + Test days ≤ Total_Days - Min_Training_Days

Example for 96-hour forecasts:
Val + Test ≤ 365 - 4 + 1 = 362
```

## ⚙️ Key Parameters

### **First Tier Config**
- `PREDICTION_WINDOW_HOURS: 168` (7-day forecasts)
- `TRAINING_WINDOW_HOURS: 24` (24-hour input windows)

### **Second Tier Config**
- `NUM_TEST_DAYS`: Number of days to test on (max = Total_Days - 17)
- `NUM_VAL_DAYS: 4` (minimum for array dimensions)
- `NUM_FORECAST_FEATURES`: Weather features + Source features

## 🎯 Common Configurations

| Prediction Window | Max Test Days Formula | Example (200 days input) |
|-------------------|----------------------|--------------------------|
| 24 hours | Total - 11 | 200 - 11 = 189 |
| 96 hours | Total - 18 | 200 - 18 = 182 |
| 168 hours | Total - 17 | 200 - 17 = 183 |

## ⚠️ Key Constraints

1. **Minimum training**: 13 days (for CNN-LSTM pattern learning)
2. **Minimum validation**: 4 days (for array dimensions)  
3. **Buffer period**: 6 days (prevents data leakage in 168h forecasts)
4. **First tier loss**: ~50% of input data lost due to sliding windows

## 🔍 Quick Verification

Check if your configuration will work:

```bash
# Check your forecast file
ROWS=$(wc -l < data/{REGION}/{REGION}_168hr_forecasts_DA.csv)
DAYS=$((ROWS / 24))
MAX_TEST=$((DAYS - 17))

echo "Available forecast days: $DAYS"
echo "Maximum NUM_TEST_DAYS: $MAX_TEST"
```

If `NUM_TEST_DAYS > MAX_TEST`, reduce NUM_TEST_DAYS or get more input data.

## 📈 Performance Expectations

**Typical MAPE by forecast day:**
- Day 1: 8-15%
- Day 2-3: 15-25% 
- Day 4-5: 25-35%
- Day 6-7: 30-45%

Performance naturally decreases with longer prediction horizons.