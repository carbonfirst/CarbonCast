# CarbonCast
CarbonCast: Multi-Day Forecasting of Grid Carbon Intensity
([PDF](https://groups.cs.umass.edu/ramesh/wp-content/uploads/sites/3/2022/09/buildsys2022-final282.pdf))
<br>

Version: 2.0 <br>
Authors: Diptyaroop Maji, Prashant Shenoy, Ramesh K Sitaraman <br>
Affiliation: University of Massachusetts, Amherst


<!-- ## CarbonCast Architecture
### First tier
### Second Tier
-->

[TODO:] Update readme about weather, config, cef etc.. Include weather src files, update data files.

## 1. Regions covered 
* US: 
    * California ([CISO](https://www.caiso.com/Pages/default.aspx))
    * Pennsylvania-Jersey-Maryland Interconnection ([PJM](https://www.pjm.com/))
    * Texas ([ERCOT](https://www.ercot.com/))
    * New England ([ISO-NE](https://www.iso-ne.com/))
* Europe (European regions are monitored by [ENTSOE](https://transparency.entsoe.eu/)):
    * Sweden
    * Germany

## 2. Data Sources
US ISO electricity generation by source: [EIA hourly grid monitor](https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48)

European regions electricity generation by source: [ENTSOE](https://transparency.entsoe.eu/)

Weather forecasts: [GFS weather forecast archive](https://rda.ucar.edu/datasets/ds084.1/)

Day-ahead solar/wind Forecasts:
* CISO: [OASIS](http://oasis.caiso.com/mrioasis/logon.do)
* European regions: [ENTSOE](https://transparency.entsoe.eu/)
* We currently do not have solar/wind forecasts for other regions, or for periods beyond 24 hours. Hence, we generate them using ANN models along with 96-hour forecasts for other sources.

## 3. Usage
### 3.1 Installing dependencies:
CarbonCast requires Python 3, Keras & Tensorflow 2.x <br>
Other required packages:
* Numpy, Pandas, MatplotLib, SKLearn, Pytz, Datetime
<!-- * ``` pip3 install numpy, matplotlib, sklearn, datetime, matplotlib ``` -->

### 3.2 Getting Weather data:
The aggregated & cleaned weather forecasts that we have used for our regions are provided in ```data/```. If you need weather forecasts for other regions, or even for the same regions (eg. if you want to use a different aggregation method or if you want to forecast for a different time period), the procedure is as follows:<br>
* GitHub repo of script to fetch weather data can be found [here](https://github.com/NCAR/rda-apps-clients).
* Once you have obtained the grib2 files, use the following files to aggregate & clean the data:<br>
```python3 getWeatherData.py```<br>
```python3 dataCollectionScript.py```<br>
```python3 cleanWeatherData.py```<br>

### 3.3 Getting source production forecasts:
For getting source production forecasts in the first-tier, run the following file:<br>
```python3 firstTierForecasts.py <configFileName> ```<br>
<b>Configuration file name:</b> <i>firstTierConfig.json</i> <br>
<b>Regions:</b> <i>CISO, PJM, ERCO, ISNE, SE, DE</i> <br>
<b>Sources:</b> <i>coal, nat_gas, oil, solar, wind, hydro, unknown, geothermal, biomass, nuclear</i> <br>
You can get source production forecasts of multiple regions together. Just add the new regions in the "REGION" parameter.
<!-- A detailed description of how to configure is given in Section 3.5 -->

### 3.4 Getting carbon intensity forecasts
For getting 96-hour average carbon intensity forecasts, run the following file: <br>
```python3 secondTierForecasts.py <configFileName> <-l/-d>```<br>
<b>Configuration file name:</b> <i>secondTierConfig.json</i> <br>
<b>Regions:</b> <i>CISO, PJM, ERCO, ISNE, SE, DE</i> <br>
<b><-l/-d>:</b> <i>Lifecycle/Direct</i> <br>


<!-- ### 3.5 Configuring CarbonCast:
Change the firstTierConfig.json and secondTierConfig.json files for desired configurations. Below are the fields used in the file along with their meaning:<br>
PREDICTION_WINDOW_HOURS: Prediction window in hours. (Default: 96) -->

## 4. Developer mode

We welcome users to suggest modifications to improve CarbonCast and/or add new features or models to the existing codebase. 
<!-- Use the developer branch to make edits and submit a change. -->

## 5. Citing CarbonCast
If you use CarbonCast, please consider citing our paper. The BibTex format is as follows: <br>
&nbsp; &nbsp; &nbsp; &nbsp;@article{maji2022carboncast,<br>
&nbsp; &nbsp; &nbsp; &nbsp;  title={CarbonCast: Multi-Day Forecasting of Grid Carbon Intensity},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  author={Maji, Diptyaroop and Shenoy, Prashant and Sitaraman, Ramesh K},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  booktitle={Proceedings of the Ninth ACM International Conference on Systems for Energy-Efficient Built Environments},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  year={2022}<br>
&nbsp; &nbsp; &nbsp; &nbsp;}<br>

## 6. Acknowledgements
This work is part of the [CarbonFirst](http://carbonfirst.org/) project, supported by NSF grant <> & VMware.