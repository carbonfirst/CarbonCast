import csv
import math
from datetime import datetime as dt
# from datetime import timedelta
from datetime import timezone as tz
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
import os
import sys

US_REGION_LIST = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPL", 
                "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYIS", "PACE", "PJM", 
                "SC", "SCEG", "SOCO", "TIDC", "TVA"] # add US regions here
EU_REGION_LIST = ["AL", "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", 
                  "FR", "GB", "GR", "HR", "HU", "IE", "IT", "LT", "LV", "NL", "PL", 
                  "PT", "RO", "RS", "SE", "SI", "SK"] # add EU regions here]

COLUMN_NAME = ["forecast_avg_wind_speed_wMean", "forecast_avg_temperature_wMean", "forecast_avg_dewpoint_wMean", 
                "forecast_avg_dswrf_wMean", "forecast_avg_precipitation_wMean"]


PREDICTION_PERIOD_DAYS = 4
PREDICTION_WINDOW_HOURS = 24 * PREDICTION_PERIOD_DAYS

def readFile(inFileName):
    print("Filename: ", inFileName)
    dataset = pd.read_csv(inFileName, header=0, parse_dates=['datetime'], index_col=['datetime'])
    dataset = dataset.iloc[:, 1:]    
    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values
    return dataset, dateTime

def getDatesInLocalTimeZone(dateTime):
    global LOCAL_TIMEZONE
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime)):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(LOCAL_TIMEZONE)
        dates.append(day)
    return dates

def writeLocalTimeToFile(dataset, dateTime, outFileName):
    localDates = getDatesInLocalTimeZone(dateTime)
    modifiedDataset = pd.DataFrame(index=dateTime)
    modifiedDataset["local_time"] = localDates
    modifiedDataset.index.name = "datetime"
    for col in dataset.columns.values:
        modifiedDataset[col] = dataset[col]
    print(modifiedDataset.head())
    modifiedDataset.to_csv(outFileName)
    return

def createHourlyTimeCol(dateTime):
    global PREDICTION_WINDOW_HOURS
    global PREDICTION_PERIOD_DAYS
    hourlyDateTime = []
    dayIndex = 0
    for dayIndex in range(len(dateTime)):
        hourlyDateTime.append(dateTime[dayIndex])
        for j in range(PREDICTION_WINDOW_HOURS-1):
            hourlyDateTime.append(hourlyDateTime[-1] + np.timedelta64(1, 'h'))
    return hourlyDateTime

def createForecastColumns(dataset, modifiedDataset, colName):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    idx, fcstIdx, i = 0, 0, 1
    while i < len(modifiedDataset.index.values):
        fcstIdx = 0
        j=3 # change this to j=1 for hourly weather forecasts
        while (j<=PREDICTION_WINDOW_HOURS): # changed from 24 for 96 hour forecast
            if(fcstIdx < j):
                fcstColName = str(j)+" hr fcst"
                modifiedDataset[colName].iloc[i] = dataset[fcstColName].iloc[idx]
                # print(i, j, idx, fcstIdx)
                fcstIdx += 1
                i += 1
                if(i == len(modifiedDataset.index.values)):
                    break
            else:
                j+=3 # change this to j+=1 for hourly weather forecasts
        idx += 1 # changed from 4 to 1 since we are not collecting updated weather data at 06, 12, 18 hours anymore
    if "wind" in colName:
        modifiedDataset[colName] = np.abs(modifiedDataset[colName].values)

    for i in range(PREDICTION_WINDOW_HOURS, len(modifiedDataset.index.values), PREDICTION_WINDOW_HOURS): # Check correctness
        modifiedDataset[colName].iloc[i] = modifiedDataset[colName].iloc[i-((PREDICTION_PERIOD_DAYS-1)*24)]

    return modifiedDataset

def createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, avgOrAcc):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    idx, fcstIdx, i = 0, 0, 1
    timePeriodSuffix = " hr "+avgOrAcc
    modifiedDatasetLength = len(modifiedDataset.index.values)
    while i < modifiedDatasetLength:
        fcstIdx = 0
        for hour in range(0, PREDICTION_WINDOW_HOURS, 3):
            timePeriod=""
            if hour%2==0: # n-(n+3) hour avg
                timePeriod = str(hour)+"-"+str(hour+3)+timePeriodSuffix
            else: # n-(n+6) hour avg --> eg. 0-6 hr avg. This is how ds084.1 returns, & how data is stored
                timePeriod = str(hour-3)+"-"+str(hour+3)+timePeriodSuffix
            nHourAvgorAcc = dataset[timePeriod].iloc[idx]
            while(fcstIdx < hour+3 and i < modifiedDatasetLength):
                # print(timePeriod, idx, i ,len(modifiedDataset.index.values))
                modifiedDataset[colName].iloc[i] = nHourAvgorAcc
                i += 1
                fcstIdx += 1
        idx += 1 # changed from 4 to 1 since we are not collecting updated weather data at 06, 12, 18 hours anymore

    for i in range(PREDICTION_WINDOW_HOURS, len(modifiedDataset.index.values), PREDICTION_WINDOW_HOURS):  # Check correctness
        modifiedDataset[colName].iloc[i] = modifiedDataset[colName].iloc[i-((PREDICTION_PERIOD_DAYS-1)*24)]

    return modifiedDataset

def createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, avgOrAcc):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    idx, fcstIdx, i = 0, 0, 1
    timePeriodSuffix = " hr "+avgOrAcc
    modifiedDatasetLength = len(modifiedDataset.index.values)
    while i < modifiedDatasetLength:
        fcstIdx = 0
        # for hour in range(1, PREDICTION_WINDOW_HOURS+1): # uncomment this line & comment below line for hourly forecasts
        for hour in range(3, PREDICTION_WINDOW_HOURS+1, 3):
            timePeriod= str(hour) + timePeriodSuffix
            nHourAvgorAcc = dataset[timePeriod].iloc[idx]
            while(fcstIdx < hour+3 and i < modifiedDatasetLength):
                modifiedDataset[colName].iloc[i] = nHourAvgorAcc
                i += 1
                fcstIdx += 1
        idx += 1 # changed from 4 to 1 since we are not collecting updated weather data at 06, 12, 18 hours anymore

    for i in range(PREDICTION_WINDOW_HOURS, len(modifiedDataset.index.values), PREDICTION_WINDOW_HOURS):  # Check correctness
        modifiedDataset[colName].iloc[i] = modifiedDataset[colName].iloc[i-((PREDICTION_PERIOD_DAYS-1)*24)]

    return modifiedDataset

def calcluateWindSpeed(dataset):
    dataset["forecast_wind_speed"] = [None]*len(dataset)
    for i in range(len(dataset)):
        u = dataset["forecast_u_wind"].iloc[i]
        v = dataset["forecast_v_wind"].iloc[i]
        dataset["forecast_wind_speed"].iloc[i] = round(math.sqrt(u*u * v*v), 5)
    return dataset


