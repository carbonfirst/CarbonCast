import os
import pandas as pd
from entsoe import EntsoePandasClient
from datetime import datetime, timedelta
import time
import numpy as np
import sys

# public key for ENTSOE API
ENTSOE_API_KEY="c0b15cbf-634c-4884-b784-5b463182cc97"

# ENTSOE_BAL_AUTH_LIST = ['AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']
ENTSOE_BAL_AUTH_LIST =  ['FR']
# ENTSOE_BAL_AUTH_LIST = ['DK', 'DE', 'FR', 'RO']
INVALID_AUTH_LIST = ['AL', 'DK-DK2']

# get production data by source type from ENTSOE API
def getProductionDataBySourceTypeDataFromENTSOE(ba, curDate, curEndDate):
    print(ba)

    startDate = pd.Timestamp(curDate, tz='UTC')
    endDate = pd.Timestamp(curEndDate, tz='UTC') + pd.Timedelta(hours=23, minutes=45)
    print(startDate, endDate)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    try:
        dataset = client.query_generation(ba, start=startDate, end=endDate, psr_type=None)
        empty = False
    except: # mark if data was empty
        dataset = None
        empty = True

    return dataset, empty

# parse production data by source type from ENTSOE API
def parseENTSOEProductionDataBySourceType(data):  
    dataset = pd.DataFrame()
    timerows = []
    for column in data: # iterate through the columns
        if (type(column) is tuple):
            source = column[0]
        else:
            source = column
        if (source == "Hydro Pumped Storage"):
            continue # Ignoring storage for now
        if (source in dataset.columns): # fix; find out how to keep nan values
            # dataset[source] = dataset[source].fillna(0) + data[column].fillna(0)
            for row in range(len(data.index)):
                firstNaN = pd.isna(dataset[source].iloc[row])
                secondNaN = pd.isna(data[column].iloc[row])
                if (firstNaN and secondNaN):
                    dataset[source].iloc[row] = np.nan
                else:
                    firstVal = 0 if firstNaN else dataset[source].iloc[row]
                    secondVal = 0 if secondNaN else data[column].iloc[row]
                    dataset[source].iloc[row] = firstVal + secondVal
        else:
            dataset.insert(loc=len(dataset.columns), column=source, value=data[column])
    # converting time to UTC time & appending as 1st column
    for time in data.index:
        timerows.append(time.astimezone(tz='UTC'))
    dataset.insert(loc=0, column="UTC Time", value=timerows)
    return dataset

def getElectricityProductionDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP):
    fullDataset = pd.DataFrame()
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")

    for days in range(0, numDays, DAY_JUMP): # DAY_JUMP: # days of data got each time
        endDateObj = startDateObj + timedelta(days=DAY_JUMP-1)
        endDate = endDateObj.strftime("%Y-%m-%d")
        data, empty = getProductionDataBySourceTypeDataFromENTSOE(balAuth, startDate, endDate)
        print("was the dataset empty?: ", empty)

        if (empty):
            continue # skip this iteration
        dataset = parseENTSOEProductionDataBySourceType(data)
        
        if (days == 0):
            fullDataset = dataset.copy()
        else:
            if (days%60 == 0):
                time.sleep(1)
            fullDataset = pd.concat([fullDataset, dataset], sort=False) # if doesn't work for new columns, fix here

        # startDate incremented    
        startDateObj = startDateObj + timedelta(days=DAY_JUMP)
        startDate = startDateObj.strftime("%Y-%m-%d")

    return fullDataset




# for FORECAST raw data

# get forecast data by source type from ENTSOE API
def getForecastDataBySourceTypeDataFromENTSOE(ba, curDate, curEndDate):
    print(ba)

    startDate = pd.Timestamp(curDate, tz='UTC')
    endDate = pd.Timestamp(curEndDate, tz='UTC') + pd.Timedelta(hours=23, minutes=45)
    print(startDate, endDate)

    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
    try:
        dataset = client.query_wind_and_solar_forecast(ba, start=startDate, end=endDate, psr_type=None)
        empty = False
    except: # mark if data was empty
        dataset = None
        empty = True

    return dataset, empty

# parse forecast data by source type from ENTSOE API
def parseENTSOEForecastDataBySourceType(data):  
    dataset = pd.DataFrame()
    timerows = []
    for column in data: # iterate through the columns
        if (type(column) is tuple):
            source = column[0]
        else:
            source = column
        if (source in dataset.columns): # fix; find out how to keep nan values
            print("there is a duplicate for source ", source)
            exit()
        dataset.insert(loc=len(dataset.columns), column=source, value=data[column], allow_duplicates=True)
    # converting time to UTC time & appending as 1st column
    for time in data.index:
        timerows.append(time.astimezone(tz='UTC'))
    dataset.insert(loc=0, column="UTC Time", value=timerows)
    return dataset

def getElectricityForecastDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP):
    fullDataset = pd.DataFrame()
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")

    for days in range(0, numDays, DAY_JUMP): # DAY_JUMP: # days of data got each time
        endDateObj = startDateObj + timedelta(days=DAY_JUMP-1)
        endDate = endDateObj.strftime("%Y-%m-%d")
        data, empty = getForecastDataBySourceTypeDataFromENTSOE(balAuth, startDate, endDate)
        print("was the dataset empty?: ", empty)

        if (empty):
            continue # skip this iteration
        dataset = parseENTSOEForecastDataBySourceType(data)
        
        if (days == 0):
            fullDataset = dataset.copy()
        else:
            if (days%60 == 0):
                time.sleep(1)
            fullDataset = pd.concat([fullDataset, dataset], sort=False) # if doesn't work for new columns, fix here

        # startDate incremented    
        startDateObj = startDateObj + timedelta(days=DAY_JUMP)
        startDate = startDateObj.strftime("%Y-%m-%d")

    return fullDataset



if __name__ == "__main__":
    if (len(sys.argv)!=3):
        print("Usage: python3 entsoeParser.py <yyyy-mm-dd> <# days to fetch data for>")
        exit(0)
    startDate = sys.argv[1] # "2022-01-01" #"2019-01-01"
    numDays = int(sys.argv[2]) #368 #1096

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        fullProductionDataset = getElectricityProductionDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP=8)
        # fullForecastDataset = getElectricityForecastDataFromENTSOE(balAuth, startDate, numDays, DAY_JUMP=8)

        parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
        filedir = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/ENTSOE"))
        
        csv_path = os.path.normpath(os.path.join(filedir, f"./{balAuth}_raw_production.csv"))
        with open(csv_path, 'w') as f: # open as f means opens as file
            fullProductionDataset.to_csv(f, index=False)

        # csv_path = os.path.normpath(os.path.join(filedir, f"./{balAuth}_raw_forecast.csv"))
        # with open(csv_path, 'w') as f: # open as f means opens as file
        #     fullForecastDataset.to_csv(f, index=False)

        print("raw data parsed for " + balAuth)