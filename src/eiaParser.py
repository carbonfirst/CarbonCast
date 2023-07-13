import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import sys
import numpy as np

# public key for EIA API
EIA_API_KEY="CZdQsisRJzwOfqUWV3jiMPNEx3ZbHcuJ2VQus04i"

# map EIA fuel types to source types
EIA_SOURCE_MAP = {
    "OTH": "other", 
    "COL": "coal",
    "SUN": "solar",
    "NG": "nat_gas",
    "NUC": "nuclear",
    "WND": "wind",
    "WAT": "hydro",
    "OIL": "oil"
    }

# list of balancing authorities to get data for
# EIA_BAL_AUTH_LIST = ["CISO", "PJM", "ERCO", "ISNE", "MISO", "SWPP", "SOCO", "BPAT", "FPL", "NYIS", "BANC", "LDWP", 
#                      "TIDC", "DUK", "SC", "SCEG", "SPA", "FMPP", "FPC", "TAL", "TEC", "AECI", "LGEE", "DOPD",
#                      "GCPD", "GRID", "IPCO", "NEVP", "NWMT", "PACE", "PACW", "PGE", "PSCO", "PSEI", "SCL", 
#                      "TPWR", "WACM", "SOCO", "AZPS", "EPE", "PNM", "SRP", "TEPC", "WALC", "TVA"]

EIA_BAL_AUTH_LIST = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCOT", "FPC", 
                "FPL", "GRID", "IPCO", "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYISO", 
                "PACE", "PACW", "PJM", "PSCO", "PSEI", "SC", "SCEG", "SOCO", "SPA", "SRP", 
                "SWPP", "TIDC", "TVA", "WACM", "WALC"]

# get production data by source type from EIA API
def getProductionDataBySourceTypeDataFromEIA(ba, curDate, curEndDate):
    print(ba)
    API_URL="https://api.eia.gov/v2/electricity/rto/fuel-type-data/data?api_key="
    API_URL_SORT_PARAMS="sort[0][column]=period&sort[0][direction]=asc&sort[1][column]=fueltype&sort[1][direction]=desc"
    API_URL_SUFFIX="&frequency=hourly&data[]=value&facets[respondent][]={}&"+API_URL_SORT_PARAMS+"&start={}&end={}&offset=0&length=5000"

    startDate = curDate+"T00"
    endDate = curEndDate+"T23"
    print(startDate, endDate)
    URL = API_URL+EIA_API_KEY+API_URL_SUFFIX.format(ba, startDate, endDate)
    resp = requests.get(URL)
    print(resp.url)
    if (resp.status_code != 200):
        print("Error! Code: ", resp.status_code)
        print("Error! Message: ", resp.text)
        print("Error! Reason: ", resp.reason)
    responseData = resp.json()["response"]["data"]
    return responseData

# parse production data by source type from EIA API
def parseEIAProductionDataBySourceType(data, startDate, electricitySources, numSources):
    electricityBySource = {}
    hourlyElectricityData = []
    electricityProductionData = []
    # startDate = startDate + " 00:00"
    # electricityBySource.append(startDate)
    # dateObj = datetime.strptime(startDate, "%Y-%m-%d %H:%M")
    if (len(data) == 0):
        # empty data fetched from EIA. For now, make everything Nan
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
            electricityBySource[EIA_SOURCE_MAP[electricitySourceData["fueltype"]]]= electricitySourceData["value"]
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
            electricityBySource[EIA_SOURCE_MAP[electricitySourceData["fueltype"]]]= electricitySourceData["value"]
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

