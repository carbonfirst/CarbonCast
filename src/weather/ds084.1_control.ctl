dataset=ds084.1
date=202112010000/to/202201310000 # change start and end dates as required
datetype=init
param=A PCP
level=SFC:0
nlat=-8.75
slat=-29.75
wlon=137.50
elon=154
#product=Analysis/3-hour Forecast/6-hour Forecast/9-hour Forecast/12-hour Forecast/15-hour Forecast/18-hour Forecast/21-hour Forecast/24-hour Forecast/27-hour Forecast/30-hour Forecast/33-hour Forecast/36-hour Forecast/39-hour Forecast/42-hour Forecast/45-hour Forecast/48-hour Forecast/51-hour Forecast/54-hour Forecast/57-hour Forecast/60-hour Forecast/63-hour Forecast/66-hour Forecast/69-hour Forecast/72-hour Forecast/75-hour Forecast/78-hour Forecast/81-hour Forecast/84-hour Forecast/87-hour Forecast/90-hour Forecast/93-hour Forecast/96-hour Forecast
#product=3-hour Average (initial+0 to initial+3)/6-hour Average (initial+0 to initial+6)/3-hour Average (initial+6 to initial+9)/6-hour Average (initial+6 to initial+12)/3-hour Average (initial+12 to initial+15)/6-hour Average (initial+12 to initial+18)/3-hour Average (initial+18 to initial+21)/6-hour Average (initial+18 to initial+24)/3-hour Average (initial+24 to initial+27)/6-hour Average (initial+24 to initial+30)/3-hour Average (initial+30 to initial+33)/6-hour Average (initial+30 to initial+36)/3-hour Average (initial+36 to initial+39)/6-hour Average (initial+36 to initial+42)/3-hour Average (initial+42 to initial+45)/6-hour Average (initial+42 to initial+48)/3-hour Average (initial+48 to initial+51)/6-hour Average (initial+48 to initial+54)/3-hour Average (initial+54 to initial+57)/6-hour Average (initial+54 to initial+60)/3-hour Average (initial+60 to initial+63)/6-hour Average (initial+60 to initial+66)/3-hour Average (initial+66 to initial+69)/6-hour Average (initial+66 to initial+72)/3-hour Average (initial+72 to initial+75)/6-hour Average (initial+72 to initial+78)/3-hour Average (initial+72 to initial+81)/6-hour Average (initial+78 to initial+84)/3-hour Average (initial+84 to initial+87)/6-hour Average (initial+84 to initial+90)/3-hour Average (initial+90 to initial+93)/6-hour Average (initial+90 to initial+96)
product=3-hour Accumulation (initial+0 to initial+3)/6-hour Accumulation (initial+0 to initial+6)/3-hour Accumulation (initial+6 to initial+9)/6-hour Accumulation (initial+6 to initial+12)/3-hour Accumulation (initial+12 to initial+15)/6-hour Accumulation (initial+12 to initial+18)/3-hour Accumulation (initial+18 to initial+21)/6-hour Accumulation (initial+18 to initial+24)/3-hour Accumulation (initial+24 to initial+27)/6-hour Accumulation (initial+24 to initial+30)/3-hour Accumulation (initial+30 to initial+33)/6-hour Accumulation (initial+30 to initial+36)/3-hour Accumulation (initial+36 to initial+39)/6-hour Accumulation (initial+36 to initial+42)/3-hour Accumulation (initial+42 to initial+45)/6-hour Accumulation (initial+42 to initial+48)/3-hour Accumulation (initial+48 to initial+51)/6-hour Accumulation (initial+48 to initial+54)/3-hour Accumulation (initial+54 to initial+57)/6-hour Accumulation (initial+54 to initial+60)/3-hour Accumulation (initial+60 to initial+63)/6-hour Accumulation (initial+60 to initial+66)/3-hour Accumulation (initial+66 to initial+69)/6-hour Accumulation (initial+66 to initial+72)/3-hour Accumulation (initial+72 to initial+75)/6-hour Accumulation (initial+72 to initial+78)/3-hour Accumulation (initial+72 to initial+81)/6-hour Accumulation (initial+78 to initial+84)/3-hour Accumulation (initial+84 to initial+87)/6-hour Accumulation (initial+84 to initial+90)/3-hour Accumulation (initial+90 to initial+93)/6-hour Accumulation (initial+90 to initial+96)
targetdir=/glade/scratch


# Weather variables (replace lines 4 & 5 above as required):

# 1. Wind speed. We obtain the u- & v- components of wind & then calculate the magintude of wind speed
# param=U GRD/V GRD
# level=HTGL:10
# Uncomment line 10. Comment lines 11 & 12

# 2. Temperature & Dewpoint temperature.
# param=TMP/DPT
# level=HTGL:2
# Uncomment line 10. Comment lines 11 & 12

# 3. Downward shortwave radiation flux (solar irradiance).
# param=DSWRF
# level=SFC:0
# Uncomment line 11. Comment lines 10 & 12

# 1. Total annual precipitation.
# param=A PCP
# level=SFC:0
# Uncomment line 12. Comment lines 10 & 11


# Bounding boxes for the regions covered. Change lines 6-9 with relevant values.

# US regions
# CISO: nlat=42 slat=32 wlon=-124.75 elon=-113.5
# PJM: nlat=43 slat=34.25 wlon=-91 elon=-73.5
# ERCOT: nlat=36.5 slat=25.25 wlon=-104.5 elon=-93.25
# ISNE: nlat=48 slat=40 wlon=-74.25 elon=-66.5
# MISO: nlat=50.00 slat=28.50 wlon=-107.75 elon=-81.75
# BPAT: nlat=49.50 slat=39.50 wlon=-125.25 elon=-105.50
# SWPP: nlat=49.50 slat=30.25 wlon=-107.75 elon=-89.50
# SOCO: nlat=35.50 slat=29.25 wlon=-90.50 elon=-80.25 
# FPL: nlat=31.25 slat=24.00 wlon=-83.50 elon=-79.50 
# NYISO: nlat=45.50 slat=40.00 wlon=-80.25 elon=-71.25 


# EU regions
# Sweden: SE: nlat=69 slat=55.25 wlon=11.25 elon=21.25
# GReat Britain: GB: nlat=61 slat=49.75 wlon=-8.25 elon=2.25
# Germany: DE: nlat=55.25 slat=47.25 wlon=5.75 elon=15
# Denmark zone 2: DK-DK2: nlat=57.75 slat=54.75 wlon=7.25 elon=11.25
# Poland: PL: nlat=54.75 slat=49 wlon=14 elon=24
# Finland: FI: nlat=70.00 slat=59.75 wlon=20.50 elon=31.50
# France: FR: nlat=51.25 slat=42.25 wlon=-5.25 elon=8.25 
# Spain: ES: nlat=43.75 slat=36.00 wlon=-9.25 elon=3.50
# Belgium: BE: nlat=51.50 slat=49.50 wlon=2.50 elon=6.25
# Netherlands: NL: nlat=53.50 slat=50.75 wlon=3.25 elon=7.00

# AUS regions
# AUS-NSW: nlat=-34.75 slat=-36.50 wlon=148.25 elon=150
# AUS_QLD: nlat=-8.75 slat=-29.75 wlon=137.50 elon=154
# AUS_SA: nlat=-25.50 slat=-38.50 wlon=128.50 elon=141.50

# Other regions
# Canada-Ontario: CA-ON: nlat=57.25 slat=41.25 wlon=-95.75 elon=-73.75