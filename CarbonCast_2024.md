# Running CarbonCast (2024)

## Files 
Files were mainly uploaded to the data, src, and CI_forecast_data folder. 

### data
In the data folder, it contains the US and EU regions, along with the EU weather data for 2023. 

For the US and EU regions, it contains these 4 important files, listed below, which are necessarily for the UI. Additionally, it has the fuel_forecast folder and the daily folder which are used for first-tier and for the UI. 
* **{region}_clean.csv**,
* **{region}_direct_emissions.csv**, 
* **{region}_lifecycle_emissons**, 
* **{region}_96hr_forecasts_DA.csv**. 

Below is a comprehensive list of the US and EU regions, along with the missing regions/data: 

US regions (28): 

* AECI, AZPS, BPAT, CISO, DUK, EPE, ERCO, FPL, IPCO, ISNE, LDWP, MISO, NEVP, NWMT, NYIS, PACE, PACW, PJM, PSCO, SC, SCEG, SOCO, SPA, SRP, SWPP, TIDC, TVA, WACM
* **Missing: FPC, GRID, PSEI, WALC, RO**

EU regions (26): 

* AT, BE, BG, CH, CZ, DE, DK, EE, ES, FI, FR, GB, GR, HR, HU, IE, IT, LT, LV, NL, PL, PT, RS, SE, SI, SK
* **Missing: AL, BA, CY, GE, LU, MD, ME, MK, NO, UK**

### src 
* [concatFiles.py](../src/concatFiles.py) 
* [concatWeather.py](../src/concatWeather.py) 
* [dailyFetcherEU.py](../src/dailyFetcherEU.py) 
* [dailyFetcherUS.py](../src/dailyFetcherUS.py)
* [missingData.py](../src/missingData.py)

concatFiles.py and concatWeather.py are uses to combine the older data with the recent data. dailyFetcher are uses to fetch files from the data and CI_forecast_data folder for a format use by the UI, and this is stored in a folder call daily within each region. missingData.py is use to fill missing source column data with values like 0s. 

### CI_forecast_data
In each of the US and EU regions listed above. Their CI_forecast_data files contains 6 important files which are: 

* **{region}_direct_96hr_CI_forecasts_0PERIOD_{num}.csv**
* **{region}_lifecycle_96hr_CI_forecasts_0PERIOD_{num}.csv**

The num is either 0, 1, or 2 which are the 3 training periods in the second-tier. 

## Accomplishment in 2024 
1. Fetch the sources data for the missing EU regions. If you want to fetch the weather data, please refer to this [wgrib2](https://theweatherguy.net/blog/how-to-install-and-compile-wgrib2-on-mac-os-apple-silicon-m1-m3-clean-install-version/) guide.
2. Run first-tier and second-tier for all the US and EU regions that were not missing. 
```
python3 firstTierForecasts.py firstTierConfig.json 
python3 secondTierForecasts.py secondTierConfig.json -d
python3 secondTierForecasts.py secondTierConfig.json -l
```
3. Create python scripts for merging old and new data, extracting daily files, and filling in missing hour/columns.
4. Extend first-tier to support other machine learning models (GRU, RNN, LSTM, MLP, Transformers, Random Forest, XGBoost).
5. Found new metrics to evaluate the forecasts. A few notable ones were: 
* Mean Bias Error (MBE) - average bias in the model indicating if a model is over or under predicting (implemented in first-tier)
* SMA (Simple Moving Average)
* DTW (Dynamic Time Warping)
* [Similarity_Between_2_Numbers](https://math.stackexchange.com/questions/1481401/how-to-compute-similarity-between-two-numbers)
6. Data analysis for first and second tier. Some results that may be useful for future work: 
* Under time and computational constraints, MLP will be an ideal substitue for non-renewable sources. Meanwhile for renewable sources, maintain the original model (ANN). 
* Variation in a model's performance is due to seasonal dependencies and noisy data, since renewable sources like solar, wind, and hydro is connected with weather features like windSpeed and precipitation. Thus, during spring and summer the forecasts will be closer to the actual. 
* We will want models like LSTM that captures long-term dependencies and avoid machine learning architecture that does not contain memory components. 