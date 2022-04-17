import csv
import math
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
import seaborn as sns
# from keras import metrics, optimizers, regularizers
# from keras.initializers import initializers_v2
# from keras.layers import Dense, Flatten
# from keras.layers.convolutional import AveragePooling1D, Conv1D, MaxPooling1D
# from keras.layers.core import Activation, Dropout
# from keras.layers.normalization.batch_normalization import BatchNormalization
# from keras.models import Sequential
import tensorflow as tf
from numpy.lib.utils import source
from pandas.core.frame import DataFrame
from pandas.io.formats import style
from scipy.sparse import data
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from sklearn.utils import validation
from statsmodels.tsa.stattools import adfuller

# ISO_LIST = ["CISO", "ERCO", "ISNE", "PJM"]
LOCAL_TIMEZONES = {"BPAT": "US/Pacific", "CISO": "US/Pacific", "ERCO": "US/Central", 
                    "SOCO" :"US/Central", "SWPP": "US/Central", "FPL": "US/Eastern", 
                    "ISNE": "US/Eastern", "NYIS": "US/Eastern", "PJM": "US/Eastern", 
                    "MISO": "US/Eastern"}
# START_ROW = {"CISO": 30712, "ERCO": 30714, "ISNE": 30715, "PJM": 30715}
ISO = "ERCO"
IN_FILE_NAME = None
OUT_FILE_NAME = None

DAY_INTERVAL = 1
MONTH_INTERVAL = 1

#carbon rate used by electricityMap. Checkout this link:
# https://github.com/tmrowco/electricitymap-contrib/blob/master/config/co2eq_parameters.json
carbonRate = {"coal": 820, "biomass": 230, "nat_gas": 490, "geothermal": 38, "hydro": 24,
                "nuclear": 12, "oil": 650, "solar": 45, "unknown": 700, 
                "other": 700, "wind": 11} # g/kWh
forcast_carbonRate = {"avg_coal_production_forecast": 820, "avg_biomass_production_forecast": 230, 
                "avg_nat_gas_production_forecast": 490, "avg_geothermal_production_forecast": 38, 
                "avg_hydro_production_forecast": 24, "avg_nuclear_production_forecast": 12, 
                "avg_oil_production_forecast": 650, "avg_solar_production_forecast": 45, 
                "avg_unknown_production_forecast": 700, "avg_other_production_forecast": 700, 
                "avg_wind_production_forecast": 11} # g/kWh

# carbonRate = {"coal": 820, "biomass": 230, "nat_gas": 490, "geothermal": 38, "hydro": 24,
#                 "nuclear": 12, "oil": 650, "solar": 45, "unknown": 292.9, 
#                 "other": 700, "wind": 11} # g/kWh  # SE
# forcast_carbonRate = {"avg_coal_production_forecast": 820, "avg_biomass_production_forecast": 230, 
#                 "avg_nat_gas_production_forecast": 490, "avg_geothermal_production_forecast": 38, 
#                 "avg_hydro_production_forecast": 24, "avg_nuclear_production_forecast": 12, 
#                 "avg_oil_production_forecast": 650, "avg_solar_production_forecast": 45, 
#                 "avg_unknown_production_forecast": 292.9, "avg_other_production_forecast": 700, 
#                 "avg_wind_production_forecast": 11} # SE




def initialize(inFileName, startRow):
    # load the new file
    print("FILE: ", inFileName)
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=["UTC time"]) #, index_col=["Local time"]
    # dataset.rename(columns={"NG": "net_generation", "NG: COL": "coal", "NG: NG": "nat_gas", 
    #                         "NG: NUC": "nuclear", "NG: OIL": "oil", "NG: WAT": "hydro",
    #                         "NG: SUN": "solar", "NG: WND": "wind", "NG: OTH": "other", 
    #                         "NG: UNK": "unknown"}, inplace=True)
    # numRows = 17544 #8784
    # startRowOf2019 = startRow
    # dataset = dataset.iloc[startRowOf2019:startRowOf2019+numRows, :]
    print(dataset.head(2))
    print(dataset.tail(2))
    dataset.replace(np.nan, 0, inplace=True) # replace NaN with 0.0
    num = dataset._get_numeric_data()
    num[num<0] = 0
    
    print(dataset.columns)
    print("UTC time", dataset["UTC time"].dtype)
    # for i in range(1, len(dataset.columns.values)):
    #     col = dataset.columns.values[i]
    #     print(col, dataset[col].dtype)
    #     dataset[col] = dataset[col].astype(np.float64)
    #     print(col, dataset[col].dtype)
    return dataset

