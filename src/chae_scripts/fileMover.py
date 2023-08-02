import os
import shutil

ENTSOE_BAL_AUTH_LIST = ['AL']
# ENTSOE_BAL_AUTH_LIST = ['AL', 'AT', 'BE', 'BG', 'HR', 'CZ', 'DK', 'DK-DK2', 'EE', 'FI', 
#                          'FR', 'DE', 'GB', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'NL',
#                         'PL', 'PT', 'RO', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH']


def runningCarbonCast(ba):
    parentdir = os.path.normpath(os.path.join(os.getcwd(), os.pardir)) # goes to CarbonCast folder
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


def createChaeREUFolder(ba):
    newFolderDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/{ba}/chae_reu"))
    oldFolderDir = os.path.abspath(os.path.join(__file__, f"../../../data/EU_DATA/{ba}/ENTSOE"))

    os.mkdir(newFolderDir)
    
    prodfile1 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_raw_production.csv"))
    prodfile2 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_prod_interval_changes.csv"))
    prodfile3 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_prod_missing_source_data.csv"))

    fcstfile1 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_raw_forecast.csv"))
    fcstfile2 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_fcst_interval_changes.csv"))
    fcstfile3 = os.path.abspath(os.path.join(oldFolderDir, f"../{ba}_fcst_missing_source_data.csv"))

    newprodfile1 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_raw_production.csv"))
    newprodfile2 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_prod_interval_changes.csv"))
    newprodfile3 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_prod_missing_source_data.csv"))

    newfcstfile1 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_raw_forecast.csv"))
    newfcstfile2 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_fcst_interval_changes.csv"))
    newfcstfile3 = os.path.abspath(os.path.join(newFolderDir, f"../{ba}_fcst_missing_source_data.csv"))

    os.rename(prodfile1, newprodfile1)
    os.rename(prodfile2, newprodfile2)
    os.rename(prodfile3, newprodfile3)
    os.rename(fcstfile1, newfcstfile1)
    os.rename(fcstfile2, newfcstfile2)
    os.rename(fcstfile3, newfcstfile3)


if __name__ == "__main__":

    for balAuth in ENTSOE_BAL_AUTH_LIST:
        createChaeREUFolder(balAuth)

        # runningCarbonCast(balAuth)