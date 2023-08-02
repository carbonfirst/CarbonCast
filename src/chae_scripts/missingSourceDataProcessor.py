import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import sys


ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
                         'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
                        'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
# ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'EE', 'FI', 
#                          'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
# ENTSOE_BAL_AUTH_LIST = ['CZ'] # ['DK', 'DE', 'FR', 'RO']
INVALID_AUTH_LIST = ['AL', 'DK-DK2']


 # Regions with changing intervals have the initial intervals (ES, RO)
 # IE has different interval (production 30min forecast 1hr)
AUTH_INTERVALS = {'AT': 15, 'BE': 60, 'BG': 60, 'HR': 60, 'CZ': 60, 'DK': 60, 'EE': 60, 
                  'FI': 60, 'FR': 60, 'DE': 15, 'GB': 30, 'GR': 60, 'HU': 15, 'IE': 30, 
                  'IT': 60, 'LV': 60, 'LT': 60, 'NL': 15, 'PL': 60, 'PT': 60, 'RO': 60, 
                  'RS': 60, 'SK': 60, 'SI': 60, 'ES': 60, 'SE': 60, 'CH': 60}

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
    try:
        rawProductionData = pd.read_csv(rawProdDir, header=0, index_col=["UTC Time"])
    except:
        rawProductionData = None
    try:
        rawForecastData = pd.read_csv(rawFcstDir, header=0, index_col=["UTC Time"])
    except:
        rawForecastData = None

    return rawProductionData, rawForecastData

# find parts of the dataset where the time interval changes/is irregular
def findMissingSourceData(rawProdData, rawFcstData): 
    if (rawProdData is not None):
        # create a new dataframe to keep missing/changing time/rows of production data
        prodDF = pd.DataFrame(columns=rawProdData.columns.insert(0, "UTC Time"))
        for row in range(len(rawProdData)):      
            nanExists = False      
            newRow = {}
            newRow["UTC Time"] = rawProdData.index[row]
            for column in range(len(rawProdData.columns)):
                if (pd.isna(rawProdData.iloc[row, column])):
                    if (nanExists == False):
                        nanExists = True
                    newRow[rawProdData.columns[column]] = True
                else:
                    newRow[rawProdData.columns[column]] = False
            if nanExists:
                # newRow = pd.Series(newRow)
                prodDF = pd.concat([prodDF, pd.DataFrame(newRow, index=[0])], axis=0, ignore_index=True)
    else:
        prodDF = None
 
    if (rawFcstData is not None):
        # create a new dataframe to keep missing/changing time/rows of production data
        fcstDF = pd.DataFrame(columns=rawFcstData.columns.insert(0, "UTC Time"))
        for row in range(len(rawFcstData)):      
            nanExists = False      
            newRow = {}
            newRow["UTC Time"] = rawFcstData.index[row]
            for column in range(len(rawFcstData.columns)):
                if (pd.isna(rawFcstData.iloc[row, column])):
                    if (nanExists == False):
                        nanExists = True
                    newRow[rawFcstData.columns[column]] = True
                else:
                    newRow[rawFcstData.columns[column]] = False
            if nanExists:
                # newRow = pd.Series(newRow)
                fcstDF = pd.concat([fcstDF, pd.DataFrame(newRow, index=[0])], axis=0, ignore_index=True)
    else:
        fcstDF = None

    return prodDF, fcstDF

