import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import sys

# ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
ENTSOE_BAL_AUTH_LIST = ['DK', 'DE', 'FR', 'RO'] # ['DK', 'DE', 'FR', 'RO']
INVALID_AUTH_LIST = ['AL', 'DK-DK2']

AUTH_INTERVALS = {'DK': 60, 'DE': 15, 'FR': 60, 'RO': 60 and 15, 'GB': 30} # for reference

# pd.set_option('display.max_columns', None)  # or 1000
# pd.set_option('display.max_rows', None)  # or 1000
# pd.set_option('display.max_colwidth', None)  # or 199

# get the dataframe with the raw production & forecast values
def getRawDataframe(ba):
    print("\nregion: ", ba)

    rawProdDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{ba}/ENTSOE/{ba}_raw_production.csv"))
    rawFcstDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{ba}/ENTSOE/{ba}_raw_forecast.csv"))
    
    rawProductionData = pd.read_csv(rawProdDir, header=0, index_col=["UTC Time"])
    rawForecastData = pd.read_csv(rawFcstDir, header=0, index_col=["UTC Time"])

    return rawProductionData, rawForecastData

# find parts of the dataset where the time interval changes/is irregular
def findChangingTimeIntervals(rawProdData, rawFcstData):  
    # create a new dataframe to keep missing/changing time/rows of production data
    prodDF = pd.DataFrame(columns=["Interval", "UTC Time", "Next Time", "Time Difference"])
    prodInterval = 0
    for row in range(len(rawProdData) - 1):
        curTime = rawProdData.index[row]
        nextTime = rawProdData.index[row + 1]
        timeDiff = (datetime.strptime(nextTime, "%Y-%m-%d %H:%M:00+00:00")
                    - datetime.strptime(curTime, "%Y-%m-%d %H:%M:00+00:00"))
        if (row == 0): # Assume 1st time block has data normal & time interval doesn't change; to check later manually
            prodInterval = timeDiff
        if (prodInterval > timedelta(hours=1)): # if data missing (more than 1hr), set interval to an hour
            prodInterval == timedelta(hours=1)
            # exit()
        
        # add if statement for when it goes from 1hr to less
        if (prodInterval == timedelta(hours=1) and timeDiff < timedelta(hours=1)): # changing interval to 1hr to smaller
            prodInterval = timeDiff
            print("Interval changed to " + str(prodInterval.seconds/60) + " minutes on " + curTime)
        elif (timeDiff > timedelta(hours=1) or prodInterval != timeDiff): # would catch any interval not equal to prodInterval
            newDFRow = {"Interval": prodInterval.seconds/60, "UTC Time": curTime, "Next Time": nextTime, "Time Difference": timeDiff}
            prodDF.loc[len(prodDF)] = newDFRow
 
    # do the same for forecast data
    fcstDF = pd.DataFrame(columns=["Interval", "UTC Time", "Next Time", "Time Difference"])
    fcstInterval = 0
    for row in range(len(rawFcstData) - 1):
        curTime = rawFcstData.index[row]
        nextTime = rawFcstData.index[row + 1]
        timeDiff = (datetime.strptime(nextTime, "%Y-%m-%d %H:%M:00+00:00")
                    - datetime.strptime(curTime, "%Y-%m-%d %H:%M:00+00:00"))
        if (row == 0):
            fcstInterval = timeDiff
        if (fcstInterval > timedelta(hours=1)): # if data missing (more than 1hr), set interval to an hour
            fcstInterval == timedelta(hours=1)
            # exit()

        #interval variance
        if (fcstInterval == timedelta(hours=1) and timeDiff < timedelta(hours=1)): # changing interval to 1hr to smaller
            fcstInterval = timeDiff
            print("Interval changed to " + str(fcstInterval.seconds/60) + " minutes on " + curTime)
        elif (timeDiff > timedelta(hours=1) or fcstInterval != timeDiff): # would catch any interval not equal to fcstInterval
            newDFRow = {"Interval": fcstInterval.seconds/60, "UTC Time": curTime, "Next Time": nextTime, "Time Difference": timeDiff}
            fcstDF.loc[len(fcstDF)] = newDFRow

    return prodDF, fcstDF


def calculateMissingTime(prodDF, fcstDF):
    totalProdMissingMin = 0
    for row in range(len(prodDF.index)):
        timeDiff = prodDF.loc[row, "Time Difference"]
        totalProdMissingMin = (totalProdMissingMin - prodDF.loc[row, "Interval"] 
                               + timeDiff.seconds/60 + timeDiff.days*24*60)
    print("Production data has total " + str(totalProdMissingMin) + " missing minutes; " 
            + str(round((totalProdMissingMin/TOTAL_MINS)*100, 4)) + " percent of the whole data")
    
    totalFcstMissingMin = 0
    for row in range(len(fcstDF.index)):
        timeDiff = fcstDF.loc[row, "Time Difference"]
        totalFcstMissingMin = (totalFcstMissingMin - fcstDF.loc[row, "Interval"] 
                               + timeDiff.seconds/60 + timeDiff.days*24*60)
    print("Forecast data has total " + str(totalFcstMissingMin) + " missing minutes; " 
            + str(round((totalFcstMissingMin/TOTAL_MINS)*100, 4)) + " percent of the whole data")


if __name__ == "__main__":
    TOTAL_MINS = 1464 * 24 * 60 # 1464 days b/w 2019-01-01 and 2023-01-03

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        rawProductionData, rawForecastData = getRawDataframe(balAuth)
        prodDF, fcstDF = findChangingTimeIntervals(rawProductionData, rawForecastData)

        if (prodDF.empty):
            print("No abnormal interval for " + balAuth + " production data")
        else:
            print("\nProduction data info:\n", prodDF)
        if (fcstDF.empty):
            print("No abnormal interval for " + balAuth + " forecast data")
        else:
            print("\nForecast data info:\n", fcstDF)

        if (not prodDF.empty and not fcstDF.empty):
            calculateMissingTime(prodDF, fcstDF)
        
        prodDir = os.path.abspath(os.path.join(__file__, 
                    f"../../../data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_prod_interval_changes.csv"))
        fcstDir = os.path.abspath(os.path.join(__file__, 
                    f"../../../data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_fcst_interval_changes.csv"))
        with open(prodDir, 'w') as f:
            prodDF.to_csv(f, index=False)
        with open(fcstDir, 'w') as f:
            fcstDF.to_csv(f, index=False)