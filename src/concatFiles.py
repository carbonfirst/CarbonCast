# Import the required libraries 
import os
import pandas as pd
from datetime import date
import shutil

ENTSOE_BAL_AUTH_LIST = ['AT', 'BA', 'BE', 'BG', 'HR', 'CZ', 'CY', 'DE', 'DK', 'EE', 'FI', 
                        'FR', 'GE', 'DE', 'GR', 'HU', 'IE', 'IT', 'XK', 'LV', 'LT', 'LU', 'MD', 'ME', 'NL',
                       'MK', 'NO', 'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH', 'UA', 'UK']

# Create backup for references purpose 
def create_backup(src_file_name, dst_dir):
    try:
        # Source and destination file paths
        src_file_path = src_file_name
        dst_file_name =   "backup_" + os.path.basename(src_file_name)
        dst_file_path = os.path.join(dst_dir, dst_file_name)
        
        # Create destination directory if it doesn't exist
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        # Copy the file from source to destination 
        shutil.copy2(src_file_path, dst_file_path)
        print('Backup Successful!')
    except FileNotFoundError:
        print("File does not exist! Please provide the complete path")
    except PermissionError: 
        shutil.copytree(src_file_path, dst_file_path)
    print('Backup of directory is successful!')

# Process the data by concating 
def concatDataset(old_file,new_file):
    # Load the data into DataFrames
    for balAuth in ENTSOE_BAL_AUTH_LIST: 
        df1 = pd.read_csv(old_file,header=0)
        df2 = pd.read_csv(new_file,header=0)
        #print(df1.head()) check that its working
        #print(df2.head())

        #concat the 2 df and drop duplicates values 
        final_df = pd.concat([df1, df2])
        final_df.sort_values(by = 'UTC time', inplace=True)
        final_df.drop_duplicates(subset=['UTC time'], keep='last',inplace=True)
        concat_path = os.path.join(fuel_dir, f"{balAuth}_clean.csv")
        final_df.to_csv(concat_path, index=False)

if __name__ == "__main__":

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        
     parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
     fuel_dir = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/fuel_forecast"))
     entsoe_dir = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/ENTSOE"))
     
     old_csv_path = os.path.normpath(os.path.join(fuel_dir, f"{balAuth}_clean.csv"))
     new_csv_path = os.path.normpath(os.path.join(entsoe_dir, f"{balAuth}_clean_mod.csv"))

     create_backup(old_csv_path,f"./data/EU_DATA/{balAuth}/fuel_forecast/")
     final_df = concatDataset(old_csv_path,new_csv_path) 
     #final_df.to_csv(fuel_dir+f"/{balAuth}_clean_mod.csv")
