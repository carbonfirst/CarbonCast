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
# import tensorflow as tf
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
ISO = "DE"
IN_FILE_NAME = None
OUT_FILE_NAME = None

DAY_INTERVAL = 1
MONTH_INTERVAL = 1



def initialize(inFileName, startRow):
    # load the new file
    print("FILE: ", inFileName)
    # dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
    #                          parse_dates=["UTC time"])
    dataset = pd.read_csv(inFileName, header=0)
    return dataset

def plotCDF(dataset):
    # plt.hist(dataset["CNN"].values, bins=20, density=True, cumulative=True, label='CDF DATA', 
    #      histtype='step', alpha=0.55, color='purple')
    print(dataset.columns.values)
    count, bins_count = np.histogram(dataset["CNN"].values, bins=20, density=True)
    pdf = count / sum(count)
    cdf = np.cumsum(pdf)
    plt.plot(bins_count[1:], cdf, label="CarbonCastCNN", linewidth = 8, color="k")
    count, bins_count = np.histogram(dataset["ANN"].values, bins=20, density=True)
    pdf = count / sum(count)
    cdf = np.cumsum(pdf)
    plt.plot(bins_count[1:], cdf, label="NH-1", linestyle="dashed", linewidth = 8, color="r")
    plt.xlabel("MAPE (%)", fontsize=20)
    plt.ylabel("CDF", fontsize=20)
    plt.legend(fontsize=19)
    plt.yticks(np.arange(0.0, 1.1, 0.1), fontsize=19)
    plt.xticks(fontsize=19)
    plt.grid(axis="y")
    plt.show()    
    return

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
        # print(x)
        # print(y)
        # overlay median value
        plt.text(x, y, '%.1f' % y,
            horizontalalignment='center', fontsize=12) # draw above, centered

    # for line in bp_dict['boxes']:
    #     x, y = line.get_xydata()[0] # bottom of left line
    #     plt.text(x,y, '%.1f' % y,
    #         horizontalalignment='center', # centered
    #         verticalalignment='top')      # below
    #     x, y = line.get_xydata()[3] # bottom of right line
    #     plt.text(x,y, '%.1f' % y,
    #         horizontalalignment='center', # centered
    #             verticalalignment='top')      # below
    plt.xlabel("Zones/ISOs", fontsize=20)
    plt.ylabel("MAPE (%)", fontsize=20)
    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    # plt.title("MAPE boxplots")
    # plt.grid(axis="x")
    plt.show()
    return

def plotLineGraphs(actualVal, predictedVal, testDates, predictedValWithoutForecasts = None):
        
    fig, ax = plt.subplots()
    ax.plot(testDates, actualVal, label="Actual carbon intensity", color="k")
    ax.plot(testDates, predictedVal, label="Predicted (with forecast features)", color="b")
    if predictedValWithoutForecasts is not None:
        ax.plot(testDates, predictedValWithoutForecasts, label="Predicted (without forecast features)", color='r')
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    # ax.xaxis.set_major_locator(mdates.HourLocator(interval=12, tz=pytz.timezone("US/Pacific")))
    # ax.set_ylim(ymin=0)
    # ax.set_ylim(ymax=450)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=pytz.timezone("US/Pacific")))
    
    # plt.xlabel("Local time")
    plt.xlabel("Local Time")
    plt.ylabel("Carbon Intensity (g/KWh)")
    plt.title("Predictions with & without forecasts as features")
    plt.grid(axis="x")
    plt.xticks(rotation=45)
    # plt.xticks(np.arange(0, 73, 12.0))

    plt.legend()
    plt.show()
    return