def getELectricityProductionDataFromEIA(balAuth, startDate, numDays, DAY_JUMP):
    # DM: For DAY_JUMP > 1, there is a bug while filling missing hours
    fullDataset = pd.DataFrame()
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    electricitySources = set()
    numSources = 0
    for days in range(0, numDays, DAY_JUMP):
        endDateObj = startDateObj + timedelta(days=DAY_JUMP-1)
        endDate = endDateObj.strftime("%Y-%m-%d")
        data = getProductionDataBySourceTypeDataFromEIA(balAuth, startDate, endDate)
        if (days == 0): # assuming all data is correctly available for the first day at least
            for electricitySourceData in data:
                electricitySources.add(EIA_SOURCE_MAP[electricitySourceData["fueltype"]])
                numSources = len(electricitySources)
        dataset = parseEIAProductionDataBySourceType(data, startDate, electricitySources, numSources)
        print(dataset)
        if (days == 0):
            fullDataset = dataset.copy()
        else:
            if (days%60 == 0):
                time.sleep(1)
            fullDataset = pd.concat([fullDataset, dataset])
        startDateObj = startDateObj + timedelta(days=DAY_JUMP)
        startDate = startDateObj.strftime("%Y-%m-%d")
        # print(fullDataset.tail(2))

    return fullDataset

def concatDataset():
    for balAuth in EIA_BAL_AUTH_LIST:
        d1 = pd.read_csv("./eiaData/2019-2021/"+balAuth+".csv", header=0)
        d2 = pd.read_csv("./eiaData/2022/"+balAuth+".csv", header=0)
        fullDataset = pd.concat([d1, d2])
        fullDataset.to_csv("./eiaData/"+balAuth+".csv")
    return

def cleanElectricityProductionDataFromEIA(dataset, balAuth):
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
        print("Usage: python3 eiaParser.py <yyyy-mm-dd> <# days to fetch data for>")
        exit(0)

    startDate = sys.argv[1] # "2022-01-01" #"2019-01-01"
    numDays = int(sys.argv[2]) #368 #1096

    # chae note: fixed the directories; might not work linux, etc? might have to os.path methods to create paths instead of strings +
    for balAuth in EIA_BAL_AUTH_LIST:
        # fetch electricity data
        fullDataset = getELectricityProductionDataFromEIA(balAuth, startDate, numDays, DAY_JUMP=8)
        # DM: For DAY_JUMP > 1, there is a bug while filling missing hours
        parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
        filedir = os.path.normpath(os.path.join(parentdir, f"./data/{balAuth}"))
        #csv_path = os.path.normpath(os.path.join(filedir, f"./{balAuth}.csv"))
        with open(filedir+f"/{balAuth}.csv", 'w') as f:
            fullDataset.to_csv(f, index=False)
        
        # clean electricity data
        dataset = pd.read_csv(filedir+f"/{balAuth}.csv", header=0, 
                            parse_dates=["UTC time"], index_col=["UTC time"])
        cleanedDataset = cleanElectricityProductionDataFromEIA(dataset, balAuth)
        cleanedDataset.to_csv(filedir+f"/{balAuth}_clean.csv")

        # adjust source columns
        dataset = pd.read_csv(filedir+"/"+balAuth+"_clean.csv", header=0, index_col=["UTC time"])
        modifiedDataset = adjustColumns(dataset, balAuth)
        modifiedDataset.to_csv(filedir+f"/{balAuth}_clean_mod.csv")

        # # fetch electricity data
        # fullDataset = getELectricityProductionDataFromEIA(balAuth, startDate, numDays, DAY_JUMP=8)
        # # DM: For DAY_JUMP > 1, there is a bug while filling missing hours
        # parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
        # filedir = os.path.normpath(os.path.join(parentdir, f"./data/{balAuth}"))
        # csv_path = os.path.normpath(os.path.join(filedir, f"./{balAuth}.csv"))
        # with open(csv_path, 'w') as f:
        #     fullDataset.to_csv(f, index=False)
        
        # # clean electricity data
        # dataset = pd.read_csv(csv_path, header=0, 
        #                     parse_dates=["UTC time"], index_col=["UTC time"])
        # cleanedDataset = cleanElectricityProductionDataFromEIA(dataset, balAuth)
        # cleanedDataset.to_csv(filedir+"/"+balAuth+"_clean.csv")

        # # adjust source columns
        # dataset = pd.read_csv(filedir+"/"+balAuth+"_clean.csv", header=0, index_col=["UTC time"])
        # modifiedDataset = adjustColumns(dataset, balAuth)
        # newPath = os.path.normpath(os.path.join(filedir, f"./{balAuth}_clean_mod.csv"))
        # modifiedDataset.to_csv(newPath)
        

    # concatDataset()
