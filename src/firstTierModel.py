#import the libraries 
import sklearn 
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
import xgboost as xbg 
from xgboost import XGBRegressor

#neural networks libraries 
from keras.layers import Dense, Flatten, LSTM, Input, MultiHeadAttention, LayerNormalization, GRU, SimpleRNN
from keras.layers import Conv1D, MaxPooling1D
from keras.layers import Activation, Dropout, Add
from keras.models import Sequential, Model
from keras.regularizers import l2
import tensorflow as tf
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.models import load_model, save_model
from keras.layers import RepeatVector
import statsmodels.api as sm 
import common 

                                                            ### FIRST TIER BACKUPS ###
                                                            # bestTrainedModel = firstTierModel.train(, "lstm")

def getHyperParams(firstTierConfig):
    hyperParams = {}
    modelHyperparamsFromConfigFile = firstTierConfig["FIRST_TIER_ANN_MODEL_HYPERPARAMS"]
    hyperParams["epoch"] = modelHyperparamsFromConfigFile["EPOCH"]
    hyperParams["batchsize"] = modelHyperparamsFromConfigFile["BATCH_SIZE"]
    hyperParams["actv"] = modelHyperparamsFromConfigFile["ACTIVATION_FUNC"]
    hyperParams["loss"] = modelHyperparamsFromConfigFile["LOSS_FUNC"]
    hyperParams["lr"] = modelHyperparamsFromConfigFile["LEARNING_RATE"]
    hyperParams["hidden"] = modelHyperparamsFromConfigFile["HIDDEN_UNITS"]
    hyperParams["input_shape"] = modelHyperparamsFromConfigFile["INPUT_SHAPE"]
    hyperParams["numheads"] = modelHyperparamsFromConfigFile["NUM_HEADS"]
    hyperParams["ffdim"] = modelHyperparamsFromConfigFile["FF_DIM"]
    hyperParams["dropout"] = modelHyperparamsFromConfigFile["DROPOUT"]
    hyperParams["n_estimators"] = modelHyperparamsFromConfigFile["N_ESTIMATORS"]
    return hyperParams


def trainfirstTier(trainX, trainY, valX, valY, hyperParams, savedModelLocation, region, source, model_option):
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    epochs = hyperParams["epoch"]
    batchSize = hyperParams["batchsize"]
    lossFunc = hyperParams["loss"]
    actvFunc = hyperParams["actv"]
    hiddenDims = hyperParams["hidden"]
    learningRates = hyperParams["lr"]
    inputShape = hyperParams["input_shape"]
    numHeads = hyperParams["numheads"]
    ffDim = hyperParams["ffdim"]
    dropoutRate = hyperParams["dropout"]
    nEstimators = hyperParams['n_estimators']

    if model_option.lower() in ['gru', 'rnn', 'lstm', 'mlp', 'transformers']:
        if model_option.lower() == 'gru':
            model = train_GRU(n_timesteps, n_features, hiddenDims, actvFunc, n_outputs)
        elif model_option.lower() == 'rnn':
            model = train_RNN(n_timesteps, n_features, hiddenDims, actvFunc, n_outputs)
        elif model_option.lower() == 'lstm':
            model = train_LSTM(n_timesteps, n_features, hiddenDims, actvFunc, n_outputs)
        elif model_option.lower() == 'mlp':
            if source in ['HYDRO', 'SOLAR', 'WIND']:
                inputShape = [24, 11]
            else:
                inputShape = [24, 6]
            model = train_MLP(inputShape, hiddenDims, actvFunc, n_outputs)
        elif model_option.lower() == 'transformers':
            model = train_Transformers(n_timesteps, n_features, hiddenDims, actvFunc, n_outputs, numHeads, ffDim, dropout_rate=dropoutRate)

        opt = tf.keras.optimizers.Adam(learning_rate=learningRates)
        model.compile(loss=lossFunc, optimizer=opt, metrics=["mean_absolute_error"])
        es = EarlyStopping(monitor="val_loss", mode="min", verbose=1, patience=10)
        mc = ModelCheckpoint(savedModelLocation + region + "_" + source + "_best_model_ann.h5", monitor="val_loss", mode="min", verbose=1, save_best_only=True)

        hist = model.fit(trainX, trainY, epochs=epochs, batch_size=batchSize[0], verbose=2, validation_data=(valX, valY), callbacks=[es, mc])
        model = load_model(savedModelLocation + region + "_" + source + "_best_model_ann.h5")
        common.showModelSummary(hist, model)
        print("Number of features used in training: ", n_features)

    elif model_option.lower() in ['rf', 'xgb']:
        trainX_reshaped = trainX.reshape(trainX.shape[0], -1)  # Reshape for machine learning models
        valX_reshaped = valX.reshape(valX.shape[0], -1)

        if model_option.lower() == 'rf':
            model = train_rf(trainX_reshaped, trainY, nEstimators, random_state=42)
        elif model_option.lower() == 'xgb':
            model = train_xgb(trainX_reshaped, trainY, learningRates, nEstimators, random_state=42)

        model.fit(trainX_reshaped, trainY)
        print("Number of features used in training: ", n_features)

    else:
        print("No model is found in selection, please choose among gru, rnn, lstm, mlp, transformers, rf, or xgb")
        return None 
    
    return model