def plotDailyFuelMix(dataset):
    columns = dataset.columns.values
    sources = columns[2:]
    x = dataset["Local time"].values
    y = np.transpose(dataset.iloc[:, 2:])

    fig, ax = plt.subplots()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    pal = ["#ef6b6b", "#d08e59", "#611319", "#736047",
            "#adc0f3", "#fee675", "#60b45d", "#828e9a"]
    ax.set_ylabel("Electricity generated (MWh)", fontsize=19)
    ax.set_xlabel("Local Time", fontsize=19)
    # ax.grid(axis="x")
    ax.tick_params(axis="x", labelsize=18, labelrotation=30)
    ax.tick_params(axis="y", labelsize=18)
    # ax.set_yticks(fontsize=16)
    lns1 = ax.stackplot(x, y, labels=sources, colors=pal)
    # ax.legend(loc='lower center', ncol=4)

    ax2 = ax.twinx()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax2.set_ylabel("Carbon Intensity (g/KWh)", fontsize=19)
    ax2.tick_params(axis="y", labelsize=18)
    lns2 = ax2.plot(x, dataset["carbon_intensity"].values, "k--", label="carbon intensity", linewidth=2)
    lns = lns1+lns2
    labs = [l.get_label() for l in lns]
    ax2.legend(lns, labs, bbox_to_anchor=(0.5, 1), loc='lower center', ncol=5, framealpha=0.3, fontsize=19)
    # ax2.legend()



    # plt.xlabel("Local Time")
    # plt.ylabel("Carbon Intensity (g/KWh)")
    # plt.ylabel("Electricity generated (MWh)")
    plt.xticks(rotation=45)
    
    # plt.legend(loc='lower center', ncol=4)
    plt.show()
    return

def plotPercentageBarGraph(dataset):
    x = dataset["ISO"].values
    col = dataset.columns.values
    r=[6,5,4,3,2,1,0]
    x[1] = "Pennsylvania-Jersey-\n-Maryland (PJM)"
    x[3] = "New England (ISO-NE)"
    barWidth = 0.85
    pal = ["#ef6b6b", "#d08e59", "#611319", "#736047", "#efc9cc",
            "#c0fe8b", "#adc0f3", "#fee675", "#60b45d", "#828e9a"]
    patterns = [ "/" , "\\" , "|" , "-" , "+" , "x", "o", "O", ".", "*" ]
    plt.barh(r, dataset.iloc[:, 1], edgecolor='black', height=0.6, color=pal[0],
                label=col[1]) #hatch=patterns[0], width=barWidth, 
    ypos = dataset.iloc[:, 1].values
    for i in range(2,len(col)):
        plt.barh(r, dataset.iloc[:, i], left=ypos, edgecolor='black', height=0.6, color=pal[i-1],
                label=col[i]) #, width=barWidth, 
        for j in range(len(ypos)):
            ypos[j] += dataset.iloc[j, i]
    plt.yticks(r, x, fontsize=19, rotation=30)
    plt.xticks(fontsize=16)
    # plt.ylabel("ISO")
    plt.xlabel("Electricity generation (%)", fontsize=20)
    plt.legend(loc='lower center', bbox_to_anchor=(0.4,1), ncol=5, framealpha=0.3, fontsize=21)
    plt.show()
    return

def plotScatterPlot(dataset):
    x = dataset["weighted avg error"].values
    y = dataset["carbon error"].values
    pal = ["#ef6b6b", "#d08e59", "#611319", "#736047", "#efc9cc",
            "#c0fe8b", "#adc0f3", "#fee675", "#60b45d", "#828e9a"]
    patterns = [ "/" , "\\" , "|" , "-" , "+" , "x", "o", "O", ".", "*" ]
    plt.scatter(x, y)
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    plt.plot(x,p(x),"r--")

    plt.yticks(fontsize=21)
    plt.xticks(fontsize=21)
    plt.ylim(bottom=0)
    plt.xlim(left=0)
    # plt.ylabel("ISO")
    plt.xlabel("Avg source production forecast error (%)", fontsize=22)
    plt.ylabel("Carbon intensity prediction error (%)", fontsize=22)
    # plt.legend(loc='lower center', bbox_to_anchor=(0.4,1), ncol=5, framealpha=0.3, fontsize=21)
    plt.show()
    return

