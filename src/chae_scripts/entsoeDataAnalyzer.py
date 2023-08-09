import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# ENTSOE_SOURCE_LIST = ["coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "biomass", "geothermal", "unknown"]

AUTH_INTERVALS = {'AT': 15, 'BE': 60, 'BG': 60, 'HR': 60, 'CZ': 60, 'DK': 60, 'EE': 60, 
                  'FI': 60, 'FR': 60, 'DE': 15, 'GB': 30, 'GR': 60, 'HU': 15, 'IE': 60, 
                  'IT': 60, 'LV': 60, 'LT': 60, 'NL': 15, 'PL': 60, 'PT': 60, 'RO': 60, 
                  'RS': 60, 'SK': 60, 'SI': 60, 'ES': 60, 'SE': 60, 'CH': 60}

# Converting to common names as in eiaParser.py
ENTSOE_SOURCES = {
    "Biomass": "biomass",
    "Fossil Brown coal/Lignite": "coal",
    "Fossil Coal-derived gas": "nat_gas",
    "Fossil Gas": "nat_gas",
    "Fossil Hard coal": "coal",
    "Fossil Oil": "oil",
    "Fossil Oil shale": "coal",
    "Fossil Peat": "coal",
    "Geothermal": "geothermal",
    "Hydro Pumped Storage": "STOR",
    "Hydro Run-of-river and poundage": "hydro",
    "Hydro Water Reservoir": "hydro",
    "Marine": "unknown",
    "Nuclear": "nuclear",
    "Other renewable": "unknown",
    "Solar": "solar",
    "Waste": "biomass",
    "Wind Offshore": "wind",
    "Wind Onshore": "wind",
    "Other": "unknown"
}

# ENTSOE_BAL_AUTH_LIST = ['AT', 'DK']
ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
                         'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
                        'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']