# GRU 
def train_GRU(n_timesteps,n_features,hiddenDims,actvFunc,n_outputs):
    model = Sequential()
    model.add(GRU(hiddenDims[0],input_shape=(n_timesteps,n_features),activation=actvFunc,return_sequences=True))
    model.add(GRU(hiddenDims[1],activation=actvFunc))
    model.add(Dense(n_outputs))
    return model 

# RNN 
def train_RNN(n_timesteps,n_features,hiddenDims,actvFunc,n_outputs):
    model = Sequential()
    model.add(SimpleRNN(hiddenDims[0],input_shape=(n_timesteps,n_features),activation=actvFunc,return_sequences=True))
    model.add(SimpleRNN(hiddenDims[1],activation=actvFunc))
    model.add(Dense(n_outputs))
    return model 

# LSTM 
def train_LSTM(n_timesteps,n_features,hiddenDims,actvFunc,n_outputs):
    model = Sequential()
    model.add(LSTM(hiddenDims[0],input_shape=(n_timesteps,n_features),activation=actvFunc,return_sequences=True))
    model.add(LSTM(hiddenDims[1],activation=actvFunc))
    model.add(Dense(n_outputs))
    return model 

# MLP
def train_MLP(input_shape, hiddenDims, actvFunc, n_outputs):
    model = Sequential()
    model.add(Flatten(input_shape=input_shape))
    model.add(Dense(hiddenDims[0],activation=actvFunc))
    model.add(Dense(hiddenDims[1],activation=actvFunc))
    model.add(Dense(n_outputs))
    return model 


# SARIMA 
# def train_SARIMA(time_series,order,seasonal_order):
    model = sm.tsa.statespace.SARIMAX(time_series,order=order,seasonal_order=seasonal_order)
    prediction = model.fit()
    return prediction

# Transformers
def train_Transformers(n_timesteps, n_features, hiddenDims, actvFunc, n_outputs, num_heads, ff_dim, dropout_rate=0.1):
    model = Sequential()

    input_layer = tf.keras.layers.Input(shape=(n_timesteps, n_features))
    attn_output = MultiHeadAttention(num_heads=num_heads, key_dim=n_features)(input_layer, input_layer)
    attn_output = Dropout(dropout_rate)(attn_output)
    out1 = Add()([input_layer, attn_output])
    out1 = LayerNormalization(epsilon=1e-6)(out1)

    ffn_output = Dense(ff_dim, activation=actvFunc)(out1)
    ffn_output = Dense(n_features)(ffn_output)
    ffn_output = Dropout(dropout_rate)(ffn_output)
    out2 = Add()([out1, ffn_output])
    out2 = LayerNormalization(epsilon=1e-6)(out2)

    model.add(tf.keras.Model(inputs=input_layer, outputs=out2))
    model.add(Flatten())
    model.add(Dense(hiddenDims[0], activation=actvFunc)) 
    model.add(Dense(hiddenDims[1], activation=actvFunc)) 
    model.add(Dense(n_outputs))
    return model

# Random Forest 
def train_rf(X_train,y_train,n_estimators,random_state=42):
    if len(X_train.shape) > 2:
        X_train= X_train.reshape(X_train.shape[0], -1)    
    model = RandomForestRegressor(n_estimators=n_estimators,random_state=random_state)
    model.fit(X_train,y_train)
    return model

# XGBoost
def train_xgb(X_train,y_train,learning_rate,n_estimators,random_state=42): 
    model = XGBRegressor(learning_rate=learning_rate,n_estimators=n_estimators,random_state=random_state)
    model.fit(X_train,y_train)
    return model 