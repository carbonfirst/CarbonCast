"""
Real-time weather data is fetched from the NOMADS website
"""

import requests
import time
import os

url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

# continent = ["US", "EU"]

boundingBox = {
    "US": {"nlat": 50, "slat": 24, "wlon": -125.25, "elon": -66.5},
    "EU": {"nlat": 70.00, "slat": 35.00, "wlon": -10.00, "elon": 31.50},
}

def buildUrl(date, param, level, continent, t):
    request_url = f"{url}?dir=/gfs.{date}/00/atmos&file=gfs.t00z.pgrb2.0p25.f0{t}&{'&'.join([f'var_{comp}=on' for comp in param.split('/')])}&lev_{level}=on&subregion=&toplat={boundingBox[continent]['nlat']}&leftlon={boundingBox[continent]['wlon']}&rightlon={boundingBox[continent]['elon']}&bottomlat={boundingBox[continent]['slat']}"
    return request_url

def submitDataRequest(param, level, continent, year, month, day):
    filedir = os.path.dirname(__file__)
    t = "00"
    date = f"{year}{month}{day}"
    # for i in range(1, 97): # uncomment this line & comment below line for hourly weather forecasts
    for i in range(3, 97, 3): 
        if i < 10:
            t = "0" + str(i)
        else:
            t = str(i)
        request_url = buildUrl(date, param, level, continent, t)
        response = requests.get(request_url)

        if (continent == "US"):
            with open(os.path.normpath(os.path.join(filedir, f"../../real_time/weather_data/{param.lower().replace('/', '_')}/gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")), 'wb+') as f:
                f.write(response.content)
        elif (continent == "EU"):
            with open(os.path.normpath(os.path.join(filedir, f"../../real_time/EU_DATA/weather_data/{param.lower().replace('/', '_')}/gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")), 'wb+') as f:
                f.write(response.content)
        # print(f"Downloaded file: gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")
        time.sleep(1)

# date = 2023-05-21
def getWeatherData(continent, date):
    submitDataRequest("UGRD/VGRD", "10_m_above_ground", continent, date[0:4], date[5:7], date[8:10])
    print("Finished UGRD/VGRD")
    
    submitDataRequest("TMP/DPT", "2_m_above_ground", continent, date[0:4], date[5:7], date[8:10])
    print("Finished TMP/DPT")
    
    submitDataRequest("DSWRF", "surface", continent, date[0:4], date[5:7], date[8:10])
    print("Finished DSWRF")
    
    submitDataRequest("APCP", "surface", continent, date[0:4], date[5:7], date[8:10])
    print("Finished APCP")

# https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?dir=/gfs.20230407/00/atmos&file=gfs.t00z.pgrb2.0p25.f000&var_UGRD=on&lev_10_m_above_ground=on&subregion=&toplat=42&leftlon=-124.75&rightlon=-113.5&bottomlat=32