"""This script functions as a glue-script. It can be run as follows:
    python run.py <region> <date>
    where <region> is the region of interest and <date> is the date of interest.

    This script will then do the following in order:
    - Download the data from the EIA API
    - Download weather data from NOMADS for the region and date of interest
    - Run the first-tier model on the downloaded data and generate models for each source
    - Run the second-tier model on the downloaded data and generate 96-hour carbon intensity forecasts
"""
import argparse
import pandas as pd
from data.scripts.eiaParser import getEIAData
from src.weather.getWeatherData_NOMADS import getWeatherData
from src.carbonIntensityCalculator import runProgram
from src.weather.dataCollectionScript import average_weather_data
from src.weather.cleanWeatherData import aggregate_weather_data
from src.firstTierTesting import runFirstTierTestingScript
from src.secondTierTesting import runSecondTierScript

parser = argparse.ArgumentParser(
    prog='CarbonCast',
    description='Generate carbon intensity forecasts for a given region and date.')
parser.add_argument('region', metavar='r', type=str, nargs=1,
                    help='the region of interest')
parser.add_argument('date', metavar='d', type=str, nargs=1,
                    help='date in the format YYYY-MM-DD')

args = parser.parse_args()
region = args.region[0]
date = args.date[0]

# TODO: Change this to be downloaded only for the specific region
print(f"Downloading EIA data on {date} for all regions")
getEIAData(date)
print("Download complete")

runProgram(region, False, False, 8, date)
print(f"Generated direct emissions for {region} on {date}")
runProgram(region, True, False, 8, date)
print(f"Generated lifecycle emissions for {region} on {date}")

df = pd.read_csv(f"data/{region}/day/{region}_direct_emissions.csv")
# move other column to end
df = df[['UTC time', 'carbon_intensity', 'coal', 'nat_gas', 'nuclear', 'oil', 'hydro', 'solar', 'wind', 'other']]
df.to_csv(f"data/{region}/day/{region}_direct_emissions.csv", index=False)
print("Moved 'other' column of direct emissions to the end")

# first_column = df.columns[0]
# # Delete first
# df = df.drop([first_column], axis=1)

print(f"Downloading weather data for {region} on {date}")
getWeatherData(region, date)

average_weather_data(date)
print(f"Generated source averages")

aggregate_weather_data()
print(f"Generated weather forecasts")

print(f"Running first-tier model to generate source DA forecast")
runFirstTierTestingScript()

df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_weather_forecast.csv")

# add additional columns for each of the 8 sources
wind_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_WIND.csv")
solar_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_SOLAR.csv")
nat_gas_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_NAT_GAS.csv")
coal_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_COAL.csv")
nuclear_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_NUCLEAR.csv")
hydro_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_HYDRO.csv")
oil_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_OIL.csv")
other_df = pd.read_csv(f"src/weather/extn/{region}/weather_data/{region}_DA_OTHER.csv")

df['avg_wind_production_forecast'] = wind_df['avg_wind_production_forecast']
df['avg_solar_production_forecast'] = solar_df['avg_solar_production_forecast']
df['avg_nat_gas_production_forecast'] = nat_gas_df['avg_nat_gas_production_forecast']
df['avg_coal_production_forecast'] = coal_df['avg_coal_production_forecast']
df['avg_nuclear_production_forecast'] = nuclear_df['avg_nuclear_production_forecast']
df['avg_hydro_production_forecast'] = hydro_df['avg_hydro_production_forecast']
df['avg_oil_production_forecast'] = oil_df['avg_oil_production_forecast']
df['avg_other_production_forecast'] = other_df['avg_other_production_forecast']

df.to_csv(f"src/weather/extn/{region}/weather_data/{region}_96hr_forecasts_DA.csv")

print(f"Generated 96-hour DA forecast file")

print(f"Running second-tier model to generate 96-hour carbon intensity forecast")
runSecondTierScript()

print(f"Generated 96-hour carbon intensity forecast file")

