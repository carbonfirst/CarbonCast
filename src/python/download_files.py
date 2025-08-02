import argparse
import math
import pathlib
import shutil
import sys
try:
    import rdams_client as rc
except ImportError:
    from rda_apps_clients import rdams_client as rc
from time import sleep
import re
import json

# s = "CISO: nlat=42 slat=32 wlon=-124.75 elon=-113.5"

strings = ["CISO: nlat=42 slat=32 wlon=-124.75 elon=-113.5",
"PJM: nlat=43 slat=34.25 wlon=-91 elon=-73.5",
"ERCOT: nlat=36.5 slat=25.25 wlon=-104.5 elon=-93.25",
"ISNE: nlat=48 slat=40 wlon=-74.25 elon=-66.5",
"MISO: nlat=50.00 slat=28.50 wlon=-107.75 elon=-81.75",
"BPAT: nlat=49.50 slat=39.50 wlon=-125.25 elon=-105.50",
"SWPP: nlat=49.50 slat=30.25 wlon=-107.75 elon=-89.50",
"SOCO: nlat=35.50 slat=29.25 wlon=-90.50 elon=-80.25",
"FPL: nlat=31.25 slat=24.00 wlon=-83.50 elon=-79.50",
"NYISO: nlat=45.50 slat=40.00 wlon=-80.25 elon=-71.25",
"BANC: nlat=41.75 slat=37.00 wlon=-124.00 elon=-120.00",
"LDWP: nlat=38.00 slat=33.25 wlon=-119.00 elon=-117.00",
"TIDC: nlat=38.25 slat=36.75 wlon=-121.75 elon=-119.75",
"DUK: nlat=37.00 slat=33.00 wlon=-84.75 elon=-77.75",
"SC: nlat=35.25 slat=31.50 wlon=-82.75 elon=-78.00",
"SCEG: nlat=35.25 slat=31.50 wlon=-83.00 elon=-78.75",
"SPA: nlat=40.75 slat=34.25 wlon=-98.00 elon=-89.00",
"FMPP: nlat=30.75 slat=24.00 wlon=-83.00 elon=-79.50",
"FPC: nlat=31.25 slat=25.75 wlon=-86.50 elon=-80.00",
"TAL: nlat=31.25 slat=29.75 wlon=-84.75 elon=-83.50",
"TEC: nlat=29.00 slat=27.00 wlon=-83.25 elon=-81.25",
"AECI: nlat=41.75 slat=34.25 wlon=-98.50 elon=-88.50",
"LGEE: nlat=39.50 slat=36.00 wlon=-89.75 elon=-82.25",
"DOPD: nlat=49.50 slat=46.75 wlon=-120.75 elon=-118.25",
"GCPD: nlat=48.50 slat=46.25 wlon=-120.50 elon=-118.50",
"GRID: nlat=46.25 slat=44.75 wlon=-119.75 elon=-118.25",
"IPCO: nlat=47.25 slat=41.50 wlon=-120.50 elon=-111.00",
"NEVP: nlat=42.50 slat=34.50 wlon=-122.00 elon=-111.00",
"NWMT: nlat=49.50 slat=43.25 wlon=-116.50 elon=-103.50",
"PACE: nlat=45.50 slat=33.00 wlon=-115.75 elon=-104.25",
"PACW: nlat=47.50 slat=38.75 wlon=-124.75 elon=-115.75",
"PGE: nlat=46.50 slat=44.25 wlon=-124.25 elon=-121.25",
"PSCO: nlat=41.75 slat=35.75 wlon=-109.50 elon=-102.00",
"PSEI: nlat=49.50 slat=45.75 wlon=-123.75 elon=-119.75",
"SCL: nlat=48.25 slat=47.00 wlon=-123.00 elon=-121.75",
"TPWR: nlat=48.25 slat=45.75 wlon=-124.00 elon=-120.50",
"WACM: nlat=48.00  slat=35.50 wlon=-114.50 elon=-95.75",
"SOCO: nlat=35.50 slat=29.50 wlon=-90.50 elon=-80.25",
"AZPS: nlat=36.75 slat=30.75 wlon=-115.25 elon=-108.75",
"EPE: nlat=34.00  slat=26.75 wlon=-108.75 elon=-98.25",
"PNM: nlat=44.50 slat=30.75 wlon=-123.50 elon=-101.50",
"SRP: nlat=34.50 slat=32.00 wlon=-113.75 elon=-110.50",
"TEPC: nlat=36.75 slat=31.25 wlon=-115.25 elon=-110.00",
"WALC: nlat=44.00 slat=30.75 wlon=-124.25 elon=-105.00",
"TVA: nlat=38.00 slat=31.75 wlon=-90.75 elon=-81.25",
"AL: nlat=42.75 slat=39.50 wlon=19.25 elon=21.00",
"AT: nlat=49.00 slat=46.50 wlon=9.50 elon=17.00",
"BE: nlat=51.50 slat=49.50 wlon=2.50 elon=6.25",
"BG: nlat=44.25 slat=41.25 wlon=22.25 elon=28.50",
"HR: nlat=46.50 slat=42.50 wlon=13.75 elon=19.50",
"DK: nlat=57.75 slat=54.50 wlon=7.50 elon=13.25",
"EE: nlat=59.50 slat=57.50 wlon=23.25 elon=28.25",
"FI: nlat=70.00 slat=59.75 wlon=20.50 elon=31.50",
"FR: nlat=51.25 slat=42.25 wlon=-5.25 elon=8.25",
"DE: nlat=55.25 slat=47.25 wlon=5.75 elon=15",
"GR: nlat=41.75 slat=35.00 wlon=20.25 elon=26.50",
"HU: nlat=48.50 slat=45.75 wlon=16.25 elon=22.75",
"IE: nlat=55.25 slat=51.75 wlon=-10.00 elon=-6.00",
"IT: nlat=47.00 slat=36.50 wlon=6.75 elon=18.50",
"LV: nlat=58.00 slat=55.50 wlon=21.00 elon=28.25",
"LT: nlat=56.25 slat=54.00 wlon=21.00 elon=26.50",
"NL: nlat=53.50 slat=50.75 wlon=3.25 elon=7.00",
"PL: nlat=54.75 slat=49 wlon=14 elon=24",
"PT: nlat=42.75 slat=36.50 wlon=-10.00 elon=-5.75",
"RO: nlat=48.25 slat=43.75 wlon=20.25 elon=29.50",
"RS: nlat=46.25 slat=42.25 wlon=18.75 elon=23.00",
"SK: nlat=49.50 slat=47.75 wlon=16.75 elon=22.50",
"SI: nlat=46.75 slat=45.50 wlon=13.75  elon=16.50",
"ES: nlat=43.75 slat=36.00 wlon=-9.25 elon=3.50",
"SE: nlat=69 slat=55.25 wlon=11.25 elon=21.25",
"CH: nlat=47.75 slat=45.75 wlon=6.00 elon=10.50",
"CZ: nlat=51.00 slat=48.50 wlon=12.25 elon=18.75",
"GB: nlat=61 slat=49.75 wlon=-8.25 elon=2.25"]