def createHourlyTimeCol(dataset, datetime, startDate):
    modifiedDataset = pd.DataFrame(np.empty((17544, len(dataset.columns.values))) * np.nan,
                    columns=dataset.columns.values)
    startDateTime = np.datetime64(startDate)
    hourlyDateTime = []
    hourlyDateTime.append(startDateTime)
    idx = 0
    modifiedDataset.iloc[0] = dataset.iloc[0]
    for i in range(17544-1):
        hourlyDateTime.append(hourlyDateTime[i] +np.timedelta64(1, 'h'))
        # # print(datetime[i+1], datetime[i], (datetime[i+1]-datetime[i]).total_seconds())
        # # if (hourlyDateTime[-1] != datetime[i+1]):
        # if ((pd.Timestamp(datetime[i+1]).hour-pd.Timestamp(datetime[i]).hour) != 1):
        #     if (pd.Timestamp(datetime[i]).hour == 23 and pd.Timestamp(datetime[i+1]).hour == 0):
        #         pass
        #     else:
        #     # print(i, hourlyDateTime[-1], datetime[i+1])
        #         print(i, datetime[i], datetime[i+1], pd.Timestamp(datetime[i]).hour, pd.Timestamp(datetime[i+1]).hour)
        #     # print(dataset.iloc[i-1])
        #     # print(dataset.iloc[i])
    # exit(0)
    return hourlyDateTime

def fillMissingHours(dataset, datetime, hourlyDateTime):
    modifiedDataset = pd.DataFrame(index=hourlyDateTime, columns= dataset.columns.values)
    idx = 0
    for i in range(len(hourlyDateTime)):
        if(datetime[idx]==hourlyDateTime[i]):
            for j in range(len(dataset.columns.values)):
                modifiedDataset.iloc[i,j] = dataset.iloc[idx,j]
            idx +=1
        else:
            print(idx, i, datetime[idx], hourlyDateTime[i])
            modifiedDataset.iloc[i,0] = hourlyDateTime[i]
            for j in range(1, len(dataset.columns.values)):
                modifiedDataset.iloc[i,j] = dataset.iloc[idx,j]
    return modifiedDataset



def calculateCarbonIntensity(dataset, carbonRate):
    carbonIntensity = 0
    carbonCol = []
    miniDataset = dataset.iloc[:, CARBON_INTENSITY_COLUMN:]
    print("**", miniDataset.columns.values)
    rowSum = miniDataset.sum(axis=1).to_list()
    for i in range(len(miniDataset)):
        if(rowSum[i] == 0):
            # basic algorithm to fill missing values if all sources are missing
            # just using the previous hour's value
            # same as electricityMap
            for j in range(1, len(dataset.columns.values)):
                if(dataset.iloc[i, j] == 0):
                    dataset.iloc[i, j] = dataset.iloc[i-1, j]
                miniDataset.iloc[i] = dataset.iloc[i, CARBON_INTENSITY_COLUMN:]
                # print(miniDataset.iloc[i])
            rowSum[i] = rowSum[i-1]
        carbonIntensity = 0
        for j in range(len(miniDataset.columns.values)):
            source = miniDataset.columns.values[j]
            sourceContribFrac = miniDataset.iloc[i, j]/rowSum[i]
            # print(sourceContribFrac, carbonRate[source])
            carbonIntensity += (sourceContribFrac * carbonRate[source])
        if (carbonIntensity == 0):
            print(miniDataset.iloc[i])
        carbonCol.append(round(carbonIntensity, 2))
    dataset.insert(loc=CARBON_INTENSITY_COLUMN, column="carbon_intensity", value=carbonCol)
    return dataset