def plotBarGraphsFeature():
    xLabel = ["crbn", "h_sin", "h_cos", "nuclear", "wind_speed", "dswrf", "precip",
            "coal_fcst", "nat_gas_fcst", "wind_fcst"]
    yValues = [0.20044158, 0.11322591, 0.12514174, -0.10464927, -0.102419615, -0.086386256, 0.10588705, 0.10559652, 0.3086214, -0.33092508]
    plt.figure()
    plt.bar(range(len(yValues)), yValues, color=(0.1, 0.1, 0.1, 0.1), width=0.4, edgecolor='blue')
    # plt.xticks(range(len(featureList)), featureList, rotation=90)
    plt.xticks(range(len(xLabel)), xLabel, rotation=75, fontsize=21)
    plt.yticks(fontsize=20)
    for i in range(len(yValues)):
        plt.text(i-0.4,yValues[i],round(yValues[i], 2), fontsize=16)
    plt.axhline(y=0, color='k')
    plt.ylabel('Gradients', fontsize=22) 
    # plt.xlabel('Features', fontsize=22)
    plt.show()    
    return

def plotBarGraphsForecastOutlier(dataset):

    N = 3
    ind = np.arange(N) 
    width = 0.1
    xLabel = ["11/07/21", "12/24/21", "12/26/21"]
    pal = ["#ef6b6b", "#d08e59", "#611319", "#736047",
            "#adc0f3", "#fee675", "#60b45d", "#828e9a"]

    plt.figure
    
    patterns = [ "/" , "\\" , "|" , "-" , "+" , "x", "o", "O", ".", "*" ]

    orig = dataset["original"]
    bar1 = plt.bar(ind, orig, width, color = 'k')
    
    wind = dataset["wind"]
    bar2 = plt.bar(ind+width, wind, width, color="#60b45d", hatch="/")
    
    nat_gas = dataset["nat_gas"]
    bar3 = plt.bar(ind+width*2, nat_gas, width, color="#d08e59", hatch="-")

    coal = dataset["coal"]
    bar4 = plt.bar(ind+width*3, coal, width, color="#611319", hatch=".")

    all = dataset["all"]
    bar5 = plt.bar(ind+width*4, all, width, color='w', edgecolor="k", hatch="\\")
    
    
    plt.xticks(ind+width*2, xLabel, fontsize=21)
    plt.yticks(fontsize=20)
    # plt.show()

    
    
    # plt.xticks(range(len(featureList)), featureList, rotation=90)
    # ax.set_xticklabels(xLabel)
    # ax.tick_params(axis="x", labelsize=21)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # ax.tick_params(axis="y", labelsize=20)
    # for i in range(len(y1)):
    #     plt.text(i,y1[i],round(y1[i], 2), fontsize=16)
    plt.ylabel('MAPE (%)', fontsize=22) 
    plt.xlabel('Outlier days', fontsize=22)
    plt.legend( (bar1, bar2, bar3, bar4, bar5), 
            ("Original forecasts", "Ideal wind", "Ideal nat_gas", "Ideal coal", "All ideal"), fontsize=17,
            bbox_to_anchor=(0.5, 0.95), loc='lower center', ncol=3, framealpha=0.3 )
    plt.show() 
    return


def plotBarGraphsForecastOverall(dataset):

    N = 4
    ind = np.arange(N) 
    width = 0.1
    xLabel = ["Mean", "Median", "90th \npercentile", "95th \npercentile"]
    pal = ["#ef6b6b", "#d08e59", "#611319", "#736047",
            "#adc0f3", "#fee675", "#60b45d", "#828e9a"]

    plt.figure
    
    patterns = [ "/" , "\\" , "|" , "-" , "+" , "x", "o", "O", ".", "*" ]

    orig = dataset["original"]
    bar1 = plt.bar(ind, orig, width, color = 'k')
    
    wind = dataset["wind"]
    bar2 = plt.bar(ind+width, wind, width, color="#60b45d", hatch="/")
    
    nat_gas = dataset["nat_gas"]
    bar3 = plt.bar(ind+width*2, nat_gas, width, color="#d08e59", hatch="-")

    coal = dataset["coal"]
    bar4 = plt.bar(ind+width*3, coal, width, color="#611319", hatch=".")

    all = dataset["all"]
    bar5 = plt.bar(ind+width*4, all, width, color='w', edgecolor="k", hatch="\\")
    
    
    plt.xticks(ind+width*2, xLabel, fontsize=21, rotation=30)
    plt.yticks(fontsize=20)
    plt.ylabel('MAPE (%)', fontsize=22) 
    # plt.xlabel('Overall', fontsize=22)
    plt.legend( (bar1, bar2, bar3, bar4, bar5), 
            ("Original forecasts", "Ideal wind", "Ideal nat_gas", "Ideal coal", "All ideal"), fontsize=17,
            bbox_to_anchor=(0.5, 0.95), loc='lower center', ncol=3, framealpha=0.3 )
    plt.show() 
    return