pattern = r'''^
    (\w+):
    \s+
    nlat=(-?\d+(?:\.\d+)?)
    \s+
    slat=(-?\d+(?:\.\d+)?)
    \s+
    wlon=(-?\d+(?:\.\d+)?)
    \s+
    elon=(-?\d+(?:\.\d+)?)
$'''

locations = [] # (grid, nlat, slat, wlon, elon)
coord_dict = {}

for s in strings:
  m = re.match(pattern, s, re.VERBOSE)
  if m:
      name, nlat, slat, wlon, elon = m.groups()
      # convert the numeric strings to floats if you need
      nlat, slat, wlon, elon = map(float, (nlat, slat, wlon, elon))
      # print(name, int(nlat), int(slat), int(wlon), int(elon))
      # tmp = (name, nlat, slat, wlon, elon)
      tmp = (name, nlat, slat, wlon, elon)
      locations.append(tmp)
      coord_dict[(nlat, slat, wlon, elon)] = name
      # print(type(name), type(nlat), type(slat), type(wlon), type(elon))
  else:
    print(f"ERROR {s}")
    
control_file_loc_check = set()

for loc, nlat, slat, wlon, elon in locations:
  nlat = int(nlat)
  slat = int(slat)
  wlon_c = math.ceil(wlon) # int(wlon)
  elon_f = math.floor(elon)
  lat = f"Latitudes (top/bottom): {nlat} / {slat}"
  lon = f"Longitudes (left/right): {wlon_c} / {elon_f}"
  control_file_loc_check.add((loc, lat, lon))
  
  elon_c = math.ceil(elon)
  lat = f"Latitudes (top/bottom): {nlat} / {slat}"
  lon = f"Longitudes (left/right): {wlon_c} / {elon_c}"
  control_file_loc_check.add((loc, lat, lon))
  
  wlon_f = math.floor(wlon) # int(wlon)
  elon_f = math.floor(elon)
  lat = f"Latitudes (top/bottom): {nlat} / {slat}"
  lon = f"Longitudes (left/right): {wlon_f} / {elon_f}"
  control_file_loc_check.add((loc, lat, lon))
  
  elon_c = math.ceil(elon)
  lat = f"Latitudes (top/bottom): {nlat} / {slat}"
  lon = f"Longitudes (left/right): {wlon_f} / {elon_c}"
  control_file_loc_check.add((loc, lat, lon))

