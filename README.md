# CarbonCast
A system to predict short-term carbon intensity in the power grids using machine learning.<br>
[Link to paper]()

Version: 1.0 <br>
Authors: Diptyaroop Maji, Ramesh K Sitaraman, Prashant Shenoy <br>
Affiliation: University of Massachusetts, Amherst


<!-- ## CarbonCast Architecture
### First tier
### Second Tier
#### CarbonCastCNN
#### CarbonCastLR -->

## Regions covered 
1. US: 
    * California
    * Pennsylvania-Jersey-Marylan Interconnection
    * Texas
    * New England
2. Europe:
    * Sweden
    * Germany

## Data Sources
US ISO electricity generation by source: [EIA hourly grid monitor](https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48)

Europe zones electricity generation by source:

Weather forecasts:

Solar Wind Forecasts:
* CISO:
* European zones:

## Usage
### Running CarbonCast
1. CarbonCastCNN:
python3 forecastCarbonIntensity.py
2. CarbonCastLR:
python3 lrCarbonIntensity.py

### Weather data cleaning and aggregation
### Obtaining & cleaning source production forecasts

### Changing confifurations:
Change the config.json file for desired configurations. Below are the fields used in the file along with their meaning:<br>
PREDICTION_WINDOW_HOURS: Prediction window in hours. (Default: 24, for day-ahead forecasting)

## Citing CarbonCast: