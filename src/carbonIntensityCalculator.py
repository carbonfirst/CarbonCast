'''
File to calculate real-time/historical carbon intensity values from source data, as well as
carbon intensity forecasts from source production forecasts (DACF).

CODE TO WRITE CARBON DATA TO FILE IS CURRENTLY COMMENTED. UNCOMMENT IF REQUIRED.
'''

import csv
import math
import sys
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
import tensorflow as tf

CARBON_INTENSITY_COLUMN = 1 # column for real-time carbon intensity
SRC_START_COL = 1
PREDICTION_WINDOW_HOURS = 96
MODEL_SLIDING_WINDOW_LEN = 24
TEST_PERIOD = "Jul_Dec_2021"

# Operational carbon emission factors
# Carbon rate used by electricityMap. Checkout this link:
# https://github.com/electricitymap/electricitymap-contrib/blob/master/config/co2eq_parameters_direct.json

# Median direct emission factors
carbonRateDirect = {"coal": 760, "biomass": 0, "nat_gas": 370, "geothermal": 0, "hydro": 0,
                "nuclear": 0, "oil": 406, "solar": 0, "unknown": 575, 
                "other": 575, "wind": 0} # g/kWh # check for biomass. it is > 0
forcast_carbonRateDirect = {"avg_coal_production_forecast": 760, "avg_biomass_production_forecast": 0, 
                "avg_nat_gas_production_forecast": 370, "avg_geothermal_production_forecast": 0, 
                "avg_hydro_production_forecast": 0, "avg_nuclear_production_forecast": 0, 
                "avg_oil_production_forecast": 406, "avg_solar_production_forecast": 0, 
                "avg_unknown_production_forecast": 575, "avg_other_production_forecast": 575, 
                "avg_wind_production_forecast": 0} # g/kWh # correct biomass

# Median lifecycle emission factors
carbonRateLifecycle = {"coal": 820, "biomass": 230, "nat_gas": 490, "geothermal": 38, "hydro": 24,
                "nuclear": 12, "oil": 650, "solar": 45, "unknown": 700, 
                "other": 700, "wind": 11} # g/kWh
forcast_carbonRateLifecycle = {"avg_coal_production_forecast": 820, "avg_biomass_production_forecast": 230, 
                "avg_nat_gas_production_forecast": 490, "avg_geothermal_production_forecast": 38, 
                "avg_hydro_production_forecast": 24, "avg_nuclear_production_forecast": 12, 
                "avg_oil_production_forecast": 650, "avg_solar_production_forecast": 45, 
                "avg_unknown_production_forecast": 700, "avg_other_production_forecast": 700, 
                "avg_wind_production_forecast": 11} # g/kWh


def initialize(inFileName):
    print("FILE: ", inFileName)
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=["UTC time"]) #, index_col=["Local time"]
    # print(dataset.head(2))
    # print(dataset.tail(2))
    dataset.replace(np.nan, 0, inplace=True) # replace NaN with 0.0
    num = dataset._get_numeric_data()
    num[num<0] = 0
    
    print(dataset.columns)
    # print("UTC time", dataset["UTC time"].dtype)
    return dataset

def createHourlyTimeCol(dataset, datetime, startDate):
    modifiedDataset = pd.DataFrame(np.empty((17544, len(dataset.columns.values))) * np.nan,
                    columns=dataset.columns.values)
    startDateTime = np.datetime64(startDate)
    hourlyDateTime = []
    hourlyDateTime.append(startDateTime)
    idx = 0
    modifiedDataset.iloc[0] = dataset.iloc[0]
    for i in range(17544-1):
        hourlyDateTime.append(hourlyDateTime[i] +np.timedelta64(1, 'h'))
        # # print(datetime[i+1], datetime[i], (datetime[i+1]-datetime[i]).total_seconds())
        # # if (hourlyDateTime[-1] != datetime[i+1]):
        # if ((pd.Timestamp(datetime[i+1]).hour-pd.Timestamp(datetime[i]).hour) != 1):
        #     if (pd.Timestamp(datetime[i]).hour == 23 and pd.Timestamp(datetime[i+1]).hour == 0):
        #         pass
        #     else:
        #     # print(i, hourlyDateTime[-1], datetime[i+1])
        #         print(i, datetime[i], datetime[i+1], pd.Timestamp(datetime[i]).hour, pd.Timestamp(datetime[i+1]).hour)
        #     # print(dataset.iloc[i-1])
        #     # print(dataset.iloc[i])
    # exit(0)
    return hourlyDateTime

def calculateCarbonIntensity(dataset, carbonRate, numSources):
    global CARBON_INTENSITY_COLUMN
    carbonIntensity = 0
    carbonCol = []
    miniDataset = dataset.iloc[:, CARBON_INTENSITY_COLUMN:CARBON_INTENSITY_COLUMN+numSources]
    print("**", miniDataset.columns.values)
    rowSum = miniDataset.sum(axis=1).to_list()
    for i in range(len(miniDataset)):
        if(rowSum[i] == 0):
            # basic algorithm to fill missing values if all sources are missing
            # just using the previous hour's value
            # same as electricityMap
            for j in range(1, len(dataset.columns.values)):
                if(dataset.iloc[i, j] == 0):
                    dataset.iloc[i, j] = dataset.iloc[i-1, j]
                miniDataset.iloc[i] = dataset.iloc[i, CARBON_INTENSITY_COLUMN:CARBON_INTENSITY_COLUMN+numSources]
                # print(miniDataset.iloc[i])
            rowSum[i] = rowSum[i-1]
        carbonIntensity = 0
        for j in range(len(miniDataset.columns.values)):
            source = miniDataset.columns.values[j]
            sourceContribFrac = miniDataset.iloc[i, j]/rowSum[i]
            # print(sourceContribFrac, carbonRate[source])
            carbonIntensity += (sourceContribFrac * carbonRate[source])
        if (carbonIntensity == 0):
            print(miniDataset.iloc[i])
        carbonCol.append(round(carbonIntensity, 2)) # rounding to 2 values after decimal place
    dataset.insert(loc=CARBON_INTENSITY_COLUMN, column="carbon_intensity", value=carbonCol)
    return dataset

def calculateCarbonIntensityFromSourceForecasts(dataset, carbonRate, numSources):
    global SRC_START_COL
    global CARBON_INTENSITY_COLUMN
    carbonCol = []
    miniDataset = dataset.iloc[:, SRC_START_COL:SRC_START_COL+numSources]
    print("**", miniDataset.columns.values)
    rowSum = miniDataset.sum(axis=1).to_list()
    for i in range(len(miniDataset)):
        if(rowSum[i] == 0):
            # basic algorithm to fill missing values if all sources are missing
            # just using the previous hour's value
            # same as electricityMap
            for j in range(1, len(dataset.columns.values)):
                if(dataset.iloc[i, j] == 0):
                    dataset.iloc[i, j] = dataset.iloc[i-1, j]
                miniDataset.iloc[i] = dataset.iloc[i, SRC_START_COL:SRC_START_COL+numSources]
                # print(miniDataset.iloc[i])
            rowSum[i] = rowSum[i-1]
        carbonIntensity = 0
        for j in range(len(miniDataset.columns.values)):
            source = miniDataset.columns.values[j]
            sourceContribFrac = miniDataset.iloc[i, j]/rowSum[i]
            # print(sourceContribFrac, carbonRate[source])
            carbonIntensity += (sourceContribFrac * carbonRate[source])
        if (carbonIntensity == 0):
            print(miniDataset.iloc[i])
        carbonCol.append(round(carbonIntensity, 2)) # rounding to 2 values after decimal place
    dataset.insert(loc=CARBON_INTENSITY_COLUMN, column="carbon_from_src_forecasts", value=carbonCol)
    return dataset


def getDatesInLocalTimeZone(dateTime, localTimezone):
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime), 24):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(localTimezone)
        dates.append(day)    
    return dates

def manipulateTestDataShape(data, slidingWindowLen, predictionWindowHours, isDates=False): 
    X = list()
    # step over the entire history one time step at a time
    for i in range(0, len(data)-(predictionWindowHours)+1, slidingWindowLen):
        # define the end of the input sequence
        predictionWindow = i + predictionWindowHours
        X.append(data[i:predictionWindow])
    if (isDates is False):
        X = np.array(X, dtype=np.float64)
    else:
        X = np.array(X)
    return X

