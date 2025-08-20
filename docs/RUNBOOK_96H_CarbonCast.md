# CarbonCast 96-hour Forecasts — End-to-End Runbook

This guide explains how the repository generates 96-hour forecasts, the data formats required, and exact steps to run from scratch. It cites the codebase with file/function references and includes light samples of the large CSVs.


## Overview: Two-tier pipeline

- Tier-1: Source production forecasts per fuel (coal, nat_gas, solar, wind, etc.).
  - Code: `src/firstTierForecasts.py`
  - Config: `src/firstTierConfig.json`
  - Output: per-source day-ahead forecasts (stitched for 96h) under `data/<REGION>/fuel_forecast/*ANN_DA_*.csv` and consolidated inputs used later.
- Tier-2: 96-hour carbon intensity (CI) forecasts from historical CI + weather + source forecasts.
  - Code: `src/secondTierForecasts.py`
  - Config: `src/secondTierConfig.json`
  - Output: CI forecasts `.../CI_forecast_data/<REGION>/...` when enabled, or printed metrics.
- Optional: Compute CI directly from source production or forecasts via formula.
  - Code: `src/carbonIntensityCalculator.py`

Key shared utilities: `src/common.py` (train/val/test split, scaling, datetime features, metrics), `src/utility.py` (plotting, helpers).


## Data: Expected schemas (column names and types)

Below are representative headers and first rows (only sampled to avoid loading entire files). Adjust region names accordingly.

1) 96-hour forecast feature matrix (Tier-2 input)
- File: `data/CISO/CISO_96hr_forecasts_DA.csv`
- Header columns sampled (first line):
  - `UTC time`, `forecast_avg_wind_speed_wMean`, `forecast_avg_temperature_wMean`, `forecast_avg_dewpoint_wMean`, `forecast_avg_dswrf_wMean`, `forecast_avg_precipitation_wMean`, `avg_wind_production_forecast`, `avg_solar_production_forecast`, `avg_nat_gas_production_forecast`, `avg_coal_production_forecast`, `avg_nuclear_production_forecast`, `avg_hydro_production_forecast`, `avg_oil_production_forecast`, `avg_other_production_forecast`, `avg_demand_production_forecast`, `avg_wind_production_forecast` (note: duplicate last col in this file version)
- Sample row:
  - `2020-01-01 00:00:00,5.77,...,0.237...,2591.15,780.89,6769.66,9.40,2274.82,242.59,83.01,5.12,20071.00,2591.15`
- Used by: `secondTierForecasts.initialize()` reading `forecastDataset` then split via `common.splitWeatherDataset()`.

2) Historical carbon intensity and sources (Tier-2 input)
- File: `data/CISO/CISO_direct_emissions.csv` (or `..._lifecycle_emissions.csv`)
- Header: `UTC time, carbon_intensity, coal, nat_gas, nuclear, oil, hydro, solar, wind, other`
- Used by: `secondTierForecasts.initialize()` as `dataset` and trimmed by `START_COL` and `NUM_FEATURES` from config.

3) Weather-only hourly features (Tier-1 input when renewable sources used)
- File: `data/CISO/CISO_weather_forecast.csv`
- Header: `UTC time, forecast_avg_wind_speed_wMean, forecast_avg_temperature_wMean, forecast_avg_dewpoint_wMean, forecast_avg_dswrf_wMean, forecast_avg_precipitation_wMean`
- Used by: `firstTierForecasts.initialize()` to build `weatherDataset` for renewable sources.

4) Per-source training files (Tier-1 input)
- Example: `data/CISO/fuel_forecast/CISO_coal_2019_clean.csv`
- Header: `UTC time, Local time, carbon_intensity, coal, avg_coal_production_forecast`
- Used by: `firstTierForecasts.initialize()` along with `SOURCE_COL` and `NUM_FEATURES`.

Notes
- All time columns are parsed as `UTC time` in code using pandas with `parse_dates=['UTC time']` and often used as index.
- Datetime-derived features are added internally: `hour_sin`, `hour_cos`, `month_sin`, `month_cos`, `weekend` via `common.addDateTimeFeatures()`.


## Tier-1: Source production forecasts (how it works)

- Entrypoint: `src/firstTierForecasts.py: runFirstTier(configFile)`
  - Reads `src/firstTierConfig.json` for:
    - Global params: `TRAINING_WINDOW_HOURS`, `PREDICTION_WINDOW_HOURS` (typically 96), `MODEL_SLIDING_WINDOW_LEN` (24), `NUM_VAL_DAYS`, `NUMBER_OF_EXPERIMENTS_PER_REGION`.
    - Region blocks (e.g., `CISO`):
      - `IN_FILE_NAME_PREFIX` and `IN_FILE_NAME_SUFFIX` to compose per-source CSV paths like `.../CISO_<source>_2019_clean.csv`.
      - `WEATHER_FORECAST_IN_FILE_NAME` for renewable source features.
      - `SOURCES` and `SOURCE_COL` define which column offsets to include and target.
      - `NUM_FEATURES` and `NUM_WEATHER_FEATURES` control feature counts fed to model.
      - `PARTIAL_FORECAST_AVAILABILITY_LIST` allows using known 24h day-ahead values when available (e.g., solar/wind day-1).
  - For each period in `TRAIN_TEST_PERIOD`, `initialize()`:
    - Loads per-source dataset and weather dataset, adds datetime features (common.addDateTimeFeatures), truncates to `DATASET_LIMITER` hours for train window, and keeps a `BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24` tail for evaluation alignment.
  - Dataset split: `common.splitDataset()` into train/val/test by days; if renewable, `common.splitWeatherDataset()` with `PREDICTION_WINDOW_HOURS` stride.
  - Scaling: `common.scaleDataset()` (min-max based on train) for both history and weather.
  - Model: `trainANN()` builds a simple ANN (Flatten + Dense hidden layers + Dense output of size label window) and trains with early stopping and `ModelCheckpoint`.
  - Inference: `getDayAheadForecasts()` performs 96-hour forecasting in 24-hour blocks, rolling forward by injecting predicted values into history; if partial forecasts are available for first 24h, they override predictions.
  - Output writing: `writeSourceProductionForecastsToFile()` writes `datetime, <source>_actual, avg_<source>_production_forecast` rows.

Key functions to read:
- `initialize()`, `trainingandValidationPhase()`, `manipulateTrainingDataShape()`, `getDayAheadForecasts()`, `getForecasts()` in `src/firstTierForecasts.py`.
- Scaling and splits in `src/common.py`.


## Tier-2: 96-hour CI forecasts (how it works)

- Entrypoint: `src/secondTierForecasts.py: runSecondTier(configFile, cefType, loadFromSavedModel)`
  - Config: `src/secondTierConfig.json` with region list, windows, `NUM_FEATURES`, `NUM_FORECAST_FEATURES`, and file paths for `DIRECT_CEF_IN_FILE_NAME` or `LIFECYCLE_CEF_IN_FILE_NAME`, plus `FORECAST_IN_FILE_NAME` (combined weather + source forecasts for 96h).
  - Data init: `initialize()` reads CI time series as `dataset` and 96h forecast matrix as `forecastDataset`, then adds datetime features to the historical set via `addDateTimeFeatures()` (Tier-2 has its own copy of this function).
  - Splits: `common.splitDataset()` on `dataset` with buffer to align 96h windows; weather/forecast side via `common.splitWeatherDataset()` using `MAX_PREDICTION_WINDOW_HOURS`.
  - Scaling: Separate min-max for historical feature block and forecast block.
  - Model: `trainModel()` builds a CNN+LSTM sequence-to-vector model predicting 96 values; optionally loads saved `.h5` models if `-s` is provided.
  - Inference: `getDayAheadForecasts()` rolls forward 24h at a time until 96h, appending predicted target to history and replacing dependent var in the temp history with predictions.
  - Metrics: `getUnscaledForecastsAndForecastAccuracy()` unscales and computes RMSE/MAPE and daily MAPE via `getScores()`.

