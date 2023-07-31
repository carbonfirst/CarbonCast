import os
import shutil

ENTSOE_BAL_AUTH_LIST = ['AL'] # EXCLUDE RO
# ENTSOE_BAL_AUTH_LIST = ['AL', 'AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'DK-DK2', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']

if __name__ == "__main__":

    parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
    
    for balAuth in ENTSOE_BAL_AUTH_LIST:

        # parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
        # destination = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}"))

        # newDestination = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/ENTSOE"))

        # allfiles = os.listdir(destination)
        # os.mkdir(newDestination)

        # # iterate on all files to move them to destination folder
        # for f in allfiles:
        #     src_path = os.path.join(destination, f)
        #     dst_path = os.path.join(newDestination, f)
        #     os.rename(src_path, dst_path)

        # folder1 = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/fuel_forecast"))
        # folder2 = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/weather_data"))

        # os.mkdir(folder1)
        # os.mkdir(folder2)



        # 1) creating 3 folders
        newFolder = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/solar_wind_forecasts"))
        os.mkdir(newFolder)

        # 2) copying & pasting region_clean.csv files
        originalRegionClean = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_clean_mod.csv"))
        destinationRegionClean = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}"))
        oldName = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/{balAuth}_clean_mod.csv"))
        newName = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/{balAuth}_clean.csv"))
        shutil.copy2(originalRegionClean, newName)        
        # shutil.copy2(originalRegionClean, destinationRegionClean)
        # os.rename(oldName, newName)

        # 4) moving files from EU_FINAL_WEATHER_DATA into individual folders
        aggregatedFile = os.path.normpath(os.path.join(os.getcwd(), f"./EU_final_weather_data/{balAuth}_aggregated_weather_data.csv"))
        weatherFile = os.path.normpath(os.path.join(os.getcwd(), f"./EU_final_weather_data/{balAuth}_weather_forecast.csv"))
        destination = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}"))
        shutil.move(aggregatedFile, destination)
        shutil.move(weatherFile, destination)

        aggrStart = os.path.normpath(os.path.join(destination, f"./{balAuth}_aggregated_weather_data.csv"))
        aggrDestination = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/weather_data"))
        shutil.copy2(aggrStart, aggrDestination)

        # 5) copying and pasting forecasts into solar_wind_forecasts
        forecastStart = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/ENTSOE/{balAuth}_SW_clean_mod.csv"))
        forecastDestination = os.path.normpath(os.path.join(parentdir, f"./data/EU_DATA/{balAuth}/solar_wind_forecasts/{balAuth}_solar_wind_forecast.csv"))
        shutil.copy2(forecastStart, forecastDestination)
        # os.rename(forecastDestination, newForecastName)

