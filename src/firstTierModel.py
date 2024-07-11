#import the libraries 
import sklearn 
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.svm import SVR

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

                            ### FIRST TIER BACKUPS ###

# GRU 
def train_GRU(n_timesteps,n_features,hiddenDims,actvFunc,n_outputs):
    model = Sequential()
    model.add(GRU(hiddenDims[0],input_shape=(n_timesteps,n_features),activation=actvFunc,return_sequences=True))
    model.add(GRU(hiddenDims[1],activation=actvFunc))
    model.add(Dense(n_outputs))
    return model 

# RNN 
def train_RNN(n_timesetps,n_features,hiddenDims,actvFunc,n_outputs):
    model = Sequential()
    model.add(SimpleRNN(hiddenDims[0],input_shape=(n_timesetps,n_features),activation=actvFunc,return_sequences=True))
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
    model.add(Flatten(input_shape=(input_shape)))
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