Key functions to read:
- `manipulateTrainingDataShape()`, `trainModel()`, `getDayAheadForecasts()`, `getUnscaledForecastsAndForecastAccuracy()` in `src/secondTierForecasts.py`.


## Weather collection and formatting

- Raw download (GFS ds084.1): `src/weather/getWeatherData.py` and `src/weather/ds084.1_control.ctl` (template). Requires NCAR RDA client and credentials. See README Section 5.1 and comments in the script.
- Aggregation from GRIB2 -> CSV: `src/weather/dataCollectionScript.py` wraps `wgrib2` to extract variables and computes area-weighted means over a region bounding box. Outputs intermediate CSVs with 3-hourly forecast columns: `3 hr fcst, 6 hr fcst, ... 96 hr fcst`, or windowed averages/accumulations for DSWRF/APCP.
- Hourly expansion: `src/weather/cleanWeatherData.py` converts 3-hour steps to hourly sequences for the 96-hour window using `createForecastColumns()` / `createAvgOrAccForecastColumns()` and writes `*_aggregated_weather_data.csv` with columns:
  - `forecast_avg_wind_speed_wMean`, `forecast_avg_temperature_wMean`, `forecast_avg_dewpoint_wMean`, `forecast_avg_dswrf_wMean`, `forecast_avg_precipitation_wMean`.
- These weather features are then merged with source forecasts to form the Tier-2 `..._96hr_forecasts*.csv` files.
  Note: The weather scripts in this branch write intermediate/output files under `../extn/<ISO>/weather_data/`. You can either copy/rename the aggregated hourly CSV to `data/<REGION>/<REGION>_weather_forecast.csv`, or point `WEATHER_FORECAST_IN_FILE_NAME` in `firstTierConfig.json` to the `extn/` path directly.

### Using `separateWeatherByRegion.py` (alternative GRIB2 → per‑region CSV)

If you already have per‑continent GFS GRIB2 files, you can aggregate them by ISO region using `src/weather/separateWeatherByRegion.py` and then clean to hourly with `cleanWeatherData.py`:

- Configure constants at the top of `separateWeatherByRegion.py`:
  - `FILE_DIR`: list of four input directories for `ugrd_vgrd/`, `tmp_dpt/`, `dswrf/`, `apcp/` that contain GRIB2 files.
  - `OUT_FILE_DIR`: output directory where per‑region CSVs will be written.
  - `YEARS`: list of years to process.
  - The script expects `wgrib2` on PATH and file naming like `gfs.0p25.<YYYYMMDD><HH>.fXXX.grib2`.
- Run per variable index (from `src/weather/`):
  - `python3 separateWeatherByRegion.py US 0`  # wind (ugrd_vgrd)
  - `python3 separateWeatherByRegion.py US 1`  # temperature/dewpoint (tmp_dpt)
  - `python3 separateWeatherByRegion.py US 2`  # dswrf
  - `python3 separateWeatherByRegion.py US 3`  # apcp
- Clean to hourly (still 96h by default):
  - Ensure `PREDICTION_PERIOD_DAYS = 4` in `cleanWeatherData.py`.
  - Run: `python3 cleanWeatherData.py US <OUT_FILE_DIR>`
- Output locations/names:
  - `separateWeatherByRegion.py` writes `<OUT_FILE_DIR>/<REGION>_<VAR>.csv` (e.g., `CISO_WIND_SPEED.csv`).
  - `cleanWeatherData.py` writes `<OUT_FILE_DIR>/<REGION>_aggregated_weather_data_2023.csv` and then a shifted `<REGION>_weather_forecast_2023.csv`.
  - Use the aggregated hourly file in Tier‑1 as `WEATHER_FORECAST_IN_FILE_NAME` or copy/rename to `data/<REGION>/<REGION>_weather_forecast.csv`.

For extending these scripts to 168h, see the dedicated 168h guide in `docs/EXTEND_TO_168H_CarbonCast.md`.


## Run it from scratch (step-by-step)