status = rc.get_status()

def extract_parameter(text):
  lines = text.splitlines()
  for i, line in enumerate(lines):
    if "Parameter(s):" in line:
      # Return the line right after "Parameter(s):", stripped of leading/trailing whitespace
      return lines[i + 1].strip()
  return None  # Return None if not found

def extract_coordinates(text):
  match = re.search(r'nlat=([-\d.]+);slat=([-\d.]+);wlon=([-\d.]+);elon=([-\d.]+)', text)
  if match:
      return tuple(map(float, match.groups()))
  else:
      return None

"""
for every elem in status:
  for every location poss:
    check if the elem is that location:
      now that we know the location
      get the type of data it has, and save the acronym
      download the file and save the 'wfile'
      save this into a dict, (loc, data type): wfile
"""

"""
TMP/DPT
tmp_dpt
Temperature
# Dewpoint temperature

DSWRF
dswrf
Downward shortwave radiation flux

U GRD/V GRD
ugrd_vgrd
u-component of wind
# v-component of wind

A PCP
apcp
Total precipitation
"""

parameter_dict = {
  "Temperature": "tmp_dpt",
  "Downward shortwave radiation flux": "dswrf",
  "u-component of wind": "ugrd_vgrd",
  "Total precipitation": "apcp",
}

download_details = {}

for elem in status['data']:
  if elem['status'] == "Queued for Processing":
    request_index = elem['request_index']
    print("QUEUED NOT READY", request_index)
    continue
  
  if elem['status'] != 'Completed':
    print()
    coords = extract_coordinates(elem['rinfo'])
    loc = coord_dict[coords]
    parameter = parameter_dict[extract_parameter(elem["subset_info"]['note'])]
    print(elem['request_index'], loc, parameter, "ERROR")
    download_details[(loc, parameter)] = "ERROR"
    
    # request_index = str(elem['request_index'])
    # print(f"PURGING {request_index}")
    # # continue
    # rc.purge_request(request_index)
    
    continue
  
  loc_found = False
  for loc, lat, lon in control_file_loc_check:
    if lat in elem["subset_info"]['note'] and lon in elem["subset_info"]['note']:
      loc_found = True

      parameter = parameter_dict[extract_parameter(elem["subset_info"]['note'])]
      if parameter == None:
        print("UNABLE TO FIND ERROR")
        exit()
        
      date_range_match = re.search(r"Date range: (.*)", elem["subset_info"]['note'])
      date_range_str = ""
      if date_range_match:
        date_range_str = date_range_match.group(1)
        print(date_range_str)
      
      request_index = elem['request_index']
      download_output = rc.download(request_index, out_dir=f"./downloaded_files/{loc}_{parameter}_{date_range_str}_")
      print(elem, parameter)

  if loc_found == False:
    print()
    print("NO LOC FOUND", elem['request_index'])


# print()
# print(download_details)


# with open("rda_downloaded_files.txt", "w") as f:
#   json.dump(download_details, f, indent=2)


"""
dsnum=d084001;startdate=2019-01-01 00:00;enddate=2023-12-31 00:00;parameters=3!7-0.2-1:0.0.0,3!7-0.2-1:0.0.6;product=1,3,23,26,29,32,35,38,41,45,47,50,53,56,59,62,65,68,71,74,77,80,83,86,92,95,98,101,110,119,124,129,134,139,144,149,154,159,164,169,174,179,184,189,199,204,209,214,219,224,229,234,239,244,249,254;level=221;nlat=43.0;slat=34.25;wlon=-91.0;elon=-73.5;dates=init
"""

"""
Latitudes (top/bottom): 36 / 25
Longitudes (left/right): -104 / -93

Latitudes (top/bottom): 42 / 32
Longitudes (left/right): -125 / -114

Latitudes (top/bottom): 43 / 34
Longitudes (left/right): -91 / -74

Latitudes (top/bottom): 42 / 32
Longitudes (left/right): -125 / -114

Latitudes (top/bottom): 43 / 34
Longitudes (left/right): -91 / -74

Latitudes (top/bottom): 42 / 32
Longitudes (left/right): -125 / -114

Latitudes (top/bottom): 43 / 34
Longitudes (left/right): -91 / -74
"""