def calculateCarbonIntensityFromSourceForecasts(dataset, carbonRate, carbonIntensityCol):
    carbonIntensity = 0
    carbonCol = []
    miniDataset = dataset.iloc[:, carbonIntensityCol:]
    print("**", miniDataset.columns.values)
    rowSum = miniDataset.sum(axis=1).to_list()
    for i in range(len(miniDataset)):
        if(rowSum[i] == 0):
            # basic algorithm to fill missing values if all sources are missing
            # just using the previous hour's value
            # same as electricityMap
            for j in range(1, len(dataset.columns.values)):
                if(dataset.iloc[i, j] == 0):
                    dataset.iloc[i, j] = dataset.iloc[i-1, j]
                miniDataset.iloc[i] = dataset.iloc[i, carbonIntensityCol:]
                # print(miniDataset.iloc[i])
            rowSum[i] = rowSum[i-1]
        carbonIntensity = 0
        for j in range(len(miniDataset.columns.values)):
            source = miniDataset.columns.values[j]
            sourceContribFrac = miniDataset.iloc[i, j]/rowSum[i]
            # print(sourceContribFrac, carbonRate[source])
            carbonIntensity += (sourceContribFrac * carbonRate[source])
        if (carbonIntensity == 0):
            print(miniDataset.iloc[i])
        carbonCol.append(round(carbonIntensity, 2))
    dataset.insert(loc=carbonIntensityCol, column="carbon_from_src_forecasts", value=carbonCol)
    return dataset

def getMape(dates, actual, forecast):
    avgDailyMape = []
    mape = tf.keras.losses.MeanAbsolutePercentageError()
    for i in range(0, len(actual), 24):
        mapeTensor =  mape(actual[i:i+24], forecast[i:i+24])
        mapeScore = mapeTensor.numpy()
        print("Day: ", dates[i], "MAPE: ", mapeScore)
        avgDailyMape.append(mapeScore)

    mapeTensor =  mape(actual, forecast)
    mapeScore = mapeTensor.numpy()
    return avgDailyMape, mapeScore

def plotBoxplots(isoDailyMape):
    fig = plt.figure()
    
    # get dictionary returned from boxplot
    fig, ax = plt.subplots()
    bp_dict = ax.boxplot(isoDailyMape.values(), vert=True)
    # print(bp_dict)
    ax.set_xticklabels(isoDailyMape.keys())
    for line in bp_dict['medians']:
        # get position data for median line
        # print(line.get_xydata())
        x, y = line.get_xydata()[1] # top of median line
        # overlay median value
        plt.text(x, y, '%.1f' % y,
            horizontalalignment='center') # draw above, centered

    plt.xlabel("Zones/ISOs")
    plt.ylabel("MAPE (%)")
    plt.title("MAPE boxplots")
    # plt.grid(axis="x")

    return

def readFile(inFileName):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=["UTC time"], index_col=["UTC time"])    
    numRowsInYear = 8784
    print(dataset.head())
    columns = dataset.columns
    print(columns)
    dateTime = dataset.index.values
    return dataset, dateTime

def showDailyAverageCarbon(dataset, dateTime, localTimezone, iso):
    carbon = np.array(dataset["carbon_intensity"].values)
    carbon = np.resize(carbon, (carbon.shape[0]//24, 24))
    dailyAvgCarbon = np.mean(carbon, axis = 1)
    dates = getDatesInLocalTimeZone(dateTime, localTimezone)    
    
    fig, ax = plt.subplots()
    ax.plot(dates, dailyAvgCarbon)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d, %H:%M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1, tz=localTimezone))    
    plt.xlabel("Local time")
    plt.ylabel("Daily avg Carbon Intensity (g/kWh)")
    plt.title(iso)
    plt.grid(axis="x")
    plt.xticks(rotation=90)
    plt.legend()
    return