def calculateMissingMinutes(ba, isProd, sourceDF, timeDF, missingData):
    newRow = {}
    if timeDF is None or timeDF.empty:
        missingRowMins = 0
    else:
        missingRowMins = int(float(timeDF.iloc[len(timeDF)-2, 0])) # minutes missing for all sources

    timeInterval = AUTH_INTERVALS[ba]
    if (ba == 'IE' and isProd):
        timeInterval = 30
    ROIntervalChanged = False
    ESIntervalChanged = False

    newRow["Region"] = ba
    newRow["Total"] = missingRowMins
    
    if sourceDF is None:
        print(ba, " has no missing source data")
    elif sourceDF.empty:
        for column in sourceDF.columns:
            newRow[ENTSOE_SOURCES[column]] = timeInterval
    else:
        for column in sourceDF.columns: # start off by adding the missing row minutes to all sources
            newRow[ENTSOE_SOURCES[column]] = missingRowMins
        for row in range(len(sourceDF)-2):
            sourceMissing = {}
            if (ba == 'RO' and row < len(sourceDF)-2 and not ROIntervalChanged):
                if (datetime.strptime(sourceDF.index.values[row], "%Y-%m-%d %H:%M:00+00:00")
                    >= (datetime.strptime("2021-01-31 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ROIntervalChanged = True
            elif (ba == 'ES' and row < len(sourceDF)-2 and not ESIntervalChanged):
                if (isProd and (datetime.strptime(sourceDF.index.values[row], "%Y-%m-%d %H:%M:00+00:00")) 
                    >= (datetime.strptime("2022-05-23 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ESIntervalChanged = True
                elif (not isProd and (datetime.strptime(sourceDF.index.values[row], "%Y-%m-%d %H:%M:00+00:00") 
                        >= datetime.strptime("2022-05-24 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                    timeInterval = 15
                    ESIntervalChanged = True

            for column in range(len(sourceDF.columns)):
                source = ENTSOE_SOURCES[sourceDF.columns[column]]
                if (sourceDF.iloc[row, column] == 'True' 
                    and (sourceMissing.get(source) == True or sourceMissing.get(source) == None)):
                    sourceMissing[source] = True
                else:
                    sourceMissing[source] = False
            srcmissing = False
            for source in sourceMissing.keys():    
                if sourceMissing[source] is True:
                    newRow[source] += timeInterval
                    srcmissing = True
            if srcmissing is True:
                newRow["Total"] += timeInterval
    
    tempDF = pd.DataFrame(newRow, index=[0])
    missingData = pd.concat([missingData, tempDF], axis=0, ignore_index=True)
    return missingData


def calculateMissingPercent(rowNum, sourcesList, ba, sourceDF, timeDF, missingData):
    newRow = {}
    if timeDF is None or timeDF.empty:
        missingRowMins = 0
    else:
        missingRowMins = int(float(timeDF.iloc[len(timeDF)-2, 0])) # minutes missing for all sources

    newRow["Region"] = ba
    newRow["Total"] = 0

    if len(sourcesList) == 0:
        print(ba, " has no missing source data")
    else:
    # calculate total number of sub-sources
        row = sourceDF.loc[rowNum]
        if len(sourcesList) != 0:
            for column in range(1, len(sourceDF.columns) - 1):
                newValue = row[sourceDF.columns[column]] # minutes missing for source
                newRow[sourceDF.columns[column]] = (missingRowMins + newValue) / (TOTAL_MINS) * 100
                if (not np.isnan(newValue)):
                    newRow["Total"] += newValue / (TOTAL_MINS * len(sourcesList)) * 100
        
    tempDF = pd.DataFrame(newRow, index=[0])
    missingData = pd.concat([missingData, tempDF], axis=0, ignore_index=True)
    return missingData


# def calculateMAPEofSolarWindForecast():

# used to be in main; moved outside for organization
def missingTimeCounterCaller():
    prodDataColumns = ["Region", "coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "biomass", "geothermal", "unknown", "Total"]
    fcstDataColumns = ["Region", "solar", "wind", "Total"]
    prodPercentData = pd.DataFrame(columns=prodDataColumns)
    fcstPercentData = pd.DataFrame(columns=fcstDataColumns)
    prodMinuteData = pd.DataFrame(columns=prodDataColumns)
    fcstMinuteData = pd.DataFrame(columns=fcstDataColumns)
    rowNum = 0
    for balAuth in ENTSOE_BAL_AUTH_LIST:
        
        print("Missing data for ", balAuth, " analyzing...")

        prodSourceDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_prod_missing_source_data.csv"))
        prodTimeDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_prod_interval_changes.csv"))    
        try:
            prodSourceDF = pd.read_csv(prodSourceDir, header=0, index_col=["UTC Time"])
            prodTimeDF = pd.read_csv(prodTimeDir, header=0, index_col=["Interval"])
        except:
            prodSourceDF = None
            prodTimeDF = None

        fcstSourceDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_fcst_missing_source_data.csv"))
        fcstTimeDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_fcst_interval_changes.csv"))
        try:
            fcstSourceDF = pd.read_csv(fcstSourceDir, header=0, index_col=["UTC Time"])
            fcstTimeDF = pd.read_csv(fcstTimeDir, header=0, index_col=["Interval"])
        except:
            fcstSourceDF = None
            fcstTimeDF = None

            
        # calculating percentage of missing forecast/production data
        prodMinuteData = calculateMissingMinutes(balAuth, True, prodSourceDF, prodTimeDF, prodMinuteData)        
        fcstMinuteData = calculateMissingMinutes(balAuth, False, fcstSourceDF, fcstTimeDF, fcstMinuteData)
        
        prodSourcesList = []
        try:
            for column in range(1, len(prodSourceDF.columns)):
                source = ENTSOE_SOURCES[prodSourceDF.columns[column]]
                if source not in prodSourcesList:
                    prodSourcesList.append(source)
        except:
            pass

        fcstSourcesList = []
        try:
            for column in range(1, len(fcstSourceDF.columns)):
                source = ENTSOE_SOURCES[fcstSourceDF.columns[column]]
                if source not in fcstSourcesList:
                    fcstSourcesList.append(source)
        except:
            pass
            
        prodPercentData = calculateMissingPercent(rowNum, prodSourcesList, balAuth, prodMinuteData, prodTimeDF, prodPercentData)
        fcstPercentData = calculateMissingPercent(rowNum, fcstSourcesList, balAuth, fcstMinuteData, fcstTimeDF, fcstPercentData)
        rowNum = rowNum + 1

    prodMinuteDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/prod_missing_min.csv"))
    with open(prodMinuteDir, 'w') as f:
        prodMinuteData.to_csv(f, index=False)

    fcstMinuteDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/fcst_missing_min.csv"))
    with open(fcstMinuteDir, 'w') as f:
        fcstMinuteData.to_csv(f, index=False)    

    prodPercentDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/prod_missing_per.csv"))
    with open(prodPercentDir, 'w') as f:
        prodPercentData.to_csv(f, index=False)

    fcstPercentDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/fcst_missing_per.csv"))
    with open(fcstPercentDir, 'w') as f:
        fcstPercentData.to_csv(f, index=False)  



if __name__ == "__main__":
    TOTAL_MINS = 1464 * 24 * 60 # 1464 days b/w 2019-01-01 and 2023-01-03
    missingTimeCounterCaller()