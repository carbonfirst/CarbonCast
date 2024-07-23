# Running CarbonCast in real time
[Back to the main Readme file](../README.md)

Currently, CarbonCast can work in real time for the US regions specified in the main page. <br>
We recommend running this as a cron job every day at after midnight (We have not yet checked how fast the latest data is 
updated in the websites from where we fetch our data, but we assume 1:00 am should be fine). <br>

Command to run CarbonCast: ``` python3 CarbonCastE2E.py <continent> <date>``` <br>
``` continent: Currently, only "US" is supported. Modify the list of regions (variable: US_REGIONS) in CarbonCastE2E.py as required.``` <br>
``` date: Any date within the last 10 days from the current date in YYYY-MM-DD format. If not date is specified, it takes the current data by default.``` <br>
Any date beyond the last 10 days will give an error, as weather data is not available. To run CarbonCast for an earlier period, follow Section 6 in the main Readme file. <br>

### Steps in running CarbonCast end-to-end:
1. Fetch electricity data of previous day from EIA. Code is in [eiaParser.py](../src/eiaParser.py). ([An API call example](https://www.eia.gov/opendata/browser/electricity/rto/fuel-type-data?frequency=hourly&data=value;&start=2023-07-05T00&sortColumn=period;&sortDirection=desc;)). <br>
2. Fetch and aggregate 96-hour weather forecasts from the current date from [NCEP NOMADS](https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl). Code is in [getRealTimeWeatherData.py](../src/weather/getRealTimeWeatherData.py) <br>
3. Fetch day-ahead solar & wind production forecasts, if they are available for a region. Currently, only CISO is supported. 
Code is in [cisoSolarWindForecastParser.py](../src/cisoSolarWindForecastParser.py). 
4. Get the source production forecasts using saved first-tier models and save them in a file. Code is in [firstTierForecasts.py](../src/firstTierForecasts.py)<br>
5. Generate 96-hour CI forecasts (using both lifecycle and direct CEF) using saved seond-tier models and save them in a file. Code is in [secondTierForecasts.py](../src/secondTierForecasts.py). The CI forecasts files are saved in the respective ```real-time/<region>/``` folders.