def getDatesInLocalTimeZone(dateTime, localTimezone):
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime), 24):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(localTimezone)
        dates.append(day)    
    return dates

def analyzeTimeSeries(dataset, trainData, testData, dateTime):
    checkStationarity(dataset) # ADF test to check if TS is staionary
    # print("Sample entropy:", SampEn(dataset, m=24, r=0.2)) # Sample Entropy to check how difficult it is to forecast a TS
    # Sample entropy taking too much time
    # Granger Causality test to check which features (TS) is useful in forecasting carbon intensity for a particular ISO

    # showTrends(dataset, dateTime, LOCAL_TIMEZONE)
    # print("Plotting each feature distribution...")
    # features = dataset.columns.values[START_COL:START_COL+NUM_FEATURES]
    # trainDataFrame = pd.DataFrame(trainData, columns=features)
    # createFeatureViolinGraph(features, trainDataFrame, dateTime)
    # print("***** Feature distribution plotting done *****")
    return

def checkStationarity(dataset):
    print(dataset.columns)
    columns = dataset.columns.values
    for i in range(CARBON_INTENSITY_COLUMN, len(columns)):
        # carbon = dataset["carbon_intensity"].values
        series = dataset[columns[i]].values
        # print(len(carbon))
        result = adfuller(series, autolag='AIC')
        print("Columns: ", columns[i])
        print(f'ADF Statistic: {result[0]}')
        print(f'n_lags: {result[1]}')
        print(f'p-value: {result[1]}')
        for key, value in result[4].items():
            print('Critial Values:')
            print(f'   {key}, {value}')
    return

def showTrends(dataset, dateTime, localTimeZone):
    carbon = np.array(dataset["carbon_intensity"].values)
    carbon = np.resize(carbon, (carbon.shape[0]//24, 24))
    dailyAvgCarbon = np.mean(carbon, axis = 1)
    dates = getDatesInLocalTimeZone(dateTime)    
    
    fig, ax = plt.subplots()
    ax.plot(dates, dailyAvgCarbon)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d, %H:%M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=MONTH_INTERVAL, tz=localTimeZone))
    
    plt.xlabel("Local time")
    plt.ylabel("Carbon Intensity (g/kWh)")
    # plt.title("Carbon Intensity Trend")
    plt.grid(axis="x")
    plt.xticks(rotation=90)

    plt.legend()
    # plt.show()
    return

def createFeatureViolinGraph(features, dataset, dateTime):
    plt.figure() #figsize=(12, 6)
    datasetMod = dataset.melt(var_name='Column', value_name='Normalized')
    ax = sns.violinplot(x='Column', y='Normalized', data=datasetMod, scale="count")
    # ax = plt.boxplot(dataset, vert=True)
    # for ft in features:
    #     print(ft, np.amax(dataset[ft].values), np.amin(dataset[ft].values))
    _ = ax.set_xticklabels(features, rotation=45)
    # plt.show()
    return

def showPlots():
    plt.show()
    return

