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

# ENTSOE_BAL_AUTH_LIST = ['DK', 'RO']
ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
                         'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
                        'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']


def calculateMissingMinutes(ba, isProd, sourceDF, timeDF, missingData):
    newRow = {}
    sourceMissing = {}
    missingRowMins = int(float(timeDF.iloc[len(timeDF)-2, 0])) # minutes missing for all sources

    timeInterval = AUTH_INTERVALS[ba]
    if (ba == 'IE' and isProd):
        timeInterval = 30
    ROIntervalChanged = False
    ESIntervalChanged = False
    
    for column in sourceDF.columns:
        newRow[ENTSOE_SOURCES[column]] = missingRowMins
    newRow["Region"] = ba
    newRow["Total"] = missingRowMins

    for row in range(len(sourceDF)-2):
        if (ba == 'RO' and row < len(sourceDF)-2 and not ROIntervalChanged):
            if (datetime.strptime(sourceDF.index[row], "%Y-%m-%d %H:%M:00+00:00")
                >= (datetime.strptime("2021-01-31 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                timeInterval = 15
                ROIntervalChanged = True
        elif (ba == 'ES' and row < len(sourceDF)-2 and not ESIntervalChanged):
            if (isProd and (datetime.strptime(sourceDF.index(row), "%Y-%m-%d %H:%M:00+00:00")) 
                >= (datetime.strptime("2022-05-23 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                timeInterval = 15
                ESIntervalChanged = True
            elif (not isProd and (datetime.strptime(sourceDF.index(row), "%Y-%m-%d %H:%M:00+00:00") 
                    >= datetime.strptime("2022-05-24 00:00:00+00:00", "%Y-%m-%d %H:%M:00+00:00"))):
                timeInterval = 15
                ESIntervalChanged = True
        for column in range(len(sourceDF.columns)):
            if (sourceDF.iloc[row, column] == 'True'):
                sourceMissing[ENTSOE_SOURCES[sourceDF.columns[column]]] = True
        for source in sourceMissing.keys():
            if sourceMissing[source] is True:
                newRow[source] += timeInterval
        newRow["Total"] += timeInterval
    
    missingData = pd.concat([missingData, pd.DataFrame(newRow, index=[0])], axis=0, ignore_index=True)
    return missingData


def calculateMissingPercent(ba, sourceDF, timeDF, missingData):
    newRow = {}
    numSources = {}
    missingRowMins = int(float(timeDF.iloc[len(timeDF)-2, 0])) # minutes missing for all sources

    # calculate total number of sub-sources
    for column in sourceDF.columns:
        source = ENTSOE_SOURCES[column]
        newRow[source] = 0
        try:
            numSources[source] += 1
        except:
            numSources[source] = 1 
    newRow["Region"] = ba
    newRow["Total"] = missingRowMins / TOTAL_MINS * 100 # initializing
  
    for column in range(len(sourceDF.columns)):
        source = ENTSOE_SOURCES[sourceDF.columns[column]]
        newValue = int(sourceDF.iloc[len(sourceDF)-2, column]) # minutes missing for source
        newRow[source] += (missingRowMins + newValue) / (TOTAL_MINS * numSources[source]) * 100
        newRow["Total"] += newValue / (TOTAL_MINS * len(sourceDF.columns)) * 100

    missingData = pd.concat([missingData, pd.DataFrame(newRow, index=[0])], axis=0, ignore_index=True)
    return missingData


if __name__ == "__main__":
    TOTAL_MINS = 1464 * 24 * 60 # 1464 days b/w 2019-01-01 and 2023-01-03
    prodDataColumns = ["Region", "coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "biomass", "geothermal", "unknown", "Total"]
    fcstDataColumns = ["Region", "solar", "wind", "Total"]
    prodPercentData = pd.DataFrame(columns=prodDataColumns)
    fcstPercentData = pd.DataFrame(columns=fcstDataColumns)
    prodMinuteData = pd.DataFrame(columns=prodDataColumns)
    fcstMinuteData = pd.DataFrame(columns=fcstDataColumns)

    for balAuth in ENTSOE_BAL_AUTH_LIST:

        # pulling prod data
        prodSourceDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_prod_missing_source_data.csv"))
        prodSourceDF = pd.read_csv(prodSourceDir, header=0, index_col=["UTC Time"])
        fcstSourceDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_fcst_missing_source_data.csv"))
        fcstSourceDF = pd.read_csv(fcstSourceDir, header=0, index_col=["UTC Time"])

        # pulling fcst data
        prodTimeDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_prod_interval_changes.csv"))
        prodTimeDF = pd.read_csv(prodTimeDir, header=0, index_col=["Interval"])
        fcstTimeDir = os.path.abspath(os.path.join(__file__, 
                                        f"../../../data/EU_DATA/{balAuth}/chae_reu/{balAuth}_fcst_interval_changes.csv"))
        fcstTimeDF = pd.read_csv(fcstTimeDir, header=0, index_col=["Interval"])

        # calculating percentage of missing forecast/production data
        prodMinuteData = calculateMissingMinutes(balAuth, True, prodSourceDF, prodTimeDF, prodMinuteData)
        fcstMinuteData = calculateMissingMinutes(balAuth, False, fcstSourceDF, fcstTimeDF, fcstMinuteData)
        
        prodPercentData = calculateMissingPercent(balAuth, prodSourceDF, prodTimeDF, prodPercentData)
        fcstPercentData = calculateMissingPercent(balAuth, fcstSourceDF, fcstTimeDF, fcstPercentData)


    prodMinuteDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/prod_missing_minute.csv"))
    with open(prodMinuteDir, 'w') as f:
        prodMinuteData.to_csv(f, index=False)

    fcstMinuteDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/fcst_missing_minute.csv"))
    with open(fcstMinuteDir, 'w') as f:
        fcstMinuteData.to_csv(f, index=False)    

    prodPercentDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/prod_missing_percent.csv"))
    with open(prodPercentDir, 'w') as f:
        prodPercentData.to_csv(f, index=False)

    fcstPercentDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/fcst_missing_percent.csv"))
    with open(fcstPercentDir, 'w') as f:
        fcstPercentData.to_csv(f, index=False)  