Prereqs
- Python 3.9+ recommended. Install requirements from project root:
  - `pip3 install -U -r requirements.txt`
- For weather collection: install and expose `wgrib2` in PATH; configure NCAR RDA client per README 5.1 (only needed if re-collecting weather).

1) Prepare per-source training CSVs (Tier-1)
- For each region you want, provide `data/<REGION>/fuel_forecast/<REGION>_<source>_2019_clean.csv` files with at least:
  - Columns: `UTC time`, `<source>`, `avg_<source>_production_forecast` (others like `Local time`, `carbon_intensity` may exist and are ignored for modeling depending on `SOURCE_COL` and `NUM_FEATURES`).
- Provide weather hourly CSV for the region: `data/<REGION>/<REGION>_weather_forecast.csv` with the five weather columns above.
- Update `src/firstTierConfig.json`:
  - `REGION`: e.g., `["CISO"]`
  - For that region block set paths, `SOURCES`, `SOURCE_COL`, `NUM_FEATURES`, `NUM_WEATHER_FEATURES` (5), `TRAIN_TEST_PERIOD` windows.

Run Tier-1 training/forecasting
- From `src/`: `python3 firstTierForecasts.py src/firstTierConfig.json`
- Outputs per-source day-ahead forecast CSVs to `data/<REGION>/fuel_forecast/*ANN_DA_<source>*.csv` and logs RMSE/MAPE files under `data/<REGION>/fuel_forecast/`.

2) Build the Tier-2 96h forecast input matrix
- Combine five weather features plus per-source forecast features aligned hourly over prediction windows into `data/<REGION>/<REGION>_96hr_forecasts_DA.csv`.
  - The repository already includes these for supported regions; if you regenerate, use the outputs of Tier-1 and the cleaned weather from `weather/` scripts. The expected header is shown in Data section (1).

3) Prepare historical CI series
- Use `data/<REGION>/<REGION>_direct_emissions.csv` or `..._lifecycle_emissions.csv` with columns listed above.
- If you need to compute these from raw source series, use `src/carbonIntensityCalculator.py` in real-time mode (`-r`) for direct or lifecycle factors.

4) Train or load Tier-2 and forecast 96 hours
- Update `src/secondTierConfig.json`:
  - `REGION`: list of regions to run.
  - Paths for: `DIRECT_CEF_IN_FILE_NAME` or `LIFECYCLE_CEF_IN_FILE_NAME`, and `FORECAST_IN_FILE_NAME`.
  - `NUM_FEATURES` (historical + datetime in Tier-2, typically 6) and `NUM_FORECAST_FEATURES` (first N columns of the forecast matrix to use).
  - Set `WRITE_CI_FORECASTS_TO_FILE` to the string "True" (not boolean) to emit CSV outputs (this branch checks string equality).
- From `src/`:
  - Train new model and forecast: `python3 secondTierForecasts.py src/secondTierConfig.json -d`
  - Load saved model (if present in `saved_second_tier_models/*`): `python3 secondTierForecasts.py src/secondTierConfig.json -d -s`
- Outputs: metrics in console; optional forecast CSVs under `CI_forecast_data/<REGION>/...`.

5) Optional: Compute CI from source forecasts (formula baseline)
- From `src/`: `python3 carbonIntensityCalculator.py <REGION> <-l|-d> -f <num_sources>`
  - Reads `data/<REGION>/<REGION>_96hr_source_prod_forecasts_DA_*.csv` and emits overall CI from those forecasts; prints MAPE vs actual.


## Important shapes and windows

- Sliding window length: 24 hours (`MODEL_SLIDING_WINDOW_LEN`).
- Prediction window: 96 hours (`PREDICTION_WINDOW_HOURS`).
- Tier-1 uses past `TRAINING_WINDOW_HOURS` to predict the next 24, iteratively rolling until 96; partial day-ahead known values can overwrite day-1.
- Tier-2 uses CNN+LSTM over concatenated history and aligned 96-hour forecast features.


## Code citations (where things happen)

