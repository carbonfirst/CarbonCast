import os
import pandas as pd
from entsoe import EntsoePandasClient
from datetime import datetime, timedelta
import time
import numpy as np
import sys

# ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
ENTSOE_BAL_AUTH_LIST = ['DK', 'DE', 'FR', 'RO'] # ['DK', 'DE', 'FR', 'RO']
INVALID_AUTH_LIST = ['AL', 'DK-DK2']

# get the dataframe with the raw production & forecast values
def getRawDataframe(ba):
    print("region: ", ba)

    rawProdDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{ba}/ENTSOE/{ba}_raw_production.csv"))
    rawFcstDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{ba}/ENTSOE/{ba}_raw_forecast.csv"))
    
    rawProductionData = pd.read_csv(rawProdDir, header=0, index_col=["UTC Time"])
    rawForecastData = pd.read_csv(rawFcstDir, header=0, index_col=["UTC Time"])

    return rawProductionData, rawForecastData

# calculate how much time/row is missing in the dataframes
def findMissingTimeIntervals(rawProdData, rawFcstData):  
    # create a new dataframe to keep missing time/rows of production data
    prodDF = pd.DataFrame(columns=["UTC Time", "Next Time", "Time Difference"])
    prodMissingTime = timedelta(0)

    for row in range(len(rawProdData) - 1):
        curTime = rawProdData.index[row]
        nextTime = rawProdData.index[row + 1]
        if (row == 0):
            oldTimeDiff = timedelta(hours=0)
        timeDiff = (datetime.strptime(nextTime, "%Y-%m-%d %H:%M:00+00:00")
                    - datetime.strptime(curTime, "%Y-%m-%d %H:%M:00+00:00"))
        
        #interval variance
        if ((timeDiff > timedelta(hours=1)) or (timeDiff < timedelta(hours=1) and timeDiff != oldTimeDiff)): # treat 1hr interval as default
            newDFRow = {"UTC Time": curTime, "Next Time": nextTime, 
                        "Time Difference": str(timeDiff.days) + " days " + str(timeDiff.seconds/60) + " minutes"}
            prodDF.loc[len(prodDF)] = newDFRow
            prodMissingTime = prodMissingTime + timeDiff
        oldTimeDiff = timeDiff

    # do the same for forecast data
    fcstDF = pd.DataFrame(columns=["UTC Time", "Next Time", "Time Difference"])
    fcstMissingTime = timedelta(0)

    for row in range(len(rawFcstData) - 1):
        curTime = rawFcstData.index[row]
        nextTime = rawFcstData.index[row + 1]
        if (row == 0):
            oldTimeDiff = timedelta(hours=0)
        timeDiff = (datetime.strptime(nextTime, "%Y-%m-%d %H:%M:00+00:00")
                    - datetime.strptime(curTime, "%Y-%m-%d %H:%M:00+00:00"))
        
        #interval variance
        if ((timeDiff > timedelta(hours=1)) or (timeDiff < timedelta(hours=1) and timeDiff != oldTimeDiff)): # treat 1hr interval as default
            newDFRow = {"UTC Time": curTime, "Next Time": nextTime, 
                        "Time Difference": str(timeDiff.days) + " days " + str(timeDiff.seconds/60) + " minutes"}
            fcstDF.loc[len(fcstDF)] = newDFRow
            fcstMissingTime = fcstMissingTime + timeDiff
        oldTimeDiff = timeDiff

    return prodDF, fcstDF, prodMissingTime, fcstMissingTime # returning in minutes


if __name__ == "__main__":
    TOTAL_MINS = 1464 * 24 * 60 # 1464 days b/w 2019-01-01 and 2023-01-03

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        rawProductionData, rawForecastData = getRawDataframe(balAuth)
        
        prodDF, fcstDF, prodMissingTime, fcstMissingTime = findMissingTimeIntervals(rawProductionData, rawForecastData)
        prodMissingMinutes = prodMissingTime.days * 24 * 60 + prodMissingTime.seconds / 60
        fcstMissingMinutes = fcstMissingTime.days * 24 * 60 + fcstMissingTime.seconds / 60  

        print("\nProduction data info:\n", prodDF)
        print("\nForecast data info:\n", fcstDF)

        print("\nsummary:")
        print("Production data has total " + str(prodMissingMinutes) + " minutes missing; " 
              + str(round((prodMissingMinutes/TOTAL_MINS)*100, 4)) + " percent of the whole data")
        print("Forecast data has total " + str(fcstMissingMinutes) + " minutes missing; " 
              + str(round((fcstMissingMinutes/TOTAL_MINS)*100, 4)) + " percent of the whole data")