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

ISO = "CISO"
LOCAL_TIMEZONES = {"BPAT": "US/Pacific", "CISO": "US/Pacific", "ERCO": "US/Central", 
                    "SOCO" :"US/Central", "SWPP": "US/Central", "FPL": "US/Eastern", 
                    "ISNE": "US/Eastern", "NYIS": "US/Eastern", "PJM": "US/Eastern", 
                    "MISO": "US/Eastern", "SE": "CET", "GB": "UTC", "DK-DK2": "CET",
                    "DE": "CET", "PL": "CET"}
# LOCAL_TIMEZONE = pytz.timezone(LOCAL_TIMEZONES[ISO])
# FILE_DIR = "../final_weather_data/"+ISO+"/" #/2019_weather_data
filedir = os.path.dirname(__file__)
IN_FILE_NAMES = [os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_AVG_WIND_SPEED.csv")), os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_AVG_TEMP.csv")), os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_AVG_DPT.csv")), os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_AVG_DSWRF.csv")), os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_AVG_APCP.csv"))]
OUT_FILE_NAMES = [os.path.normpath(os.path.join(filedir, f"extn/{ISO}/weather_data/{ISO}_weather_forecast.csv"))]
COLUMN_NAME = ["forecast_avg_wind_speed_wMean", "forecast_avg_temperature_wMean", "forecast_avg_dewpoint_wMean", 
                "forecast_avg_dswrf_wMean", "forecast_avg_precipitation_wMean"]


PREDICTION_PERIOD_DAYS = 4
PREDICTION_WINDOW_HOURS = 24 * PREDICTION_PERIOD_DAYS

def readFile(inFileName):
    print("Filename: ", inFileName)
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])    
    # print(dataset.head())
    # print(dataset.columns)
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
        j=1
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
                j+=1
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
        for hour in range(1, PREDICTION_WINDOW_HOURS):
            timePeriod= str(hour) + timePeriodSuffix
            # if hour%2==0: # n-(n+3) hour avg
            #     timePeriod = str(hour)+"-"+str(hour+3)+timePeriodSuffix
            # else: # n-(n+6) hour avg --> eg. 0-6 hr avg. This is how ds084.1 returns, & how data is stored
            #     timePeriod = str(hour-3)+"-"+str(hour+3)+timePeriodSuffix
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

def calcluateWindSpeed(dataset):
    dataset["forecast_wind_speed"] = [None]*len(dataset)
    for i in range(len(dataset)):
        u = dataset["forecast_u_wind"].iloc[i]
        v = dataset["forecast_v_wind"].iloc[i]
        dataset["forecast_wind_speed"].iloc[i] = round(math.sqrt(u*u * v*v), 5)
    return dataset

def aggregate_weather_data():
    dataset, dateTime = readFile(IN_FILE_NAMES[0])
    # writeLocalTimeToFile(dataset, dateTime, OUT_FILE_NAMES[i])
    hourlyDateTime = createHourlyTimeCol(dateTime)
    modifiedDataset = pd.DataFrame(index=hourlyDateTime, 
            columns=COLUMN_NAME)
    modifiedDataset.index.name = "datetime"
    for i in range(len(IN_FILE_NAMES)):
        dataset, dateTime = readFile(IN_FILE_NAMES[i])
        colName = modifiedDataset.columns.values[i]
        modifiedDataset[colName].iloc[0] = 0
        if "dswrf" in colName:
            modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "avg")
        elif "precipitation" in colName:
            modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "acc")
        else:
            modifiedDataset = createForecastColumns(dataset, modifiedDataset, colName) 
        print(modifiedDataset[colName].head())
        modifiedDataset[colName].iloc[0] = modifiedDataset[colName].iloc[1]
        
    modifiedDataset.to_csv(OUT_FILE_NAMES[0])

    
    
    
    
    



