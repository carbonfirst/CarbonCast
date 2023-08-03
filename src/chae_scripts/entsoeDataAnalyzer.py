import os
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import sys

ENTSOE_BAL_AUTH_LIST = ['DK', 'RO']
# ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
# ENTSOE_SOURCE_LIST = ["coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "biomass", "geothermal", "unknown"]

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


def calculateMissingData(ba, isMinute, sourceDF, timeDF, missingData):
    newRow = {}
    numSources = {}

    # calculate total number of sub-sources
    for column in sourceDF.columns:
        source = ENTSOE_SOURCES[column]
        newRow[source] = 0
        try:
            numSources[source] += 1
        except:
            numSources[source] = 1 

    # pull total rows/time missing; total missing minutes in second to the last row index 1
    # take the minute & recalculate percentage for sig figs loss
    newRow["Region"] = ba
    missingRowMins = int(float(timeDF.iloc[len(timeDF)-2, 0]))
    if isMinute:
        newRow["Total"] = missingRowMins
    else:
        newRow["Total"] = missingRowMins / TOTAL_MINS
  
    # add all source missing minutes; add to total
    for column in range(len(sourceDF.columns)):
        source = ENTSOE_SOURCES[sourceDF.columns[column]]
        newValue = int(sourceDF.iloc[len(sourceDF)-2, column])
        if isMinute:
            newRow[source] += newValue
            newRow["Total"] += newValue
        else:
            newRow[source] += newValue / (TOTAL_MINS * numSources[source]) * 100 # total missing minutes per source
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
        prodMinuteData = calculateMissingData(balAuth, True, prodSourceDF, prodTimeDF, prodMinuteData)
        fcstMinuteData = calculateMissingData(balAuth, True, fcstSourceDF, fcstTimeDF, fcstMinuteData)
        
        prodPercentData = calculateMissingData(balAuth, False, prodSourceDF, prodTimeDF, prodPercentData)
        fcstPercentData = calculateMissingData(balAuth, False, fcstSourceDF, fcstTimeDF, fcstPercentData)

    print(prodMinuteData, "\n", prodPercentData)
    # print(fcstMinuteData, fcstPercentData)
    exit()


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
