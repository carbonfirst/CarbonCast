#Copy from concatFiles 
# Import the required libraries 
import os
import pandas as pd
from datetime import date
import shutil

#ENTSOE_BAL_AUTH_LIST = ['AT', 'BA', 'BE', 'BG', 'HR', 'CZ', 'CY', 'DE', 'DK', 'EE', 'FI', 
#                        'FR', 'GE', 'DE', 'GR', 'HU', 'IE', 'IT', 'XK', 'LV', 'LT', 'LU', 'MD', 'ME', 'NL',
#                       'MK', 'NO', 'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH', 'UA', 'UK']

ENTSOE_BAL_AUTH_LIST = ['DE']

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
        #print(df1.head(100)) #check that its working
        #print(df2.head())

        #drop duplicates for the last row, not the new
        #concat the 2 df and drop duplicates values 
        final_df = pd.concat([df1, df2],ignore_index=True)
        print(final_df)

        #final_df.drop_duplicates(subset=['datetime'], keep='last',inplace=True)
        concat_path = os.path.join(concat_dir, f"{balAuth}_aggregated_weather_data_2023.csv")
        final_df.to_csv(concat_path, index=False)

if __name__ == "__main__":

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        
     parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
     ori_dir = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/weather_data"))
     new_dir = os.path.normpath(os.path.join(parentdir, f"./data/EU_weather_data_2023_Jan_Dec"))
     concat_dir =os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}"))
    
     old_csv_path = os.path.normpath(os.path.join(ori_dir, f"{balAuth}_aggregated_weather_data.csv"))
     new_csv_path = os.path.normpath(os.path.join(new_dir, f"{balAuth}_aggregated_weather_data_2023.csv"))

     create_backup(old_csv_path,f"./data/EU_DATA/{balAuth}/fuel_forecast/")
     final_df = concatDataset(old_csv_path,new_csv_path) 
     #final_df.to_csv(fuel_dir+f"/{balAuth}_clean_mod.csv")
