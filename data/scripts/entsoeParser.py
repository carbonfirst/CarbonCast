import os
import pandas as pd
from entsoe import EntsoePandasClient

ENTSOE_API_KEY="c0b15cbf-634c-4884-b784-5b463182cc97"

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

ENTSOE_REGIONS = ['DE', 'NL', 'ES', 'SE', 'PL']

startTime = pd.Timestamp('20230309', tz='UTC')
endTime = pd.Timestamp('20230310', tz='UTC')

def getProductionDataBySourceTypeDataFromENTSOE(region):
    client = EntsoePandasClient(api_key=ENTSOE_API_KEY)

    countryCode = region  
    print(startTime, endTime, region)
    
    dataset = client.query_generation(countryCode, start=startTime,end=endTime, psr_type=None)
    return dataset, startTime

def parseENTSOEProductionDataBySourceType(data):
    datasetColumns = []
    datasetColumns.append("UTC time")
    sources = set()
    for i in range(len(data.columns.values)):
        colVal = data.columns.values[i]
        if (type(colVal) is tuple):
            colVal = colVal[0]
        sourceKey = ENTSOE_SOURCES[colVal]
        if (sourceKey == "STOR"):
            continue # Ignoring storage for now
        source = ENTSOE_SOURCE_MAP[sourceKey]
        sources.add(source)
    sources = list(sources)
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

    for region in ENTSOE_REGIONS:
        script_dir = os.path.abspath('.')
        csv_path = os.path.join(script_dir, f"../{region}/day/{str(startTime)[:10]}.csv")
        data, startTime = getProductionDataBySourceTypeDataFromENTSOE(region)
        dataset, numSources = parseENTSOEProductionDataBySourceType(data)
        with open(csv_path, 'w') as f:
            dataset.to_csv(f, index=False)
