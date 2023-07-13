# initially copied from eiaParser.py in v3.0 branch then tweaked
import os
import requests
import pandas as pd
from entsoe import EntsoePandasClient
from datetime import datetime, timedelta
import time
import sys
import numpy as np

# public key for ENTSOE API
ENTSOE_API_KEY="c0b15cbf-634c-4884-b784-5b463182cc97"

# Referring ElectricityMap for grouping ENTSOE sources into used sources
#(Eg., nat_gas = fossil coal derived gas + fossil gas)
# Refer this: https://github.com/electricitymaps/electricitymaps-contrib/blob/master/parsers/ENTSOE.py

# Converting to common names as in eiaParser.py
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

# map ENTSOE fuel types to source types
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

ENTSOE_BAL_AUTH_LIST = ["AL", "AT", "BE", "BG", "HR", "CZ", "DK", "DK-DK2", "EE", "FI", 
                        "FR", "DE", "GB", "GR", "HU", "IE", "IT", "LV", "LT", "NL",
                        "PL", "PT", "RO", "RS", "SK", "SI", "ES", "SE", "CH"]  

# get production data by source type from ENTSOE API
def getProductionDataBySourceTypeDataFromENTSOE(ba, curDate, curEndDate):
    print(ba)

    # necessary for client i think
    startDate = pd.Timestamp(curDate, tz='UTC')
    endDate = pd.Timestamp(curEndDate, tz='UTC')

    print(startDate, endDate)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    dataset = client.query_generation(ba, start=startDate,end=endDate, psr_type=None)
    return dataset, startDate

# parse production data by source type from ENTSOE API
def parseENTSOEProductionDataBySourceType(data, startDate, electricitySources, numSources):
    electricityBySource = {}
    hourlyElectricityData = []
    electricityProductionData = []
    # startDate = startDate + " 00:00"
    # electricityBySource.append(startDate)
    # dateObj = datetime.strptime(startDate, "%Y-%m-%d %H:%M")



    if (len(data) == 0):
        # empty data fetched from ENTSOE. For now, make everything Nan
        for hour in range(24):
            hourlyElectricityData = [startDate+" "+str(hour).zfill(2)+":00"]
            for j in range(numSources):
                hourlyElectricityData.append(np.nan)
            electricityProductionData.append(hourlyElectricityData)
        datasetColumns = ["UTC time"]
        for source in electricitySources:
            datasetColumns.append(source)

        # print(electricityProductionData)
        dataset = pd.DataFrame(electricityProductionData, columns=datasetColumns)
        return dataset
    curDate = data[0]["period"]

    # checking if time starts from 00:00
    curHour = curDate.split("T")[1]
    for hour in range(int(curHour)):
        hourlyElectricityData = [curDate.split("T")[0]+" "+str(hour).zfill(2)+":00"]
        for j in range(numSources):
            hourlyElectricityData.append(np.nan)
        electricityProductionData.append(hourlyElectricityData)
    hourlyElectricityData = []
    hourlyElectricityData.append(curDate.split("T")[0]+" "+curHour.zfill(2)+":00")

    for electricitySourceData in data:
        if (electricitySourceData["period"] == curDate):
            electricityBySource[ENTSOE_SOURCE_MAP[electricitySourceData["fueltype"]]]= electricitySourceData["value"]
        else:
            curDate = electricitySourceData["period"]
            curHour = curDate.split("T")[1]
            for source in electricitySources:
                if (source not in electricityBySource.keys()):
                    electricityBySource[source] = np.nan
            for source in electricitySources:
                hourlyElectricityData.append(electricityBySource[source])
            electricityProductionData.append(hourlyElectricityData)
            # print(hourlyElectricityData)
            hourlyElectricityData = [curDate.split("T")[0]+" "+curHour.zfill(2)+":00"]
            electricityBySource[ENTSOE_SOURCE_MAP[electricitySourceData["fueltype"]]]= electricitySourceData["value"]
    for source in electricitySources:
        hourlyElectricityData.append(electricityBySource[source])
    electricityProductionData.append(hourlyElectricityData)

    # checking if time ends at 23:00
    for hour in range(int(curHour)+1, 24):
        hourlyElectricityData = [curDate.split("T")[0]+" "+str(hour).zfill(2)+":00"]
        for j in range(numSources):
            hourlyElectricityData.append(np.nan)
        electricityProductionData.append(hourlyElectricityData)

    datasetColumns = ["UTC time"]
    for source in electricitySources:
        datasetColumns.append(source)

    # print(electricityProductionData)
    dataset = pd.DataFrame(electricityProductionData, columns=datasetColumns)
    return dataset

def getElectricityProductionDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP):
    
    fullDataset = pd.DataFrame() # where to save the whole dataset
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d") # input date converted to yyyy-mm-dd format
    electricitySources = set() # for the loop
    numSources = 0 # for the loop

    print("start date:", startDate)


    for days in range(0, numDays, DAY_JUMP): # DAY_JUMP: # days of data got each time

        endDateObj = startDateObj + timedelta(days=DAY_JUMP-1)
        endDate = endDateObj.strftime("%Y-%m-%d")
        data = getProductionDataBySourceTypeDataFromENTSOE(balAuth, startDate, endDate)
                
        # if 1st day, add source to the list of sources & adjust number; FIX
        if (days == 0): # assuming all data is correctly available for the first day at least
            for electricitySourceData in data:
                electricitySources.add(ENTSOE_SOURCE_MAP[ENTSOE_SOURCES[colVal]])
                numSources = len(electricitySources)
        
        dataset = parseENTSOEProductionDataBySourceType(data, startDate, electricitySources, numSources)
        print(dataset)

        if (days == 0):
            fullDataset = dataset.copy()
        else:
            if (days%60 == 0):
                time.sleep(1)
            fullDataset = pd.concat([fullDataset, dataset])

        # startDate incremented    
        startDateObj = startDateObj + timedelta(days=DAY_JUMP)
        startDate = startDateObj.strftime("%Y-%m-%d")

        # print(fullDataset.tail(2))

    return fullDataset

def concatDataset():
    for balAuth in ENTSOE_BAL_AUTH_LIST:
        d1 = pd.read_csv("./eiaData/2019-2021/"+balAuth+".csv", header=0)
        d2 = pd.read_csv("./eiaData/2022/"+balAuth+".csv", header=0)
        fullDataset = pd.concat([d1, d2])
        fullDataset.to_csv("./eiaData/"+balAuth+".csv")
    return

def cleanElectricityProductionDataFromENTSOE(dataset, balAuth):
    dataset = dataset.astype(np.float64)
    dataset[dataset<0] = 0
    for i in range(len(dataset)):
        for j in range(len(dataset.columns)):
            if (pd.isna(dataset.iloc[i,j]) is True or dataset.iloc[i,j] == np.nan):
                prevHour = dataset.iloc[i-1, j] if (i-1)>=0 else np.nan
                prevDay = dataset.iloc[i-24, j] if (i-24)>=0 else np.nan
                nextHour = dataset.iloc[i+1, j] if (i+1)<len(dataset) else np.nan
                nextDay = dataset.iloc[i+24, j] if (i+24)<len(dataset) else np.nan
                numerator = 0
                denominator = 0
                if (pd.isna(prevHour) is False):
                    numerator += prevHour
                    denominator+=1
                if (pd.isna(prevDay) is False):
                    numerator += prevDay
                    denominator+=1
                if (pd.isna(nextHour) is False):
                    numerator += nextHour
                    denominator+=1
                if (pd.isna(nextDay) is False):
                    numerator += nextDay
                    denominator+=1
                dataset.iloc[i, j] = (numerator/denominator) if denominator>0 else 0
                # print(balAuth, dataset.index.values[i], prevHour, prevDay, nextHour, nextDay, dataset.iloc[i, j])
                # filling missing values by taking average of prevHour, prevDay same hour, 
                # nextHour & nextDay same hour

    print(balAuth)
    print(dataset.head())
    return dataset

def adjustColumns(dataset, balAuth):
    sources = ["coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "other"]
    modifiedSources = []
    print(dataset.shape)
    modifiedDataset = np.zeros(dataset.shape)
    idx = 0
    for source in sources:
        if (source in dataset.columns):
            modifiedSources.append(source)
            val = dataset[source].values
            modifiedDataset[:, idx] = val
            idx += 1
    modifiedDataset = pd.DataFrame(modifiedDataset, columns=modifiedSources, index=dataset.index)
    print(modifiedDataset.shape)
    return modifiedDataset

if __name__ == "__main__":
    if (len(sys.argv)!=3):
        print("Usage: python3 entsoeParser.py <yyyy-mm-dd> <# days to fetch data for>")
        exit(0)

    startDate = sys.argv[1] # "2022-01-01" #"2019-01-01"
    numDays = int(sys.argv[2]) #368 #1096

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        # fetch electricity data
        fullDataset = getElectricityProductionDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP=8)
        # DM: For DAY_JUMP > 1, there is a bug while filling missing hours

        # figure out how to save folders in data folder from src codes
        parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
        filedir = os.path.normpath(os.path.join(parentdir, f"./data/CHAE_DATA/{balAuth}"))
        
        csv_path = os.path.normpath(os.path.join(filedir, f"./{balAuth}.csv"))
        with open(csv_path, 'w') as f: # open as f means opens as file
            fullDataset.to_csv(f, index=False)
        
        # clean electricity data
        dataset = pd.read_csv(csv_path, header=0, 
                            parse_dates=["UTC time"], index_col=["UTC time"])
        cleanedDataset = cleanElectricityProductionDataFromENTSOE(dataset, balAuth)
        cleanedDataset.to_csv(os.path.normpath(os.path.join(filedir, f"{balAuth}_clean.csv"))) # see if string suffices

        # adjust source columns
        dataset = pd.read_csv(filedir+f"/{balAuth}_clean.csv", header=0, index_col=["UTC time"])
        modifiedDataset = adjustColumns(dataset, balAuth)
        modifiedDataset.to_csv(filedir+f"./{balAuth}_clean_mod.csv")

    # concatDataset()
