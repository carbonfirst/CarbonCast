import numpy as np
import pandas as pd
import pytz as pytz
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
import sys
import os 

US_REGIONS = ["AECI","AZPS","BPAT","CISO","DUK","EPE","ERCO","FPC","FPL",
             "GRID","IPCO","ISNE","LDWP","MISO","NEVP","NWMT","NYIS","PACE",
            "PACW","PJM","PSCO","PSEI","SC","SCEG","SOCO","SPA","SRP","SWPP",
             "TIDC","TVA","WACM","WALC"]

#US_REGIONS = ["SRP"] # test region 

FILES = ["clean.csv", "direct_emissions.csv", "lifecycle_emissions.csv",
                  "96hr_forecasts_DA.csv", "direct_96hr_CI_forecasts_0.csv", 
                  "lifecycle_96hr_CI_forecasts_0.csv"]

def getDailyFilesFromDataFile(folder,region_name,file_name):
    dataset = pd.read_csv(f"../{folder}/{region_name}/{file_name}", header = 0)
    outputFileDir = f"../data/{region_name}/daily"
    #check if files is here or not 
    if not os.path.exists(outputFileDir):
        os.makedirs(outputFileDir)
    else: 
        print(f"Directory was already created ")
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
        subset = dataset.iloc[start:end]
        curDate = pd.to_datetime(dataset[index].values[i]).strftime('%Y-%m-%d')
        print(curDate)
        # print(subset)
        if file_name == f"{region_name}_clean.csv":
            output_file_name = f"{region_name}_{curDate}.csv"
        elif file_name.endswith("_direct_emissions.csv"):
            output_file_name = f"{region_name}_{curDate}_direct_emissions.csv"
        elif file_name.endswith("_lifecycle_emissions.csv"):
            output_file_name = f"{region_name}_{curDate}_lifecycle_emissions.csv"
        elif file_name.endswith("_96hr_forecasts_DA.csv"):
            output_file_name = f"{region_name}_96hr_forecasts_{curDate}.csv"
        elif file_name.endswith("_direct_96hr_CI_forecasts_0.csv"):
            output_file_name = f"{region_name}_direct_CI_forecasts_{curDate}.csv"
        else:
            output_file_name = f"{region_name}_lifecycle_CI_forecasts_{curDate}.csv"
        subset.to_csv(f"{outputFileDir}/{output_file_name}", index=False)

    return

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