# Find values equal to TRUE and append the number of rows
def calculateMissingSourceData(ba, prodDF, fcstDF): # FIX: RO and ES to change intervals after the dates
    TOTAL_MINS = 1464 * 24 * 60 # 1464 days b/w 2019-01-01 and 2023-01-03
    timeInterval = AUTH_INTERVALS[ba]

    ROIntervalChanged = False
    ESIntervalChanged = False
    if (prodDF is not None): # send if statements for time intervals for ES and RO (changing time intervals)
        prodDF.loc[len(prodDF)] = 0
        prodDF.loc[len(prodDF)-1, "UTC Time"] = "Total Missing Minutes"
        for row in range(len(prodDF)-1):
            # if (row < len(prodDF)-1):
            if (ba == 'RO' and not ROIntervalChanged):
                if ((datetime.strptime(prodDF.loc[row, "UTC Time"], "%Y-%m-%d %H:%M:00+00:00")) 
                    >= (datetime.strptime("2021-01-31 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ROIntervalChanged = True
            elif (ba == 'ES' and not ESIntervalChanged):
                if ((datetime.strptime(prodDF.loc[row, "UTC Time"], "%Y-%m-%d %H:%M:00+00:00")) 
                    >= (datetime.strptime("2022-05-23 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ESIntervalChanged = True
            for column in prodDF.columns:
                if (prodDF.loc[row, column] == True):
                    prodDF.loc[len(prodDF)-1, column] += timeInterval
        
        prodDF.loc[len(prodDF)] = 0
        prodDF.loc[len(prodDF)-1, "UTC Time"] = "Percentage per Source"
        for source in prodDF.columns:
            if (source != "UTC Time"):
                prodDF.loc[len(prodDF)-1, source] = round(((prodDF.loc[len(prodDF)-2, source])/TOTAL_MINS*100), 4) # out of all possible "source data"

    if (ba == 'IE'):
        timeInterval = 60
    ROIntervalChanged = False
    ESIntervalChanged = False
    if (fcstDF is not None):
        fcstDF.loc[len(fcstDF)] = 0
        fcstDF.loc[len(fcstDF)-1, "UTC Time"] = "Total Missing Minutes"
        for row in range(len(fcstDF)-1):
            if (ba == 'RO' and not ROIntervalChanged):
                if ((datetime.strptime(fcstDF.loc[row, "UTC Time"], "%Y-%m-%d %H:%M:00+00:00")) 
                    >= (datetime.strptime("2021-01-31 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ROIntervalChanged = True
            elif (ba == 'ES' and not ESIntervalChanged):
                if ((datetime.strptime(fcstDF.loc[row, "UTC Time"], "%Y-%m-%d %H:%M:00+00:00")) 
                    >= (datetime.strptime("2022-05-24 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ESIntervalChanged = True
            for column in fcstDF.columns:
                if (fcstDF.loc[row, column] == True):
                    fcstDF.loc[len(fcstDF)-1, column] += timeInterval
        
        fcstDF.loc[len(fcstDF)] = 0
        fcstDF.loc[len(fcstDF)-1, "UTC Time"] = "Percentage per Source"
        for source in fcstDF.columns:
            if (source != "UTC Time"):
                fcstDF.loc[len(fcstDF)-1, source] = round(((fcstDF.loc[len(fcstDF)-2, source])/TOTAL_MINS*100), 4) # out of all possible "source data"

    return prodDF, fcstDF


if __name__ == "__main__":

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        rawProductionData, rawForecastData = getRawDataframe(balAuth)
        prodDF, fcstDF = findMissingSourceData(rawProductionData, rawForecastData) # returns all times when nan values exist

        # calculate total time & percentage of data missing per source; add up minutes & divide by total time
        productionDF, forecastDF = calculateMissingSourceData(balAuth, prodDF, fcstDF) # number of rows/time blocks

        if (productionDF is None):
            print("Original dataframe for " + balAuth + " production is empty\n")
        elif (productionDF.empty):
            print("No missing data for " + balAuth + " production data")
        else:
            print("\nProduction data info for :\n", balAuth, productionDF)
            prodDir = os.path.abspath(os.path.join(__file__, 
                    f"../../../data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_prod_missing_source_data.csv"))
            with open(prodDir, 'w') as f:
                productionDF.to_csv(f, index=False)

        if (forecastDF is None):
            print("Original dataframe for " + balAuth + " forecast is empty\n")
        elif (forecastDF.empty):
            print("No missing data for " + balAuth + " forecast data")
        else:
            print("\nForecast data info for :\n", balAuth, forecastDF)
            fcstDir = os.path.abspath(os.path.join(__file__, 
                    f"../../../data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_fcst_missing_source_data.csv"))
            with open(fcstDir, 'w') as f:
                forecastDF.to_csv(f, index=False)