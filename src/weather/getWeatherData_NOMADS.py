import requests
import time
import os

url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

regions = ['CISO', 'PJM', 'ERCOT', 'ISNE', 'SE', 'GB', 'DE', 'CA-ON', 'DK-DK2',
            'PL', 'MISO', 'AUS-NSW', 'AUS_QLD', 'AUS_SA']

coordDict = {
    'CISO': {'nlat': 42, 'slat': 32, 'wlon': -124.75, 'elon': -113.5},
    'PJM': {'nlat': 43, 'slat': 34.25, 'wlon': -91, 'elon': -73.5},
    'ERCOT': {'nlat': 36.5, 'slat': 25.25, 'wlon': -104.5, 'elon': -93.25},
    'ISNE': {'nlat': 48, 'slat': 40, 'wlon': 74.25, 'elon': -66.5},
    'SE': {'nlat': 69, 'slat': 55.25, 'wlon': 11.25, 'elon': 21.25},
    'GB': {'nlat': 61, 'slat': 49.75, 'wlon': -8.25, 'elon': 2.25},
    'DE': {'nlat': 55.25, 'slat': 47.25, 'wlon': 5.75, 'elon': 15},
    'CA-ON': {'nlat': 57.25, 'slat': 41.25, 'wlon': -95.75, 'elon': -73.75},
    'DK-DK2': {'nlat': 57.75, 'slat': 54.75, 'wlon': 7.25, 'elon': 11.25},
    'PL': {'nlat': 54.75, 'slat': 49, 'wlon': 14, 'elon': 24},
    'MISO' : {'nlat': 107.862115248933, 'slat': 28.4286900252724, 'wlon': -81.9130970652477, 'elon': 49.884274119856},
    'AUS-NSW':{'nlat': -34.75, 'slat': -36.50, 'wlon': 148.25, 'elon': 150},
    'AUS_QLD': {'nlat': -8.75, 'slat': -29.75, 'wlon': 137.50, 'elon': 154},
    'AUS_SA': {'nlat': -25.50, 'slat': -38.50, 'wlon': 128.50, 'elon': 141.50}, 
}

def buildUrl(date, param, level, region, t):
    request_url = f"{url}?dir=/gfs.{date}/00/atmos&file=gfs.t00z.pgrb2.0p25.f0{t}&{'&'.join([f'var_{comp}=on' for comp in param.split('/')])}&lev_{level}=on&subregion=&toplat={coordDict[region]['nlat']}&leftlon={coordDict[region]['wlon']}&rightlon={coordDict[region]['elon']}&bottomlat={coordDict[region]['slat']}"

    return request_url

def submitDataRequest(param, level, region, year, month, day):
    filedir = os.path.dirname(__file__)
    t = "00"
    date = f"{year}{month}{day}"
    for i in range(1, 96):
        if i < 10:
            t = "0" + str(i)
        else:
            t = str(i)
        request_url = buildUrl(date, param, level, region, t)
        response = requests.get(request_url)

        with open(os.path.normpath(os.path.join(filedir, f"extn/{region}/weather_data/{param.lower().replace('/', '_')}/gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")), 'wb+') as f:
            f.write(response.content)
        print(f"Downloaded file: gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")
        time.sleep(1)

# date = 2023-05-21
def getWeatherData(region, date):
    submitDataRequest("UGRD/VGRD", "10_m_above_ground", region, date[0:4], date[5:7], date[8:10])
    print("Finished UGRD/VGRD")
    
    submitDataRequest("TMP/DPT", "2_m_above_ground", region, date[0:4], date[5:7], date[8:10])
    print("Finished TMP/DPT")
    
    submitDataRequest("DSWRF", "surface", region, date[0:4], date[5:7], date[8:10])
    print("Finished DSWRF")
    
    submitDataRequest("APCP", "surface", region, date[0:4], date[5:7], date[8:10])
    print("Finished APCP")

# https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?dir=/gfs.20230407/00/atmos&file=gfs.t00z.pgrb2.0p25.f000&var_UGRD=on&lev_10_m_above_ground=on&subregion=&toplat=42&leftlon=-124.75&rightlon=-113.5&bottomlat=32