def plotTimeSeries(dataset):
    fig, ax = plt.subplots()
    x=dataset["UTC time"].values
    actual=dataset["actual"].values
    cnn=dataset["carboncastcnn"].values
    lr=dataset["carboncastlr"].values
    ax.plot(x, actual, label="Actual", color="k")
    ax.plot(x, cnn, label="CarbonCastCNN", color="r", 
            linestyle="dashed", linewidth=3)
    ax.plot(x, lr, label="CarbonCastLR", color="g", 
            linestyle="dotted", linewidth=4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=pytz.timezone("US/Pacific")))
    
    # plt.xlabel("Local time")
    # plt.xlabel("Local Time", fontsize=19)
    plt.ylabel("Avg Carbon Intensity (g/KWh)", fontsize=21)
    # plt.title(plotTitle)
    plt.grid(axis="x")
    plt.xticks(rotation=45, fontsize=18)
    plt.yticks(fontsize=18)
    # plt.xticks(np.arange(0, 73, 12.0))

    plt.legend(fontsize=18, bbox_to_anchor=(0.5, 1), ncol=3, loc='lower center')
    plt.show()
    return

def plotSrcVariations(natGas, renewables, generation, x):
    fig, ax = plt.subplots()

    natGas = natGas[24*30*8: 24*30*9]
    renewables = renewables[24*30*8: 24*30*9]
    generation = generation[24*30*8: 24*30*9]
    x = x[24*30*8: 24*30*9]


    # sources = ["Nat gas", "Renewables"]
    # y = np.transpose(np.column_stack((natGas, renewables)))

    # fig, ax = plt.subplots()
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # pal = ["#d08e59", "#60b45d"]
    # ax.set_ylabel("Electricity generated (MWh)", fontsize=19)
    # ax.set_xlabel("Local Time", fontsize=19)
    # # ax.grid(axis="x")
    # ax.tick_params(axis="x", labelsize=18, labelrotation=30)
    # ax.tick_params(axis="y", labelsize=18)
    # # ax.set_yticks(fontsize=16)
    # lns1 = ax.stackplot(x, y, labels=sources, colors=pal)
    # # ax.legend(loc='lower center', ncol=4)

    # ax2 = ax.twinx()
    # ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # ax2.set_ylabel("Total generation (MWh)", fontsize=19)
    # ax2.tick_params(axis="y", labelsize=18)
    # lns2 = ax2.plot(x, generation, "k--", label="Total generation")
    # lns = lns1+lns2
    # labs = [l.get_label() for l in lns]
    # ax2.legend(lns, labs, bbox_to_anchor=(0.5, 1), loc='lower center', ncol=5, framealpha=0.3, fontsize=19)



    ax.plot(x, generation, label="Generation", color="#bcbcbc")
    ax.plot(x, natGas, label="Nat gas", color="r")
    ax.plot(x, renewables, label="Renewables", color="g")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # ax.xaxis.set_major_locator(mdates.MonthLocator(interval=MONTH_INTERVAL, tz=pytz.timezone("US/Pacific")))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=pytz.timezone("US/Pacific")))
    
    # plt.xlabel("Local time")
    # plt.xlabel("Local Time", fontsize=19)
    plt.ylabel("Electricity (MW)", fontsize=21)
    # plt.title(plotTitle)
    plt.grid(axis="x")
    plt.xticks(rotation=45, fontsize=18)
    plt.yticks(fontsize=18)

    plt.legend(fontsize=18, bbox_to_anchor=(0.5, 1), ncol=3, loc='lower center')
    plt.show()



idx=0
CARBON_INTENSITY_COLUMN = 3
ISO_LIST = ["CISO"]
# for iso in ISO_LIST:
#     # IN_FILE_NAME = iso+"/fuel_forecast/"+iso+"_2019_clean.csv"
    # IN_FILE_NAME = "./"+iso+"/"+iso+"_plot.csv"
