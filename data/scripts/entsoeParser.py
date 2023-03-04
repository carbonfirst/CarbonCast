import csv
import sys
from datetime import datetime as dt
from datetime import timezone as tz
import requests
import pandas as pd
import numpy as np
import json
from entsoe import EntsoePandasClient

ENTSOE_API_KEY=""

# Referring ElectricityMap for grouping ENTSOE sources into used sources
#(Eg., nat_gas = fossil coal derived gas + fossil gas)
# Refer this: https://github.com/electricitymaps/electricitymaps-contrib/blob/master/parsers/ENTSOE.py

ENTSOE_SOURCES = {
    "Biomass": "BIO",
    "Fossil Brown coal/Lignite": "COAL",
    "Fossil Coal-derived gas": "NG",
    "Fossil Gas": "NG",
    "Fossil Hard coal": "COAL",
    "Fossil Oil": "OIL",
    "Fossil Oil shale": "COAL",
    "Fossil Peat": "COAL", # why is peat termed as coal by eMap?
    "Geothermal": "GEO",
    "Hydro Pumped Storage": "STOR",
    "Hydro Run-of-river and poundage": "HYD",
    "Hydro Water Reservoir": "HYD",
    "Marine": "UNK",
    "Nuclear": "NUC",
    "Other renewable": "UNK",
    "Solar": "SOL",
    "Waste": "BIO",
    "Wind Offshore": "WND",
    "Wind Onshore": "WND",
    "Other": "UNK",
    }

ENTSOE_SOURCE_MAP = {
        "BIO": "biomass",
        "COAL": "coal",
        "NG": "nat_gas",
        "GEO": "geothermal",
        "HYD": "hydro",
        "NUC": "nuclear",
        "OIL": "oil",
        "SOL": "solar",
        "WND": "wind",
        "UNK": "unknown",
}


def getProductionDataBySourceTypeDataFromENTSOE(region, year):
    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)

    startTime = None
    endTime = None
    # if (year == "2019"):
    #     startTime = pd.Timestamp('20190101', tz='UTC')
    #     endTime = pd.Timestamp('20200101', tz='UTC')
    # elif (year == "2020"):
    #     startTime = pd.Timestamp('20200101', tz='UTC')
    #     endTime = pd.Timestamp('20210101', tz='UTC')
    # elif (year == "2021"):
    #     startTime = pd.Timestamp('20210101', tz='UTC')
    #     endTime = pd.Timestamp('20220105', tz='UTC')
    # # elif (year == "2022"):
    # #     startTime = pd.Timestamp('20220101', tz='UTC')
    # #     endTime = pd.Timestamp('20220131', tz='UTC')
    countryCode = region  
    startTime = pd.Timestamp('20190101', tz='UTC')
    endTime = pd.Timestamp('20190102', tz='UTC')
    print(startTime, endTime, region)
    
    dataset = client.query_generation(countryCode, start=startTime,end=endTime, psr_type=None)
    print(dataset)
    exit(0)
    # dataset.to_csv("tempdata.csv")
    return dataset, startTime

def parseENTSOEProductionDataBySourceType(data, startTime):
    # print(data)
    datasetColumns = []
    datasetColumns.append("UTC time")
    sources = set()
    for i in range(len(data.columns.values)):
        colVal = data.columns.values[i]
        # print(type(data.columns.values[i]), data.columns.values[i])
        if (type(colVal) is tuple):
            colVal = colVal[0]
        sourceKey = ENTSOE_SOURCES[colVal]
        if (sourceKey == "STOR"):
            # print("STORAGE")
            continue # Ignoring storage for now
        source = ENTSOE_SOURCE_MAP[sourceKey]
        sources.add(source)
    sources = list(sources)
    # print(sources)
    datasetColumns.extend(sources)
    numSources = len(sources)

    electricityProductionData = []
    for i in range(len(data)):
        electricityBySource = []
        electricityBySource.append(data.index[i])
        aggregateSourceProduction = {}
        for j in range(len(data.columns.values)):
            colVal = data.columns.values[j]
            if (type(colVal) is tuple):
                colVal = colVal[0]
            sourceKey = ENTSOE_SOURCES[colVal]
            if (sourceKey == "STOR"):
                continue # Ignoring storage for now
            source = ENTSOE_SOURCE_MAP[sourceKey]
            if source in aggregateSourceProduction.keys():
                aggregateSourceProduction[source] += data.iloc[i][j]
            else:
                aggregateSourceProduction[source] = data.iloc[i][j]
        for j in range(1, len(datasetColumns)):
            electricityBySource.append(aggregateSourceProduction[datasetColumns[j]])
        electricityProductionData.append(electricityBySource)
    
    dataset = pd.DataFrame(electricityProductionData, columns=datasetColumns)
    return dataset, numSources


if __name__ == "__main__":
    if (len(sys.argv) != 2):
        print("Usage: python3 entsoeParser.py <region>")
        exit(0)
    region = sys.argv[1]
    years = ["2019", "2020", "2021"]
    for year in years:
        data, startTime = getProductionDataBySourceTypeDataFromENTSOE(region, year)
        dataset, numSources = parseENTSOEProductionDataBySourceType(data, startTime)
        # print(dataset)
        dataset.to_csv(region+"_"+year+".csv")

    # print(dataset)