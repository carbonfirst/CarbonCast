# Configuration Guide for CarbonCast 168-Hour Forecasting

Simple configuration guide for setting up different regions in CarbonCast.

## 🔧 Quick Configuration for Any Region

### Step 1: Update First Tier Config ([`src/firstTierConfig.json`](../src/firstTierConfig.json))

```json
{
    "REGION": ["YOUR_REGION"],
    "YOUR_REGION": {
        "IN_FILE_NAME_PREFIX": "data/YOUR_REGION/fuel_forecast/YOUR_REGION_",
        "WEATHER_FORECAST_IN_FILE_NAME": "YOUR_REGION_output/YOUR_REGION_weather_forecast_2023.csv",
        "OUT_FILE_NAME_PREFIX": "data/YOUR_REGION/fuel_forecast/YOUR_REGION_ANN",
        "AGGREGATED_FORECAST_OUT_FILE_NAME": "data/YOUR_REGION/YOUR_REGION_168hr_forecasts_DA.csv"
    }
}
```

### Step 2: Update Second Tier Config ([`src/secondTierConfig.json`](../src/secondTierConfig.json))

```json
{
    "REGION_DIRECT": ["YOUR_REGION"],
    "YOUR_REGION": {
        "DIRECT_CEF_IN_FILE_NAME": "data/YOUR_REGION/YOUR_REGION_direct_emissions.csv",
        "FORECAST_IN_FILE_NAME": "data/YOUR_REGION/YOUR_REGION_168hr_forecasts_DA.csv",
        "DIRECT_CEF_OUT_FILE_NAME_PREFIX": "CI_forecast_data/YOUR_REGION/YOUR_REGION_direct_168hr_CI_forecasts",
        "NUM_FORECAST_FEATURES": 15
    }
}
```

## 🗂️ Required Data Files

**For each region, you need:**

```
data/YOUR_REGION/
├── fuel_forecast/
│   └── YOUR_REGION_source_prod_clean.csv        # Historical generation data
├── YOUR_REGION_direct_emissions.csv            # Direct carbon intensity data  
└── YOUR_REGION_lifecycle_emissions.csv         # Lifecycle carbon intensity data (optional)
```

## 🌍 Common Regions

### **US Regions**
- AECI, AZPS, CISO, DUK, ERCO, FPL, ISNE, MISO, NYIS, PJM, SOCO, TVA, etc.
- **Continent parameter**: `US`

### **EU Regions**  
- BE, DE, FR, NL, ES, PL, IT, AT, etc.
- **Continent parameter**: `EU`

## ⚙️ Key Settings

**168-Hour Configuration (already set):**
- `PREDICTION_WINDOW_HOURS`: 168
- `MAX_PREDICTION_WINDOW_HOURS`: 168
- `TRAINING_WINDOW_HOURS`: 24

**Weather Variable Indices:**
- 0: Wind Speed (ugrd_vgrd)
- 1: Temperature/Dewpoint (tmp_dpt)  
- 2: Solar Radiation (dswrf)
- 3: Precipitation (apcp)

## 🎯 Example: Belgium (BE) Setup

**Commands used:**
```bash
# Weather processing
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py EU 0 \
    --base tmp_files/combined/BE/ --out ./EU_2023_BE_output/ --regions BE

# Clean weather
micromamba run -n carboncast-310 python src/weather/cleanWeatherData.py EU EU_2023_BE_output/

# First tier
micromamba run -n carboncast-310 python src/firstTierForecasts.py src/firstTierConfig.json

# Second tier  
micromamba run -n carboncast-310 python scripts/run_6month_forecasting.py src/secondTierConfig.json -d
```

**Result**: `CI_forecast_data/BE/BE_direct_168hr_CI_forecasts_merged_2023.csv`

Simply replace "BE" with your region code and update the config files accordingly!