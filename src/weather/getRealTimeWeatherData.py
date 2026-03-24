"""
Real-time weather data is fetched from the NOMADS website
"""

import requests
import time
import os

url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
REQUEST_HEADERS = {
    "User-Agent": "CarbonCast/1.0",
    "Accept": "*/*",
    "Connection": "close",
}

class WeatherDownloadError(Exception):
    pass

# continent = ["US", "EU"]

boundingBox = {
    "US": {"nlat": 50, "slat": 24, "wlon": -125.25, "elon": -66.5},
    "EU": {"nlat": 70.00, "slat": 35.00, "wlon": -10.00, "elon": 31.50},
}

def buildUrl(date, param, level, continent, t):
    request_url = f"{url}?dir=/gfs.{date}/00/atmos&file=gfs.t00z.pgrb2.0p25.f0{t}&{'&'.join([f'var_{comp}=on' for comp in param.split('/')])}&lev_{level}=on&subregion=&toplat={boundingBox[continent]['nlat']}&leftlon={boundingBox[continent]['wlon']}&rightlon={boundingBox[continent]['elon']}&bottomlat={boundingBox[continent]['slat']}"
    return request_url

def _get_output_dir(param):
    filedir = os.path.dirname(__file__)
    output_dir = os.path.normpath(
        os.path.join(filedir, f"../../real_time/weather_data/{param.lower().replace('/', '_')}")
    )
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def _get_output_path(param, year, month, day, t):
    output_dir = _get_output_dir(param)
    return os.path.join(
        output_dir, f"gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2"
    )

def _all_expected_files_exist(param, year, month, day):
    for i in range(3, 97, 3):
        t = f"{i:02d}"
        if not os.path.exists(_get_output_path(param, year, month, day, t)):
            return False
    return True

def _validate_weather_response(response, request_url):
    if response.status_code != 200:
        raise WeatherDownloadError(
            f"NOMADS request failed with status {response.status_code} for {request_url}"
        )

    content_type = response.headers.get("Content-Type", "").lower()
    content_preview = response.content[:200].lstrip().lower()
    if "text/html" in content_type or content_preview.startswith(b"<!doctype html") or content_preview.startswith(b"<html"):
        raise WeatherDownloadError(
            f"NOMADS returned HTML instead of GRIB2 content for {request_url}"
        )

    if not response.content:
        raise WeatherDownloadError(f"NOMADS returned an empty response for {request_url}")

def submitDataRequest(param, level, continent, year, month, day):
    t = "00"
    date = f"{year}{month}{day}"
    if _all_expected_files_exist(param, year, month, day):
        print(f"Using existing exact-date weather files for {param} on {year}-{month}-{day}")
        return

    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    # for i in range(1, 97): # uncomment this line & comment below line for hourly weather forecasts
    try:
        for i in range(3, 97, 3): 
            if i < 10:
                t = "0" + str(i)
            else:
                t = str(i)
            request_url = buildUrl(date, param, level, continent, t)
            try:
                response = session.get(request_url, timeout=(15, 120), stream=True)
            except requests.RequestException as exc:
                raise WeatherDownloadError(
                    f"NOMADS request failed for {request_url}: {exc}. "
                    f"No exact-date cached weather files were available for {year}-{month}-{day}."
                ) from exc

            _validate_weather_response(response, request_url)

            output_path = _get_output_path(param, year, month, day, t)
            with open(output_path, 'wb+') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            response.close()
            # print(f"Downloaded file: gfs.t00z.pgrb2.0p25.{year}{month}{day}.f00{t}.grib2")
            time.sleep(1)
    finally:
        session.close()

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