- Tier-1
  - Config load and globals: `runFirstTier()`, `firstTierForecasts.py` lines ~22–69.
  - Init and feature engineering: `initialize()`, lines ~119–170; `common.addDateTimeFeatures()` in `src/common.py`.
  - Splits/scaling: `common.splitDataset()`, `common.splitWeatherDataset()`, `common.scaleDataset()` in `src/common.py`.
  - Training: `trainingandValidationPhase()`, `trainANN()` lines ~181–257.
  - Rolling forecasts: `getDayAheadForecasts()` and `getForecasts()` lines ~300–372.
  - Output: `writeSourceProductionForecastsToFile()` lines ~409–425.

- Tier-2
  - Config and run: `runSecondTier()` lines ~30–130.
  - Init: `initialize()` lines ~150–196 (adds datetime features here via local `addDateTimeFeatures()`).
  - Splits/scaling: lines ~101–146 using `common` functions.
  - Training: `trainingandValidationPhase()` and `trainModel()` lines ~484–566.
  - Inference: `getDayAheadForecasts()` lines ~318–383; `getForecasts()` lines ~396–412.
  - Metrics: `getUnscaledForecastsAndForecastAccuracy()` lines ~528–562 and `getScores()` lines ~247–306.
  - Saved model loading: when `-s` is used, the model path is taken from `DIRECT_SAVED_MODEL_LOCATION`/`LIFECYCLE_SAVED_MODEL_LOCATION` in `secondTierConfig.json` and loaded as `<location>/<region>.h5`.

- Weather processing
  - Download template and submission: `src/weather/getWeatherData.py` (uses `ds084.1_control.ctl`).
  - GRIB2 extraction and area-weighted means: `src/weather/dataCollectionScript.py` (`getWeatherData`, `getWindData`, `area_grid`).
  - Hourly expansion/cleaning: `src/weather/cleanWeatherData.py` (`createForecastColumns`, `createAvgOrAccForecastColumns`).


## Troubleshooting tips

- Duplicated column in some forecast CSVs (e.g., repeated `avg_wind_production_forecast`): ensure `NUM_FORECAST_FEATURES` selects only the first N relevant columns in `secondTierConfig.json`.
- Buffer alignment: Both tiers use `BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24` to ensure windows align; don’t trim files manually.
- NaNs: Both tiers fill missing values forward via `fillMissingData()`.
- TensorFlow macOS: requirements pin `tensorflow-macos==2.9.2` for Apple Silicon; use that if on M-series.


## Minimal “try it now” examples

- Tier-2 with provided data and direct factors. From `src/`:
  - `python3 secondTierForecasts.py src/secondTierConfig.json -d -s`  # use saved models if available
  - or `python3 secondTierForecasts.py src/secondTierConfig.json -d`   # train fresh
- Tier-1 per-source training for CISO:
  - Set `REGION: ["CISO"]` in `src/firstTierConfig.json` and run:
  - `python3 firstTierForecasts.py src/firstTierConfig.json`


## Script I/O reference (inputs and outputs at a glance)

### firstTierForecasts.py (Tier‑1)

- How to run
  - `python3 firstTierForecasts.py <configFileName>`
  - Example: `python3 firstTierForecasts.py src/firstTierConfig.json`

- Inputs (from config + files)
  - Config: `src/firstTierConfig.json` → regions, sources, file prefixes, features, windows.
  - Per‑source historical CSVs (example): `data/CISO/fuel_forecast/CISO_coal_2019_clean.csv`
    - Must include at least: `UTC time`, `<source>`, `avg_<source>_production_forecast`.
  - Weather hourly CSV (used for renewables): `data/CISO/CISO_weather_forecast.csv`
    - Columns: `forecast_avg_wind_speed_wMean`, `forecast_avg_temperature_wMean`, `forecast_avg_dewpoint_wMean`, `forecast_avg_dswrf_wMean`, `forecast_avg_precipitation_wMean`.
  - Where in code: `initialize()` loads and augments data (firstTierForecasts.py lines ~119–170); file names are built from `IN_FILE_NAME_PREFIX` + `<source>` + `IN_FILE_NAME_SUFFIX` and `WEATHER_FORECAST_IN_FILE_NAME`.

