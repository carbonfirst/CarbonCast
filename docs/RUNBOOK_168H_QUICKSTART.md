# CarbonCast 168-Hour Forecasting - Simple Quickstart Guide

Complete 4-step guide to generate 7-day (168-hour) carbon intensity forecasts from GRIB2 weather data.

## 🚀 Why micromamba?

**micromamba is the recommended environment manager for macOS users** - it handles TensorFlow Metal GPU dependencies seamlessly and avoids common installation issues with conda/pip conflicts.

---

## 📋 Prerequisites & Input Files

**Required Input Files:**
- **GRIB2 weather data** (tar files) in `tmp_files/` directory
- **Source production data**: `data/{REGION}/fuel_forecast/{REGION}_source_prod_clean.csv`
- **Carbon intensity data**: `data/{REGION}/{REGION}_direct_emissions.csv` and `data/{REGION}/{REGION}_lifecycle_emissions.csv`

**Environment:**
- micromamba environment with Python 3.10 and TensorFlow Metal
- wgrib2 installed and accessible

---

## Step 1: Setup GRIB2 Data Organization

**Input:** Tar files in `tmp_files/` directory (e.g., `BE_apcp_20220701*.tar`)

**Commands:**
```bash
# Extract tar files
cd tmp_files && for tarfile in *.tar; do dirname="${tarfile%.tar}"; mkdir -p "$dirname"; tar -xf "$tarfile" -C "$dirname"; done

# Organize GRIB2 files with fixed symlink script
bash scripts/combine_grib2_symlinks.sh tmp_files
```

**Expected Output:**
```
BE/ugrd_vgrd -> 122628 files
BE/tmp_dpt -> 122628 files  
BE/dswrf -> 122624 files
BE/apcp -> 122625 files
Combined directories created under: tmp_files/combined
```

**Verification:**
```bash
ls tmp_files/combined/BE/
# Should show: apcp/ dswrf/ tmp_dpt/ ugrd_vgrd/
```

---

## Step 2: Process Weather Variables

**Input:** Organized GRIB2 files in `tmp_files/combined/{REGION}/`

**Commands - Run all 4 weather variables:**
```bash
# Wind Speed (Index 0)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py EU 0 \
    --base tmp_files/combined/BE/ \
    --out ./EU_2023_BE_output/ \
    --regions BE

# Temperature/Dewpoint (Index 1) 
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py EU 1 \
    --base tmp_files/combined/BE/ \
    --out ./EU_2023_BE_output/ \
    --regions BE

# Solar Radiation (Index 2)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py EU 2 \
    --base tmp_files/combined/BE/ \
    --out ./EU_2023_BE_output/ \
    --regions BE

# Precipitation (Index 3)
micromamba run -n carboncast-310 python src/weather/separateWeatherByRegion.py EU 3 \
    --base tmp_files/combined/BE/ \
    --out ./EU_2023_BE_output/ \
    --regions BE
```

**Expected Output Files:**
```
EU_2023_BE_output/BE_WIND_SPEED.csv   (2.4 MB)
EU_2023_BE_output/BE_TEMP.csv        (2.4 MB)
EU_2023_BE_output/BE_DPT.csv         (2.4 MB)
EU_2023_BE_output/BE_DSWRF.csv       (1.8 MB)
EU_2023_BE_output/BE_APCP.csv        (2.0 MB)
```

**Runtime:** ~30 minutes per variable (can run in parallel)

---

## Step 3: Clean Weather Data

**Input:** Raw weather CSV files from Step 2

**Command:**
```bash
micromamba run -n carboncast-310 python src/weather/cleanWeatherData.py EU EU_2023_BE_output/
```

**Expected Output Files:**
```
EU_2023_BE_output/BE_weather_forecast_2023.csv      (37.3 MB) ← Key output
EU_2023_BE_output/BE_aggregated_weather_data_2023.csv (37.3 MB)
```

**Runtime:** ~2 minutes

---

## Step 4: Configure & Run First Tier Forecasts

**Input:** 
- Weather forecasts from Step 3
- Historical source production data: `data/{REGION}/fuel_forecast/{REGION}_source_prod_clean.csv`

