import os
import requests
import pandas as pd

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
EIA_BAL_AUTH_LIST = [ 'CISO', 'FPL', 'ISNE', 'NYIS', 'PJM', 'ERCO', 'BPAT']


# get production data by source type from EIA API
def getProductionDataBySourceTypeDataFromEIA(ba):
    print(ba)
    API_URL="https://api.eia.gov/v2/electricity/rto/fuel-type-data/data?api_key="
    API_URL_SORT_PARAMS="sort[0][column]=period&sort[0][direction]=asc&sort[1][column]=fueltype&sort[1][direction]=desc"
    API_URL_SUFFIX="&frequency=hourly&data[]=value&facets[respondent][]={}&"+API_URL_SORT_PARAMS+"&start={}&end={}&offset=0&length=5000"
    startTime = "2023-03-01T00"
    endTime = "2023-03-01T23"
    URL = API_URL+EIA_API_KEY+API_URL_SUFFIX.format(ba, startTime, endTime)
    resp = requests.get(URL)
    print(resp.url)
    if (resp.status_code != 200):
        print("Error! Code: ", resp.status_code)
        print("Error! Message: ", resp.text)
        print("Error! Reason: ", resp.reason)
    responseData = resp.json()["response"]["data"]
    return responseData, startTime

# parse production data by source type from EIA API
def parseEIAProductionDataBySourceType(data, startTime):
    datasetColumns = []
    datasetColumns.append("UTC time")
    numSources = 0
    electricityBySource = []
    electricityProductionData = []
    electricityBySource.append(startTime)

    for electricitySourceData in data:
        if (electricitySourceData["period"] == startTime):
            numSources += 1
            datasetColumns.append(EIA_SOURCE_MAP[electricitySourceData["fueltype"]])
            electricityBySource.append(electricitySourceData["value"])
        else:
            if len(electricityBySource) == numSources + 1:
                electricityProductionData.append(electricityBySource)
                electricityBySource = [electricitySourceData["period"]]
            electricityBySource.append(electricitySourceData["value"])
    electricityProductionData.append(electricityBySource)

    dataset = pd.DataFrame(electricityProductionData, columns=datasetColumns)
    return dataset, numSources

if __name__ == "__main__":
    for balAuth in EIA_BAL_AUTH_LIST:
        data, startTime = getProductionDataBySourceTypeDataFromEIA(balAuth)
        dataset, numSources = parseEIAProductionDataBySourceType(data, startTime)
        script_dir = os.path.abspath('.')
        csv_path = os.path.join(script_dir, f"data/{balAuth}/day/{startTime[:-3]}.csv")
        with open(csv_path, 'w') as f:
            dataset.to_csv(f, index=False)