- Outputs
  - Per‑source forecast CSVs per experiment iteration under the region’s fuel_forecast directory.
    - File pattern from code: `<OUT_FILE_NAME_PREFIX>_<source>_iter<EXPT>.csv`
      - Example prefix: `data/CISO/fuel_forecast/CISO_ANN_DA` → files like `CISO_ANN_DA_coal_iter0.csv`
    - Columns written by `common.writeOutFile(...)`: `datetime, <source>_actual, avg_<source>_production_forecast`
  - Metrics: RMSE/MAPE text files: `data/<REGION>/fuel_forecast/<REGION>_RMSE_iter<EXPT><source>.txt`, `..._MAPE_...txt`.
  - Where in code: `writeSourceProductionForecastsToFile()` (firstTierForecasts.py lines ~409–425) and `common.writeOutFile()` (src/common.py).

- Example files in repo
  - Input: `data/CISO/fuel_forecast/CISO_coal_2019_clean.csv`
  - Input (weather): `data/CISO/CISO_weather_forecast.csv`
  - Output (example naming): `data/CISO/fuel_forecast/CISO_ANN_DA_coal_iter0.csv` (pattern as per code; variants exist like `CISO_ANN__DA_*` in repo history).


### secondTierForecasts.py (Tier‑2)

- How to run
  - `python3 secondTierForecasts.py <configFileName> <-l|-d> [-s]`
  - `-l` lifecycle factors; `-d` direct factors; `-s` to load a saved model.
  - Example: `python3 secondTierForecasts.py src/secondTierConfig.json -d -s`

- Inputs (from config + files)
  - Config: `src/secondTierConfig.json` → regions, windows, hyperparams, and file paths for:
    - Historical CI series: `DIRECT_CEF_IN_FILE_NAME` or `LIFECYCLE_CEF_IN_FILE_NAME` (e.g., `data/CISO/CISO_direct_emissions.csv`)
    - 96‑hour forecast feature matrix: `FORECAST_IN_FILE_NAME` (e.g., `data/CISO/CISO_96hr_forecasts_DA.csv`)
    - Feature counts: `NUM_FEATURES` (historical+datetime), `NUM_FORECAST_FEATURES` (first N forecast columns to use)
  - Where in code: `initialize()` reads both datasets and adds datetime features (secondTierForecasts.py lines ~150–196).

- Outputs
  - Console metrics: Overall RMSE and MAPE, plus per‑day MAPEs.
  - Optional CSV forecasts per experiment when `WRITE_CI_FORECASTS_TO_FILE` is `True` in config.
    - File pattern from code: `<OUT_FILE_NAME_PREFIX>_<EXPT>.csv`
      - Example prefix (direct): `CI_forecast_data/CISO/CISO_direct_96hr_CI_forecasts` → `..._0.csv`
    - Columns via `common.writeOutFile(...)` for CI: `datetime, carbon_intensity_actual, avg_carbon_intensity_forecast`
  - Where in code: write occurs inside `runSecondTier()` after `getUnscaledForecastsAndForecastAccuracy()` (secondTierForecasts.py lines ~208–230); field names are set in `common.writeOutFile()` when `fuel == "carbon_intensity"`.

- Example files in repo
  - Input (historical CI): `data/CISO/CISO_direct_emissions.csv`
  - Input (96h features): `data/CISO/CISO_96hr_forecasts_DA.csv`
  - Output: enable `WRITE_CI_FORECASTS_TO_FILE` to generate under `CI_forecast_data/<REGION>/...` with the pattern above.

## Appendix: Emission factors baseline

- Formula-based CI from forecasts implemented in `src/carbonIntensityCalculator.py` with median direct and lifecycle emission factors; see dicts `carbonRateDirect`, `forcast_carbonRateDirect`, `carbonRateLifecycle`, `forcast_carbonRateLifecycle` at top of file.