**Configuration:** Update [`src/firstTierConfig.json`](src/firstTierConfig.json):
```json
{
    "REGION": ["BE"],
    "BE": {
        "IN_FILE_NAME_PREFIX": "data/BE/fuel_forecast/BE_",
        "WEATHER_FORECAST_IN_FILE_NAME": "EU_2023_BE_output/BE_weather_forecast_2023.csv",
        "OUT_FILE_NAME_PREFIX": "data/BE/fuel_forecast/BE_ANN",
        "AGGREGATED_FORECAST_OUT_FILE_NAME": "data/BE/BE_168hr_forecasts_DA.csv"
    }
}
```

**Command:**
```bash
micromamba run -n carboncast-310 python src/firstTierForecasts.py src/firstTierConfig.json
```

**Expected Output:**
- **Per-source forecasts**: `data/BE/fuel_forecast/BE_ANN_{source}_iter0.csv` (9 files)
- **Combined forecast matrix**: `data/BE/BE_168hr_forecasts_DA.csv` (22.6 MB, 122,640 rows × 15 features)

**Runtime:** ~15-30 minutes

---

## Step 5: Configure & Run Second Tier Forecasts  

**Input:**
- Forecast matrix from Step 4: `data/{REGION}/{REGION}_168hr_forecasts_DA.csv`
- Carbon intensity data: `data/{REGION}/{REGION}_direct_emissions.csv`

**Configuration:** Update [`src/secondTierConfig.json`](src/secondTierConfig.json):
```json
{
    "REGION_DIRECT": ["BE"],
    "BE": {
        "DIRECT_CEF_IN_FILE_NAME": "data/BE/BE_direct_emissions.csv",
        "FORECAST_IN_FILE_NAME": "data/BE/BE_168hr_forecasts_DA.csv",
        "DIRECT_CEF_OUT_FILE_NAME_PREFIX": "CI_forecast_data/BE/BE_direct_168hr_CI_forecasts",
        "NUM_FORECAST_FEATURES": 15
    }
}
```

**Command:**
```bash
micromamba run -n carboncast-310 python scripts/run_6month_forecasting.py src/secondTierConfig.json -d
```

**Expected Output:**
```
CI_forecast_data/BE/BE_direct_168hr_CI_forecasts_H1_0.csv        (1.4 MB) - Jan-Jun 2023
CI_forecast_data/BE/BE_direct_168hr_CI_forecasts_H2_0.csv        (1.4 MB) - Jul-Dec 2023
CI_forecast_data/BE/BE_direct_168hr_CI_forecasts_merged_2023.csv (2.2 MB) - Complete 2023
```

**Final Result:** 60,480 forecast points with proper 168hr overlapping window structure covering complete 2023.

**Runtime:** ~20-40 minutes

---

## 🎯 For Other Regions

**To process different regions (AECI, TVA, CISO, etc.):**

1. **Replace "BE" with your region** in all commands and config files
2. **Ensure region data exists** in `data/{REGION}/` directory
3. **Run same 5-step pipeline** with region-specific paths

**Example for AECI:**
```bash
# Step 2: Replace BE with AECI
--base tmp_files/combined/AECI/ --regions AECI

# Step 4: Update firstTierConfig.json
"REGION": ["AECI"]

# Step 5: Update secondTierConfig.json  
"REGION_DIRECT": ["AECI"]
```

---

## 🔧 Key Configuration Notes

**Weather Variables Mapping:**
- Index 0: Wind Speed (ugrd_vgrd)
- Index 1: Temperature/Dewpoint (tmp_dpt)
- Index 2: Solar Radiation (dswrf)  
- Index 3: Precipitation (apcp)

**168hr vs 96hr Configuration:**
- All configs are pre-set for 168-hour forecasts
- Output files automatically named with `168hr` suffix
- Uses 7-day prediction windows

**Overlap Handling:**
- H1 and H2 models both predict June 29-30, 2023
- Merged file preserves ALL predictions (no automatic selection)
- Use H2 predictions for Jul-Dec 2023 analysis (more accurate for that period)

---

## ✅ Complete Pipeline Success Checklist

After running all steps, verify:

□ **Weather CSVs created** (Step 2): 5 files in output directory  
□ **Weather cleaned** (Step 3): `{REGION}_weather_forecast_2023.csv` exists
□ **Source models trained** (Step 4): 9 `BE_ANN_{source}_iter0.csv` files + combined matrix
□ **CI forecasts generated** (Step 5): Merged 2023 file with 60k+ forecast points

**Final output:** `CI_forecast_data/{REGION}/{REGION}_direct_168hr_CI_forecasts_merged_2023.csv`

This file contains hourly carbon intensity forecasts for the complete year with proper 168-hour overlapping window structure preserved for comprehensive analysis.
