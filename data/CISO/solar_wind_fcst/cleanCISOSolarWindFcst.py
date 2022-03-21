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

def cleanSolarProduction(inFileName):
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True)    
    print(dataset.head())
    # print(dataset.columns)
    solarPower = []
    for i in range(0, len(dataset), 3):
        solarPower.append(dataset["MW"].iloc[i]+dataset["MW"].iloc[i+1]+dataset["MW"].iloc[i+2])
    return solarPower

def cleanWindProduction(inFileName):
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True)    
    print(dataset.head())
    # print(dataset.columns)
    windPower = []
    for i in range(0, len(dataset), 2):
        windPower.append(dataset["MW"].iloc[i]+dataset["MW"].iloc[i+1])
    return windPower

def createDateTime():
    datetime = np.datetime64("2019-12-31T15:00")
    dateTimeList = []
    dateTimeList.append(datetime)
    for i in range(17552):
        # print(datetime)
        datetime = datetime + np.timedelta64(1, 'h')
        dateTimeList.append(datetime)
    return dateTimeList

def getDatesInLocalTimeZone(dateTime):
    global LOCAL_TIMEZONE
    dates = []
    fromZone = pytz.timezone("UTC")
    toZone = pytz.timezone("US/Pacific")
    for i in range(0, len(dateTime)):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(toZone)
        dates.append(day)
    return dates

datetime = createDateTime()
modifiedDataset = pd.DataFrame(np.empty((17553, 3)) * np.nan)
modifiedDataset.columns = ["datetime", "forecasted_avg_solar_production", "forecasted_avg_wind_production"]
modifiedDataset["datetime"] =  datetime
modifiedDataset["forecasted_avg_solar_production"] =  cleanSolarProduction("CISO_solar_production_forecast.csv")
modifiedDataset["forecasted_avg_wind_production"] =  cleanWindProduction("CISO_wind_production_forecast.csv")

print(modifiedDataset.head(24))
modifiedDataset.to_csv("cleaned_CISO_solar_wind_production_forecast.csv")