def getMape(dates, actual, forecast, predictionWindowHours):
    mape = tf.keras.losses.MeanAbsolutePercentageError()
    # avgDailyMape = []
    # for i in range(0, len(actual), 24):
    #     mapeTensor =  mape(actual[i:i+24], forecast[i:i+24])
    #     mapeScore = mapeTensor.numpy()
    #     print("Day: ", dates[i], "MAPE: ", mapeScore)
    #     avgDailyMape.append(mapeScore)

    mse = tf.keras.losses.MeanSquaredError()

    rows, cols = len(actual)//predictionWindowHours, predictionWindowHours//24
    dailyMapeScore = np.zeros((rows, cols))
    dailyRmseScore = np.zeros((rows, cols))
    for i in range(0, len(actual), predictionWindowHours):
        for j in range(0, predictionWindowHours, 24):
            mapeTensor =  mape(actual[i+j:i+j+24], forecast[i+j:i+j+24])
            rmseScore = round(math.sqrt(mse(actual[i+j:i+j+24], forecast[i+j:i+j+24]).numpy()), 6)
            mapeScore = mapeTensor.numpy()
            dailyMapeScore[i//predictionWindowHours][j//24] = mapeScore
            dailyRmseScore[i//predictionWindowHours][j//24] = rmseScore

    mapeTensor =  mape(actual, forecast)
    mapeScore = mapeTensor.numpy()
    # return avgDailyMape, mapeScore
    return dailyMapeScore, mapeScore, dailyRmseScore

def runProgram(region, isLifecycle, isForecast):
    REAL_TIME_SRC_IN_FILE_NAME = None
    CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME = None
    FORECAST_SRC_IN_FILE_NAME = None
    CARBON_FROM_SRC_FORECASTS_OUT_FILE_NAME = None

    if (isLifecycle is True):
        if (isForecast is True):
            REAL_TIME_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+"_carbon_lifecycle_"+TEST_PERIOD+".csv"
            CARBON_FROM_SRC_FORECASTS_OUT_FILE_NAME = "../data/"+region+"/"+region+"_carbon_from_src_prod_forecasts_lifecycle_"+TEST_PERIOD+".csv"
            FORECAST_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+"_96hr_source_prod_forecasts_DA_"+TEST_PERIOD+".csv"
        else:
            # REAL_TIME_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+".csv"
            # CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME = "../data/"+region+"/"+region+"_lifecycle_emissions.csv"
            REAL_TIME_SRC_IN_FILE_NAME = "../v2.2/"+region+"/"+region+"_clean.csv"
            CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME = "../v2.2/"+region+"/"+region+"_lifecycle_emissions.csv"
    else:
        if (isForecast is True):
            REAL_TIME_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+"_carbon_direct_"+TEST_PERIOD+".csv"
            CARBON_FROM_SRC_FORECASTS_OUT_FILE_NAME = "../data/"+region+"/"+region+"_carbon_from_src_prod_forecasts_direct_"+TEST_PERIOD+".csv"
            FORECAST_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+"_96hr_source_prod_forecasts_DA_"+TEST_PERIOD+".csv"
        else:
            REAL_TIME_SRC_IN_FILE_NAME = "../data/"+region+"/"+region+".csv"
            CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME = "../data/"+region+"/"+region+"_direct_emissions.csv"
            REAL_TIME_SRC_IN_FILE_NAME = "../v2.2/"+region+"/"+region+"_clean.csv"
            CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME = "../v2.2/"+region+"/"+region+"_direct_emissions.csv"

    
    dataset = initialize(REAL_TIME_SRC_IN_FILE_NAME)
    numSources = len(dataset.columns)-1 # excluding UTC time
    forecastDataset = None
    if (isForecast is True):
        forecastDataset = initialize(FORECAST_SRC_IN_FILE_NAME)

    # Special case: SE unknown/other lifecycle CEF was 292.9 as per ElectricityMap
    # TODO: In later verwsions, make this saem as CEFs of other regions for consistency.
    if (region == "SE"):
        forcast_carbonRateLifecycle["avg_unknown_production_forecast"] = 292.9
        forcast_carbonRateLifecycle["avg_other_production_forecast"] = 292.9
        carbonRateLifecycle["unknown"] = 292.9
        carbonRateLifecycle["other"] = 292.9

    if (isLifecycle is True):
        if (isForecast is True):
            print("Calculating carbon intensity from src prod forecasts using lifecycle emission factors...")
            forecastDataset = calculateCarbonIntensityFromSourceForecasts(forecastDataset, forcast_carbonRateLifecycle, 
                        numSources)    
        else:
            print("Calculating real time carbon intensity using lifecycle emission factors...")
            dataset = calculateCarbonIntensity(dataset, carbonRateLifecycle, numSources)
    else:
        if (isForecast is True):
            print("Calculating carbon intensity from src prod forecasts using direct emission factors...")
            forecastDataset = calculateCarbonIntensityFromSourceForecasts(forecastDataset, forcast_carbonRateDirect, 
                        numSources)            
        else:
            print("Calculating real time carbon intensity using direct emission factors...")
            dataset = calculateCarbonIntensity(dataset, carbonRateDirect, numSources)

    if (isForecast is True):
        print("Carbon intensity forecasts:")
        actual = dataset["carbon_intensity"].values
        actual = manipulateTestDataShape(actual, 
                        MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
        actual = np.reshape(actual, actual.shape[0]*actual.shape[1])
        forecast = forecastDataset["carbon_from_src_forecasts"].values
        print("Actual shape: ", actual.shape, " Forecast shape: ", forecast.shape)
        dailyAvgMape, avgMape, dailyAvgRmse = getMape(forecastDataset["UTC time"].values, actual, 
                        forecast , PREDICTION_WINDOW_HOURS)

        print("Overall Mean MAPE: ", avgMape)
        print("Daywise statistics...")
        for i in range(0, PREDICTION_WINDOW_HOURS//24):
            print("Prediction day ", i+1, "(", (i*24), " - ", (i+1)*24, " hrs)")
            print("Mean MAPE: ", np.mean(dailyAvgMape[:, i]))
            print("Median MAPE: ", np.percentile(dailyAvgMape[:, i], 50))
            print("90th percentile MAPE: ", np.percentile(dailyAvgMape[:, i], 90))
            print("95th percentile MAPE: ", np.percentile(dailyAvgMape[:, i], 95))
            # print("99th percentile MAPE: ", np.percentile(dailyAvgMape[:, i], 99))
        
        outputDataset = pd.DataFrame()
        emissionFactorType = "direct"
        if (isLifecycle is True):
            emissionFactorType = "lifecycle"
        outputDataset["UTC time"] = forecastDataset["UTC time"].values
        outputDataset["actual_carbon_intensity_"+emissionFactorType] = actual
        outputDataset["forecasted_carbon_intensity_"+emissionFactorType] = forecast
        # outputDataset.to_csv(CARBON_FROM_SRC_FORECASTS_OUT_FILE_NAME)
    else:
        print("Real time carbon intensities:")
        # dataset.set_index("UTC time")
        dataset.to_csv(CARBON_FROM_REAL_TIME_SRC_OUT_FILE_NAME)
    
    return

def adjustColumns(region):
    sources = ["coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "other"]
    modifiedSources = []
    dataset = pd.read_csv("../v2.2/"+region+"/fuel_forecast/"+region+"_clean.csv", header=0, index_col=["UTC time"])
    print(dataset.shape)
    modifiedDataset = np.zeros(dataset.shape)
    idx = 0
    for source in sources:
        if (source in dataset.columns):
            modifiedSources.append(source)
            val = dataset[source].values
            modifiedDataset[:, idx] = val
            idx += 1
    modifiedDataset = pd.DataFrame(modifiedDataset, columns=modifiedSources, index=dataset.index)
    print(modifiedDataset.shape)
    modifiedDataset.to_csv("../v2.2/"+region+"/fuel_forecast/"+region+"_clean_mod.csv")
    return


if __name__ == "__main__":
    if (len(sys.argv) != 4):
        print("Usage: python3 carbonIntensityCalculator.py <region> <-l/-d> <-f/-r>")
        print("Refer github repo for regions.")
        print("l - lifecycle, d - direct")
        print("f - forecast, r - real time")
        # print("carbon_intensity_col - column no. where carbon_intensity should be inserted")
        exit(0)

    region = sys.argv[1]

    ISO_LIST = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPC", 
                "FPL", "GRID", "IPCO", "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYIS", 
                "PACE", "PACW", "PJM", "PSCO", "PSEI", "SC", "SCEG", "SOCO", "SPA", "SRP", 
                "SWPP", "TIDC", "TVA", "WACM", "WALC"]

    isForecast = False
    isLifecycle = False
    if (sys.argv[2].lower() == "-l"):
        isLifecycle = True
    if (sys.argv[3].lower() == "-f"):
        isForecast = True
    for region in ISO_LIST:
        # print(region)
        # adjustColumns(region)
        print("CarbonCast: Calculating carbon intensity for region: ", region)        
        # numSources = int(sys.argv[4])
        runProgram(region, isLifecycle, isForecast)
        # print("Calculating carbon intensity for region: ", region, " done.")
