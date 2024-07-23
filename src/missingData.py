import numpy as np
import pandas as pd
import pytz as pytz
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
import sys
import os 

MISSING_US_REGIONS = ["PJM","SC"] #"FPC","GRID","PSEI","WALC",

FLAWED_US_REGIONS = ["FPC","GRID","PSEI","WALC"]

FILES = [
    "source_prod_clean.csv"
]

def fixFlawData(folder,region_name,file_name):
    inputFileDir = f"../{folder}/{region_name}/fuel_forecast/{file_name}"
    outputFileDir = f"../data/{region_name}/fuel_forecast"
    output_file_name = f"{region_name}_source_prod_clean.csv"
    outputFilePath = f"{outputFileDir}/{output_file_name}"

    #check if files is here or not 
    if not os.path.exists(inputFileDir):
        print(f"Input file {inputFileDir} does not exist.")
        return
    
    if not os.path.exists(outputFileDir):
        os.makedirs(outputFileDir)
    else: 
        print(f"Directory was already created ")
    
    dataset = pd.read_csv(inputFileDir, header=0)
    dataset.fillna(0, inplace=True)
    dataset.to_csv(outputFilePath, index=False)

    return 





if __name__ == "__main__":
   # if len(sys.argv) < 5:
    #    print("Usage: python3 dailyFetcher.py <source> <region_name> <file_name> ")
    #    sys.exit(1)

    #folder = sys.argv[1] #data
    #source = sys.argv[2] # EU_DATA
    #region_name = sys.argv[3] #DE
    #file_name = sys.argv[4] #clean_csv

    folder = "data"
    for region_name in FLAWED_US_REGIONS:
        for file in FILES: 
            file_name = f"{region_name}_{file}"
            file_path = f"../{folder}/{region_name}/fuel_forecast/{file_name}"
            if os.path.exists(file_path):
                print(f"Processing region: {region_name}, file: {file_name}")
                fixFlawData(folder, region_name, file_name)
            else:
                print(f"File {file_path} not found for region {region_name}")           