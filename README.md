# CarbonCast
CarbonCast: Multi-Day Forecasting of Grid Carbon Intensity
([PDF](https://groups.cs.umass.edu/ramesh/wp-content/uploads/sites/3/2022/09/buildsys2022-final282.pdf)). An extended version of our paper appeared in ACM SIGEnergy Energy Informatics Review, and can be found [here](https://energy.acm.org/eir/multi-day-forecasting-of-electric-grid-carbon-intensity-using-machine-learning/).
<br>
CarbonCast provides average carbon intensity forecasts for up to 96 hours. This is an extension of [DACF](https://github.com/carbonfirst/DACF), which provides only day-ahead carbon intensity forecasts.

Version: 3.0 <br>
Authors: Diptyaroop Maji, Prashant Shenoy, Ramesh K Sitaraman <br>
Affiliation: University of Massachusetts, Amherst


<!-- ## CarbonCast Architecture
### First tier
### Second Tier
-->

<!-- [TODO:] Update readme about weather, config, cef etc.. Include weather src files, update data files. -->
## 0. Disclaimer
We will be periodically updating this repo as we update/improve/extend CarbonCast. Even after cloning the repo, please check back in a while to see if anything is updated. <br>
If something is not working, please check whether some recent update has already fixed that. <br>
In case something is not working in the latest version, or if there are any doubts/questions/suggestions, please feel free to reach us at dmaji at cs dot umass dot edu.

### 0.1 Current status:
Code files: Up to date as of 07/05/2023. <br>
Data files: Up to date as of 07/05/2023. <br>
Saved ML models for US regions: Up to date as of 07/05/2023. Models trained on 2020-2021 data. <br>
Latest stable commit: <br>

### 0.2 Changes in v3.0:
CarbonCast can fetch data & make predictions in real time for the US regions.

## 1. Regions covered 
EU & AUS regions are not updated yet. Only the US regions are up to date. <br>
* US ISOs (US region data collected from [EIA](https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48)):
    * Associated Electric Cooperative Incorporated ([AECI](https://www.aeci.org/))
    * Arizona Public Service Balancing Area ([AZPS](https://www.caiso.com/Documents/Structuralcompetitivenessoftheenergyimbalancemarket-ArizonaPublicServiceBalancingArea-June122020.pdf))
    * Bonneville Power Administration, Washington ([BPAT](https://www.bpa.gov/))
    * California ISO ([CISO](https://www.caiso.com/Pages/default.aspx))
    * Duke energy Carolinas ([DUK](https://www.duke-energy.com/home))
    * El Paso Electric ([EPE](https://www.epelectric.com/))
    * Electric Reliability Council of Texas ([ERCOT](https://www.ercot.com/). We refer the region as ERCO)
    * Florida Power & Light ([FPL](https://www.fpl.com/))
    * ISO New England ([ISO-NE](https://www.iso-ne.com/). We refer the region as ISNE.)
    * Los Angeles Department of Water and Power ([LDWP](https://www.ladwp.com/ladwp/faces/ladwp;jsessionid=wQ1RklMdsvY8KnjMYXnhh1zlhtv1q0QNJmdt9LQnLnCfTCtv31Y9!41721507?_afrLoop=469146466465544&_afrWindowMode=0&_afrWindowId=null#%40%3F_afrWindowId%3Dnull%26_afrLoop%3D469146466465544%26_afrWindowMode%3D0%26_adf.ctrl-state%3D174kwhmfu1_4))
    * Midcontinent Independent System Operator ([MISO](https://www.misoenergy.org/))
    * Nevada Power Company ([NEVP](https://www.nvenergy.com/))
    * NorthWestern Corporation ([NWMT](https://www.northwesternenergy.com/))
    * New York ISO ([NYISO](https://www.nyiso.com/). We refer to it as NYIS)
    * PacifiCorp East ([PACE](https://www.pacificorp.com/))
    * Pennsylvania-Jersey-Maryland Interconnection ([PJM](https://www.pjm.com/))
    * South Carolina Public Service Authority ([SC](https://www.santeecooper.com/))
    * Dominion Energy Inc, South Carolina ([SCEG](https://www.dominionenergy.com/south-carolina))
    * Southern Company Services Inc. ([SOCO](https://www.southerncompany.com/about/our-companies.html))
    * Salt River Project, Arizone ([SRP](https://www.srpnet.com/))
    * Turlock Irrigation District ([TIDC](https://www.tid.org/))
    * Tennessee Valley Authority ([TVA](https://www.tva.com/))
    * Western Area Power Administration, Rocky Mountain Region ([WACM](https://www.wapa.gov/regions/RM/Pages/rm.aspx))
* Europe regions (European regions are monitored by [ENTSOE](https://transparency.entsoe.eu/)):
    * Germany (DE)
    * Netherlands (NL)
    * Spain (ES)
    * Sweden (SE)
    * Poland (PL)
* Australia regions (Data for Australian regions is available at [OpenNEM](https://opennem.org.au/energy/nem/?range=7d&interval=30m))
    * Queensland (AUS-QLD)
<!-- * Canada
    * Ontario ([IESO](). We refer the region as CA_ON) -->

## 2. Data Sources
US ISO electricity generation by source: [EIA hourly grid monitor](https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48)

European regions electricity generation by source: [ENTSOE](https://transparency.entsoe.eu/)

Australian regions electricity generation by source: [OpenNEM](https://opennem.org.au/energy/nem/?range=7d&interval=30m)

Weather forecasts: [GFS weather forecast archive](https://rda.ucar.edu/datasets/ds084.1/)

Day-ahead solar/wind Forecasts:
* CISO: [OASIS](http://oasis.caiso.com/mrioasis/logon.do)
* European regions: [ENTSOE](https://transparency.entsoe.eu/)
* We currently do not have solar/wind forecasts for other regions, or for periods beyond 24 hours. Hence, we generate them using ANN models along with 96-hour forecasts for other sources.

## 3. Background on carbon intensity

### 3.1 Carbon emission factor (CEF):
CEF of a source is the amount of carbon emitted into the atmosphere per unit of electricity generated by that source. There can be two types of CEFs for a source: <br>
* Direct emission factors: These are the operational emissions when a source is converted into electricity. <br>
* Lifecycle emission factors: These include operational as well as infrastructural emissions up the supply chain. <br>
(See paper for further details.)

### 3.2 Calculating average carbon intensity:
We use the following formula for calculating avg carbon intensity:<br>
<img src="images/ci_avg_formula.png">    , where <br>
<br>
<i>CI<sub>avg</sub></i> = Average carbon intensity (real-time or forecast) of a region <br>
<i>E<sub>i</sub></i> = Electricity produced by source i. <br>
<i>CEF<sub>i</sub></i> = Carbon emission factor (lifecycle/direct) of source i. <br>

We have provided the file ``` carbonIntensityCalculator.py ``` to calculate both real-time/historical average CI values as well as carbon intensity forecasts from source prodution forecasts. Please refer to Section 4.4 for details.

## 4. Running CarbonCast with existing datasets and models

### 4.1 Installing dependencies:
CarbonCast is built on Python3. It uses Keras/Tensorflow for building the ML models, and wgrib2 for parsing weather forecasts. <br>
* Required packages & libraries are specified in ```installDependencies.sh```.<br>
* Required python modules are listed in ```requirements.txt```.<br>
Run ```source installDependencies.sh``` for installing the dependecies.
* wgrib2 (for weather data) should be correctly installed after the above command. If you need to install it from scratch, please refer 
[here](https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/compile_questions.html) for compilation/installation details. 
If you are using MacOS and having trouble compiling wgrib2, please refer to [this](https://theweatherguy.net/blog/weather-links-info/how-to-install-and-compile-wgrib2-on-mac-os-10-14-6-mojave/) article.
<!-- * ``` pip3 install numpy, matplotlib, sklearn, datetime, matplotlib ``` -->

### 4.2 Running CarbonCast using saved models/Reproducing results from paper:
We have saved second-tier models for each region which you can use with existing & new datasets to get 96-hour CI forecasts. These models are trained with data from Jan-Dec 2020 and validated with data from Jan-Jun 2021, so that results similar to the paper can be obtained when tested over Jul-Dec 2021. Each region has 2 saved models --- one for lifecycle CEF & the other for direct CEF. If you are using new datasets, you may need to update the models with new training data or generate new models.<br>
To run CarbonCast using the saved model for any region, run: <br>
```python3 secondTierForecasts.py <configFileName> <-l/-d> <-s>```<br>
<b>Configuration file name:</b> <i>secondTierConfig.json</i> <br>
<b>Regions:</b> <i>CISO, PJM, ERCO, ISNE, NYISO, FPL, BPAT, SE, DE, ES, NL, PL, AUS_QLD.</i> You can specify the region(s) in the configuration file. <br>
<b><-l/-d>:</b> <i>Lifecycle/Direct.</i> Relevant saved model for the specified region(s) will be loaded.<br>
<b><-s>: </b> <i>Use saved model.</i> Parameter that tells CarbonCast to use saved models and not train a new model.

## 5 Running CarbonCast in real time
<b>To run CarbonCast in real time (with new data/for new regions etc.), first install the dependencies mentioned in Section 4.1.
Then, follow the instructions specified [here](real_time/README.md).</b> <br>

<b>We welcome any feedback and feature request to make this better. Please raise an issue inthe GitHub if you have any
such request or if you found a bug.</b>


## 6 Running CarbonCast from scratch
To run CarbonCast from scratch (with new data/for new regions etc.), first install the dependencies mentioned in Section 4.1.

### 6.1 Getting Weather data:
Please refer to the [Weather Readme file](src/weather/README.md) for instructions on fetching and parsing weather forecast data from 
the GFS archive.

### 6.2 Getting source production forecasts:
You will need to obtain, clean, & format the datasets before you can get source production forecasts. You may also need to modify the configuration file as required.<br>
For getting source production forecasts in the first-tier, run the following file:<br>
```python3 firstTierForecasts.py <configFileName> ```<br>
<b>Configuration file name:</b> <i>firstTierConfig.json</i> <br>
<b>Regions:</b> <i>Specified in Section 1.</i> <br>
<b>Sources:</b> <i>coal, nat_gas, oil, solar, wind, hydro, unknown, geothermal, biomass, nuclear</i> <br>
You can get source production forecasts of multiple regions together. Just add the new regions in the "REGION" parameter.
<!-- A detailed description of how to configure is given in Section 3.5 -->

### 6.3 Calculating carbon intensity (real-time/historical/from source production forecasts):
For calculating real-time/historical carbon intensity from source data, or carbon intensity forecasts from the source production forecast data using the formula, run the following file: <br>
```python3 carbonIntensityCalculator.py <region> <-l/-d> <-f/-r> <num_sources>```<br>
<b>Regions:</b> <i>Specified in Section 1.</i> <br>
<b><-l/-d>:</b> <i>Lifecycle/Direct</i> <br>
<b><-f/-r>:</b> <i>Forecast/Real-time (or, historical)</i> <br>
<b>num_sources:</b> <i>No. of electricity producting sources in that region.</i> <br>

### 6.4 Getting carbon intensity forecasts using CarbonCast:
For getting 96-hour average carbon intensity forecasts, run the following file: <br>
```python3 secondTierForecasts.py <configFileName> <-l/-d>```<br>
<b>Configuration file name:</b> <i>secondTierConfig.json</i> <br>
<b>Regions:</b> <i>CISO, PJM, ERCO, ISNE, NYISO, FPL, BPAT, SE, DE, ES, NL, PL, AUS_QLD</i> <br>
<b><-l/-d>:</b> <i>Lifecycle/Direct</i> <br>
You can get carbon intensity forecasts of multiple regions together. Just add the new regions in the "REGION" parameter.

<!-- ### 3.5 Configuring CarbonCast:
Change the firstTierConfig.json and secondTierConfig.json files for desired configurations. Below are the fields used in the file along with their meaning:<br>
PREDICTION_WINDOW_HOURS: Prediction window in hours. (Default: 96) -->

## 7. Developer mode

We welcome users to suggest modifications to improve CarbonCast and/or add new features or models to the existing codebase. Please feel free to contact us at dmaji at cs dot umass dot edu with suggestions (or even working patches!)
<!-- Use the developer branch to make edits and submit a change. -->

## 8. Citing CarbonCast
If you use CarbonCast, please consider citing our paper. The BibTex format is as follows: <br>
&nbsp; &nbsp; &nbsp; &nbsp;@inproceedings{maji2022carboncast,<br>
&nbsp; &nbsp; &nbsp; &nbsp;  title={CarbonCast: multi-day forecasting of grid carbon intensity},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  author={Maji, Diptyaroop and Shenoy, Prashant and Sitaraman, Ramesh K},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  booktitle={Proceedings of the 9th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  pages={198--207},<br>
&nbsp; &nbsp; &nbsp; &nbsp;  year={2022}<br>
&nbsp; &nbsp; &nbsp; &nbsp;}<br>

## 9. Acknowledgements
This work is part of the [CarbonFirst](http://carbonfirst.org/) project, supported by NSF grants 2105494, 2021693, and 2020888, and a grant from VMware.
