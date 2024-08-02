import numpy as np
import pandas as pd
import pytz as pytz
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
import sys
import os 

#US_REGIONS = ["AECI","AZPS","BPAT","CISO","DUK","EPE","ERCO","FPC","FPL",
#             "GRID","IPCO","ISNE","LDWP","MISO","NEVP","NWMT","NYIS","PACE",
#            "PACW","PJM","PSCO","PSEI","SC","SCEG","SOCO","SPA","SRP","SWPP",
#             "TIDC","TVA","WACM","WALC"]

US_REGIONS = ["PACW"] #"FPC","GRID","PSEI","WALC",

FILES = [
    "clean.csv", 
    "direct_emissions.csv", 
    "lifecycle_emissions.csv",
    "96hr_forecasts_DA.csv",
    "direct_96hr_CI_forecasts_0.csv",
    "direct_96hr_CI_forecasts_0PERIOD_0.csv",
    "direct_96hr_CI_forecasts_0PERIOD_1.csv",
    "direct_96hr_CI_forecasts_0PERIOD_2.csv",
    "lifecycle_96hr_CI_forecasts_0.csv",
    "lifecycle_96hr_CI_forecasts_0PERIOD_0.csv",
    "lifecycle_96hr_CI_forecasts_0PERIOD_1.csv",
    "lifecycle_96hr_CI_forecasts_0PERIOD_2.csv"
]

def getDailyFilesFromDataFile(folder,region_name,file_name):
    dataset = pd.read_csv(f"../{folder}/{region_name}/{file_name}", header = 0)
    outputFileDir = f"../data/{region_name}/daily"
    #check if files is here or not 
    if not os.path.exists(outputFileDir):
        os.makedirs(outputFileDir)
    else: 
        print(f"Directory was already created ")

    version = ["3.1"]*96
    creationTime = ["2024-07-17 00:00:00"]*96

    version_2 = ["3.1"]*24
    creationTime_2 = ["2024-07-17 00:00:00"]*24

    if file_name == f"{region_name}_clean.csv" or file_name == f"{region_name}_direct_emissions.csv" or file_name == f"{region_name}_lifecycle_emissions.csv":
        numRows = 24
        start = 35064
        index = 'UTC time'
    elif file_name == f"{region_name}_96hr_forecasts_DA.csv": 
        numRows = 96
        start = 105216
        index = 'datetime'
    else: 
        numRows = 96
        start = 0
        index = 'datetime'
    for i in range(start, len(dataset), numRows): #change start index to when 2023 starts for EU and US (or the latest year)
        start = i
        end = min(i+numRows, len(dataset))
        subset = dataset.iloc[start:end].copy()
        subset.rename(columns={"datetime": "UTC time"}, inplace=True)
        curDate = pd.to_datetime(dataset[index].values[i]).strftime('%Y-%m-%d')
        print(curDate)
        # print(subset)
        if file_name == f"{region_name}_clean.csv":
            output_file_name = f"{region_name}_{curDate}.csv"
        elif file_name.endswith("_direct_emissions.csv"):
            subset = fillInconsistentData(curDate,subset,24)   
            subset.insert(2, "creation_time (UTC)", creationTime_2)
            subset.insert(3, "version", version_2)
            output_file_name = f"{region_name}_{curDate}_direct_emissions.csv"
        elif file_name.endswith("_lifecycle_emissions.csv"):
            subset = fillInconsistentData(curDate,subset,24)            
            subset.insert(2, "creation_time (UTC)", creationTime_2)
            subset.insert(3, "version", version_2)
            output_file_name = f"{region_name}_{curDate}_lifecycle_emissions.csv"
        elif file_name.endswith("_96hr_forecasts_DA.csv"):
            subset = fillInconsistentData(curDate,subset,96)            
            subset.insert(1, "creation_time (UTC)", creationTime)
            subset.insert(2, "version", version)
            output_file_name = f"{region_name}_96hr_forecasts_{curDate}.csv"
        elif file_name.endswith(("_direct_96hr_CI_forecasts_0PERIOD_0.csv","_direct_96hr_CI_forecasts_0PERIOD_1.csv","_direct_96hr_CI_forecasts_0PERIOD_2.csv")):
            subset = fillInconsistentData(curDate,subset,96)            
            subset.insert(1, "creation_time (UTC)", creationTime)
            subset.insert(2, "version", version)
            output_file_name = f"{region_name}_direct_CI_forecasts_{curDate}.csv"
        else:
            subset = fillInconsistentData(curDate,subset,96)            
            subset.insert(1, "creation_time (UTC)", creationTime)
            subset.insert(2, "version", version)
            output_file_name = f"{region_name}_lifecycle_CI_forecasts_{curDate}.csv"
        subset.to_csv(f"{outputFileDir}/{output_file_name}", index=False)

    return

def fillInconsistentData(curDate, subset, period):
    original_col = subset.columns.tolist()
    subset['UTC time'] = pd.to_datetime(subset['UTC time'])
    subset.set_index('UTC time', inplace=True)
    subset = subset[~subset.index.duplicated(keep='first')]

    expected_hours = pd.date_range(start=curDate, periods=period, freq='h')
    subset = subset.reindex(expected_hours)
    avg_values = subset.mean()

    for col in subset.columns:
        if subset[col].isna().any():
            subset[col].fillna(avg_values[col])

    subset_hours = subset.index.to_series().dt.strftime('%H:%M:%S')
    missing_hours = set(expected_hours.strftime('%H:%M:%S')) - set(subset_hours)

    if missing_hours:
        print(f"Date {curDate} is missing times: {sorted(missing_hours)}")
        if not subset.empty:
            avg_value = subset.mean()
        for hour in sorted(missing_hours):
            missing_time = pd.to_datetime(f'{curDate} {hour}')
            subset.loc[missing_time] = avg_value

    subset = subset.reindex(expected_hours)
    subset.reset_index(inplace=True)
    subset.rename(columns={'index': 'UTC time'}, inplace=True)  
    subset = subset[original_col]

    return subset


if __name__ == "__main__":
   # if len(sys.argv) < 5:
    #    print("Usage: python3 dailyFetcher.py <source> <region_name> <file_name> ")
    #    sys.exit(1)

    #folder = sys.argv[1] #data
    #source = sys.argv[2] # EU_DATA
    #region_name = sys.argv[3] #DE
    #file_name = sys.argv[4] #clean_csv

    for region_name in US_REGIONS:
        for file in FILES: 
            file_name = f"{region_name}_{file}"
            if file in ["clean.csv", "direct_emissions.csv", "lifecycle_emissions.csv", "96hr_forecasts_DA.csv"]:
                folder = "data"
            else:
                folder = "CI_forecast_data"
            file_path = f"../{folder}/{region_name}/{file_name}"
            if os.path.exists(file_path):
                print(f"Processing region: {region_name}, file: {file_name}")
                getDailyFilesFromDataFile(folder, region_name, file_name)
            else:
                print(f"File {file_path} not found for region {region_name}")            