def startScript(regionList, fileDir, columnNames, isRealTime, startDate, creationTimeInUTC=None, version=None):
    for region in regionList:
        IN_FILE_NAMES = [region+"_WIND_SPEED.csv", region+"_TEMP.csv", region+"_DPT.csv", 
                         region+"_DSWRF.csv", region+"_APCP.csv"]
        regionFileDir = fileDir
        if (isRealTime is True):
            regionFileDir = fileDir + region + "/weather_data/"
            IN_FILE_NAMES = [region+"_WIND_SPEED_"+str(startDate)+".csv", 
                             region+"_TEMP_"+str(startDate)+".csv", 
                             region+"_DPT_"+str(startDate)+".csv", 
                             region+"_DSWRF_"+str(startDate)+".csv", 
                             region+"_APCP_"+str(startDate)+".csv"]
        dataset, dateTime = readFile(regionFileDir+IN_FILE_NAMES[0])
        # writeLocalTimeToFile(dataset, dateTime, OUT_FILE_NAMES[i])
        hourlyDateTime = createHourlyTimeCol(dateTime)
        modifiedDataset = pd.DataFrame(index=hourlyDateTime, 
                columns=columnNames)
        modifiedDataset.index.name = "datetime"
        for i in range(len(IN_FILE_NAMES)):
            dataset, dateTime = readFile(regionFileDir+IN_FILE_NAMES[i])
            colName = modifiedDataset.columns.values[i]
            modifiedDataset[colName].iloc[0] = 0
            if "dswrf" in colName:
                if (isRealTime is True):
                    modifiedDataset = createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "avg")
                else:
                    modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "avg")
            elif "precipitation" in colName:
                if (isRealTime is True):
                    modifiedDataset = createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "acc")
                else:
                    modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "acc")
            else:
                modifiedDataset = createForecastColumns(dataset, modifiedDataset, colName)
            modifiedDataset[colName].iloc[0] = modifiedDataset[colName].iloc[1]
            
        outFileName = regionFileDir+region+"_aggregated_weather_data_2023.csv"
        if (startDate is not None):
            outFileName = regionFileDir+"/../"+region+"_weather_forecast_"+str(startDate)+".csv"
        if (creationTimeInUTC is not None and version is not None):
            modifiedDataset.insert(0, "creation_time (UTC)", creationTimeInUTC)
            modifiedDataset.insert(1, "version", version)
        modifiedDataset.to_csv(outFileName)
    return

def aggregateWeatherDataAcrossYears(inFileDir, outFileDir, years):
    
    dataset = [None]*len(years)
    weatherVariables = ["apcp", "dpt", "dswrf", "temp", "wind_speed"]

    for region in ISO_LIST:
        for wv in weatherVariables:
            for i in range(len(years)):
                
                inFileName = inFileDir+str(years[i])+"/"+region+"_"+wv.upper()+".csv"
                outFileName = outFileDir+region+"_"+wv.upper()+".csv"
                print(inFileName)  
                if (not os.path.exists(inFileName)):
                    print(inFileName, "does not exist")
                    continue                
                dataset[i] = pd.read_csv(inFileName, header=0)
            for i in range(1, len(years)):
                dataset[0] = pd.concat([dataset[0], dataset[i]])
            modifiedDataset = pd.DataFrame(dataset[0])
            modifiedDataset.set_index("datetime")
            
            # print(modifiedDataset.head())
            modifiedDataset.to_csv(outFileName)

def moveForecastsAheadByADay(region, inFileDir, outFileDir):
    print(region)
    inFileName = inFileDir+region+"_aggregated_weather_data_2023.csv"
    outFileName = outFileDir+region+"_weather_forecast_2023.csv"
    dataset = pd.read_csv(inFileName, header=0, index_col=["datetime"])
    modifiedDataset = np.array(dataset.iloc[96:, :])
    zeroVal = np.zeros((96, len(dataset.columns)))
    modifiedDataset = np.vstack((modifiedDataset, zeroVal))

    modifiedDataset = pd.DataFrame(modifiedDataset, columns=dataset.columns.values, index=dataset.index)
    modifiedDataset.to_csv(outFileName)
    return

if __name__ == "__main__":
    print("Cleaning up weather data by CarbonCast regions...")
    print("Usage: python3 cleanWeatherData <continent> <infileDir>")
    print("Continent: US/EU") # curently, only US is supported
    if (len(sys.argv) < 3):
        print("Wrong no. of arguments!")
        exit(0)

    continent = sys.argv[1]
    inFileDir = sys.argv[2]
    # startYear = 2023
    # endYear = 2023
    ISO_LIST = US_REGION_LIST
    if (continent == "EU"):
        ISO_LIST = EU_REGION_LIST


    startScript(ISO_LIST, inFileDir, COLUMN_NAME, isRealTime=False, startDate=None, creationTimeInUTC=None, version=None)

    # years = [2019, 2020, 2021, 2022]
    # inFileDir = "EU_"
    # outFileDir = "./EU_total_aggregated_weather_data/"
    # aggregateWeatherDataAcrossYears(inFileDir, outFileDir, years)

    for region in ISO_LIST:
        moveForecastsAheadByADay(region, inFileDir=inFileDir, outFileDir=inFileDir)





    
    
    
    
    