#     # IN_FILE_NAME = iso+"/"+iso+"_solar_wind_fcst_final.csv"
#     # OUT_FILE_NAME = iso+"/"+iso+"_src_forecast_carbon_out_woOther.csv"
#     # IN_FILE_NAME = iso+"/"+iso+"_2019.csv"
#     # OUT_FILE_NAME = iso+"/fuel_forecast/"+iso+"_2019_clean2.csv"
    # startRow = 0 #START_ROW[iso]
    # dataset = initialize(IN_FILE_NAME, startRow)
    # plotCDF(dataset)
#     # dailyMapeDict = {}
#     # for col in dataset.columns:
#     #     dailyMapeDict[col] = dataset[col].values
#     # plotBoxplots(dailyMapeDict)

    
# ############ ERCO plots start ############
# iso = "ERCO"
# IN_FILE_NAME = "./"+iso+"/"+iso+"_forecast_plot.csv"
# dataset = initialize(IN_FILE_NAME, startRow)
# plotLineGraphs(dataset["Actual"].values, dataset["Predicted (with forecasts as features)"].values, 
#             dataset["Local time"].values, dataset["Predicted (without forecast as features)"].values)

# IN_FILE_NAME = "./"+iso+"/"+iso+"_scatter_plot.csv"
# dataset = initialize(IN_FILE_NAME, 0)
# plotScatterPlot(dataset)

# plotBarGraphsFeature()

# IN_FILE_NAME = "./"+iso+"/"+iso+"_outlier_plot.csv"
# dataset = pd.read_csv(IN_FILE_NAME, header=0, infer_datetime_format=True, 
#                             parse_dates=["outlier"])
# plotBarGraphsForecastOutlier(dataset)

# IN_FILE_NAME = "./"+iso+"/"+iso+"_ideal_forecast_plot.csv"
# dataset = pd.read_csv(IN_FILE_NAME, header=0)
# plotBarGraphsForecastOverall(dataset)

# ############ ERCO plots end ############

# ############ CISO plots start ############
# iso = "CISO"
# IN_FILE_NAME = "./"+iso+"/"+iso+"_daily_fuel_mix.csv"
# dataset = initialize(IN_FILE_NAME, startRow)
# plotDailyFuelMix(dataset)

# IN_FILE_NAME = "./"+iso+"/"+iso+"_time_series.csv"
# dataset = initialize(IN_FILE_NAME, 0)
# plotTimeSeries(dataset)
# ############ CISO plots end ############

############ General plots start ############
IN_FILE_NAME = "../data/"+ISO_LIST[0]+"/"+ISO_LIST[0]+"_source_mix.csv"
dataset = pd.read_csv(IN_FILE_NAME, header = 0, infer_datetime_format=True, parse_dates=["UTC time"])
natGas = dataset["nat_gas"].values
generation = dataset["net_generation"].values
solar = dataset["solar"].values
solar = np.asarray(solar, dtype=np.float64)
wind = dataset["wind"].values
wind = np.asarray(wind, dtype=np.float64)
hydro = dataset["hydro"].values
hydeo = np.asarray(hydro, dtype=np.float64)
renewables = np.add(solar, wind)
renewables = np.add(renewables, hydro)
plotSrcVariations(natGas, renewables, generation, dataset["UTC time"].values)

# IN_FILE_NAME = "../general_plots/ISO_source_contrib.csv"
# dataset = pd.read_csv(IN_FILE_NAME, header=0)
# plotPercentageBarGraph(dataset)

# IN_FILE_NAME = "../general_plots/ISO_mape.csv"
# dataset = pd.read_csv(IN_FILE_NAME, header=0)
# isoDailyMape = {}
# col = dataset.columns.values
# for i in range(len(col)):
#     isoDailyMape[col[i]] = dataset[col[i]].values
# plotBoxplots(isoDailyMape)
############ General plots end ############

############ DE plots start ############
# iso = "DE"
# IN_FILE_NAME = "./"+iso+"/"+iso+"_scatter_plot.csv"
# dataset = initialize(IN_FILE_NAME, 0)
# plotScatterPlot(dataset)
############ DE plots end ############
    
    
    			