def aggregateHalfHourlyData(origDataset):
    dataset = pd.DataFrame(np.empty((8760*2, len(origDataset.columns.values))) * np.nan,
                    columns=origDataset.columns.values)
    idx = 1
    dataset.iloc[0] = origDataset.iloc[0]
    for i in range(1, len(origDataset)):
        if((origDataset.iloc[i-1,0].minute == 30 and origDataset.iloc[i,0].minute == 0)
            or (origDataset.iloc[i-1,0].minute == 0 and origDataset.iloc[i,0].minute == 30)):
            dataset.iloc[idx] = origDataset.iloc[i]
        else:
            if((origDataset.iloc[i-1,0].minute == 30 and origDataset.iloc[i,0].minute == 30)):
                dataset.iloc[idx] = origDataset.iloc[i-1]
                dataset.iloc[idx, 0] = origDataset.iloc[i-1, 0] + pd.DateOffset(minutes=30)
                idx += 1
                dataset.iloc[idx] = origDataset.iloc[i]
            elif((origDataset.iloc[i-1,0].minute == 0 and origDataset.iloc[i,0].minute == 0)):
                dataset.iloc[idx] = origDataset.iloc[i]
                dataset.iloc[idx, 0] = origDataset.iloc[i-1, 0] + pd.DateOffset(minutes=30)
                idx += 1
                dataset.iloc[idx] = origDataset.iloc[i]
        idx += 1

    print(idx)

    idx = 0
    modifiedDataset = pd.DataFrame(np.empty((len(dataset)//2, len(dataset.columns.values))) * np.nan,
                    columns=dataset.columns.values)
    for i in range(0, len(dataset), 2):
        modifiedDataset.iloc[idx,0] = dataset.iloc[i+1, 0]
        for j in range(1, len(dataset.columns)):
                modifiedDataset.iloc[idx,j] = dataset.iloc[i,j]+dataset.iloc[i+1, j]
        idx += 1
    print(modifiedDataset.head())
    print(len(modifiedDataset))
    return modifiedDataset

def aggregate15MinDataDE(dataset):
    dataList = []
    col = dataset.columns.values
    for i in range(0, len(dataset), 4):
        tmpList = [None] * len(col)
        tmpList[0] = dataset.iloc[i+3, 0]
        for j in range(1, len(col)):
            tmpList[j] = dataset.iloc[i, j] + dataset.iloc[i+1, j] + dataset.iloc[i+2, j] + dataset.iloc[i+3, j]
        dataList.append(tmpList)
    modifiedDataset = pd.DataFrame(dataList, columns=col)
    return modifiedDataset

def removeDuplicateDataDE(dataset):
    print(len(dataset))
    dataList = []
    col = dataset.columns.values
    i = 0
    while (i<len(dataset)):
        for j in range(48):
            if(j<24):
                tmpList = []
                dataList.append(dataset.iloc[i+j])
        i+=48
    modifiedDataset = pd.DataFrame(dataList, columns=col)
    return modifiedDataset


idx=0
CARBON_INTENSITY_COLUMN = 1
ISO_LIST = ["PL"]
for iso in ISO_LIST:
    # IN_FILE_NAME = iso+"/fuel_forecast/"+iso+"_2019_clean.csv"
    IN_FILE_NAME = iso+"/"+iso+"_forecast_carbon_copy.csv"
    # IN_FILE_NAME = iso+"/"+iso+"_solar_wind_fcst_final.csv"
    OUT_FILE_NAME = iso+"/"+iso+"_forecast_carbon.csv"
    # IN_FILE_NAME = iso+"/"+iso+"_2019.csv"
    # OUT_FILE_NAME = iso+"/fuel_forecast/"+iso+"_2019_clean2.csv"
    startRow = 0 #START_ROW[iso]
    dataset = initialize(IN_FILE_NAME, startRow)

############### ZONE: DE start ###############
    # # modifiedDataset = aggregate15MinDataDE(dataset)
    # # modifiedDataset = removeDuplicateDataDE(dataset)
    # # modifiedDataset = calculateCarbonIntensity(dataset, carbonRate)
    # # modifiedDataset = calculateCarbonIntensityFromSourceForecasts(dataset, forcast_carbonRate, 3)
    # dataset = dataset[13128:] # from July 1 2021
    # dailyAvgMape, avgMape = getMape(dataset["UTC time"].values, dataset["carbon_intensity"].values, 
    #                 dataset["carbon_from_src_forecasts"].values)
    # for item in dailyAvgMape:
    #     print(item)
    # print("Mean MAPE: ", avgMape)
    # print("Median MAPE: ", np.percentile(dailyAvgMape, 50))
    # print("90th percentile MAPE: ", np.percentile(dailyAvgMape, 90))
    # print("95th percentile MAPE: ", np.percentile(dailyAvgMape, 95))
    # print("99th percentile MAPE: ", np.percentile(dailyAvgMape, 99))
    # # modifiedDataset.to_csv(OUT_FILE_NAME)
    # exit(0)
############### ZONE: DE end ###############

############### ZONE: SE start ###############
    # # modifiedDataset = calculateCarbonIntensityFromSourceForecasts(dataset, forcast_carbonRate, 4)
    # dataset = dataset[13128:] # from July 1 2021
    # dailyAvgMape, avgMape = getMape(dataset["UTC time"].values, dataset["carbon_intensity"].values, 
    #                 dataset["carbon_from_src_forecasts"].values)
    # for item in dailyAvgMape:
    #     print(item)
    # print("Mean MAPE: ", avgMape)
    # print("Median MAPE: ", np.percentile(dailyAvgMape, 50))
    # print("90th percentile MAPE: ", np.percentile(dailyAvgMape, 90))
    # print("95th percentile MAPE: ", np.percentile(dailyAvgMape, 95))
    # print("99th percentile MAPE: ", np.percentile(dailyAvgMape, 99))
    # # modifiedDataset.to_csv(OUT_FILE_NAME)
    # exit(0)
############### ZONE: SE end ###############

############### ZONE: ERCO start ###############
    # # modifiedDataset = calculateCarbonIntensityFromSourceForecasts(dataset, forcast_carbonRate, 4)
    # dataset = dataset[13128:] # from July 1 2021
    # dailyAvgMape, avgMape = getMape(dataset["UTC time"].values, dataset["carbon_intensity"].values, 
    #                 dataset["carbon_from_src_forecasts"].values)
    # for item in dailyAvgMape:
    #     print(item)
    # print("Mean MAPE: ", avgMape)
    # print("Median MAPE: ", np.percentile(dailyAvgMape, 50))
    # print("90th percentile MAPE: ", np.percentile(dailyAvgMape, 90))
    # print("95th percentile MAPE: ", np.percentile(dailyAvgMape, 95))
    # print("99th percentile MAPE: ", np.percentile(dailyAvgMape, 99))
    # # modifiedDataset.to_csv(OUT_FILE_NAME)
    # exit(0)
############### ZONE: ERC end ###############



    # hourlyDateTime = createHourlyTimeCol(dataset, dataset["UTC time"].values, "2020-01-01T00:00")
    # dataset["UTC time"] = hourlyDateTime
    # # modifiedDataset = aggregateHalfHourlyData(dataset)
    # modifiedDataset.to_csv(OUT_FILE_NAME)
    # # print(len(modifiedDataset))
    # # modifiedDataset = fillMissingHours(modifiedDataset, modifiedDataset["UTC time"].values, hourlyDateTime)
    # # print(len(modifiedDataset))
    # exit(0)
    # print(len(modifiedDataset))
    # hourlyDateTime = createHourlyTimeCol(dataset, dataset["Local time"].values, "2019-01-01T00:00")
    # localTime = createHourlyTimeCol(dataset, dataset["Local time"].values, "2019-01-01T01:00")
    # modifiedDataset.insert(0, "datetime", hourlyDateTime)
    # modifiedDataset["Local time"] = localTime
    # modifiedDataset.index = hourlyDateTime
    # print(modifiedDataset.head())
    # print(modifiedDataset.tail())
    # modifiedDataset.to_csv(IN_FILE_NAME)
    # exit(0)
    dataset = calculateCarbonIntensity(dataset, carbonRate)
    # dataset = addDayAheadForecastColumns(dataset, 0.1)
    # print(dataset.head())
    dataset.to_csv(OUT_FILE_NAME)
    
    # inFileName = "dataset/"+iso+"_clean.csv"
    # dataset, dateTime = readFile(inFileName)
    # print("ISO: ", iso)
    # # analyzeTimeSeries(dataset, None, None, dateTime)
    # showDailyAverageCarbon(dataset, dateTime, pytz.timezone(LOCAL_TIMEZONES[idx]), iso)
    # print(iso, " Analyzed")
    idx+=1
# showPlots()


