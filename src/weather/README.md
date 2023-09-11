# Getting Weather data from GFS forecast archive:
[Back to the main Readme file](../../README.md)

The aggregated and cleaned weather forecasts that we have used for our regions are provided in ```data/```. If you need weather forecasts for other regions, or even for the same regions (e.g., if you want to use a different aggregation method or if you want to forecast for a different time period), the procedure is mentioned below.<br>
* We fetch weather data from the [GFS weather forecast archive](https://rda.ucar.edu/datasets/ds084.1/). You will need to register 
before you can get weather data. Once you have registered, do the following:
* GitHub repo of script to fetch weather data can be found [here](https://github.com/NCAR/rda-apps-clients). You can follow the instructions there and download weather forecasts in grib2 format. The repo has a sample [Jupyter Notebook](https://github.com/NCAR/rda-apps-clients/blob/main/src/python/rdams_client_example.ipynb) with step-by-step instructions. Remember to modify the notebook as required (e.g., changing the dataset id (dsid)).
* Otherwise, clone the above repo and add the following two files in the ```rda-apps-clients/src/python``` folder: <br>
    ``` src/weather/getWeatherData.py,  src/weather/ds084.1_control.ctl ``` <br>
```getWeatherData.py``` uses ``` ds084.1_control.ctl ``` as a template file to download 96-hour weather forecasting data for a particular region. Change the template file for different regions and weather variables (weather variables include wind speed, temperature, dewpoint temperature, solar irradiance (dswrf), and precipitation). The template file has instructions on how to modify it for different regions and weather variables. After you have configured the template file, run: ```python3 getWeatherData.py```<br>
* You may need to add your credentials in ```rda-apps-clients/src/python/rdams_client.py``` for API calls to work. To do that, add the following as the first line in ```get_authentication()```:<br>
```write_pw_file(<username>, <password>)```
* Once you have obtained the grib2 files, use the following files to aggregate and clean the data:<br>
```python3 separateWeatherByRegion.py <continent> <index>``` -- this file uses code from [here](https://towardsdatascience.com/the-correct-way-to-average-the-globe-92ceecd172b7) for aggregating weather forecasts over specified continent. <br>
<b>Continent:</b> <i>US -- All US regions. </i><br>
<b>Index:</b> <i> 0: Wind speed, 1: Temperature/ Dewpoint, 2: DSWRF, 3: Annual precipitation.</i><br>
You can run the file in parallel with different indices.<br>
<b>You will need to modify the FILE_DIR, OUT_FILE_DIR & YEARS variables in ```separateWeatherByRegion.py``` (lines 27-32) with the correct paths/values for this to work.</b><br>
```python3 cleanWeatherData.py <continent>``` -- this file cleans the data and generates hourly files for the above specified weather variables.<br>
<b>Continent:</b> <i>US -- All US regions. </i><br>
You will need to modify the relevant fields in the above two files to successfully parse & clean the weather data. <br>
<b>You will need to modify the FILE_DIR variable in ```cleanWeatherData.py``` (line 21) with the correct paths for this to work.</b><br>
If you are using any other weather aggregating method, please feel free to modify the above files as required.

[Back to the main Readme file](../../README.md)