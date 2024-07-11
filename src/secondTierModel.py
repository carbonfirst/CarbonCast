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
import tensorflow as tf
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.models import load_model, save_model
from keras.layers import RepeatVector
import statsmodels.api as sm 

                            ### Second Tier Model Backup ###

#Base Model - Original + SVM 
def CNN_Hybird_SVM():
    svm_model = make_pipeline(StandardScaler(),SVR(kernel='rbf'))
    svm_model.fit(X_train,y_train)

    train_features = svm_model.predict(X_train)
    test_features = svm_model.predict(X_test)

    model = Sequential()
    model.add(Conv1D(filters=numFilters1, kernel_size=kernel1Size, padding="same",
                activation=activationFunc, input_shape=(n_timesteps,n_features)))
    model.add(MaxPooling1D(pool_size=cnnPoolSize))
    model.add(Conv1D(filters=numFilters2, kernel_size=kernel2Size,
                activation=activationFunc, input_shape=(n_timesteps,n_features)))
        
    model.add(Flatten())
    model.add(RepeatVector(n_outputs))
    model.add(LSTM(n_outputs))
    model.add(Dropout(dropoutRate))
    model.add(Dense(n_outputs))

    model.compile(optimizer='adam',loss='mse')
    model.fit(train_features,y_train,epochs=numEpochs,batch_size=batchSize)

    y_pred = svm_model.predict(test_features)
    print(y_pred)

# Model 2 - Transformer + Ridge
def transformer_encoder(inputs, head_size, num_heads, ff_dim, dropout=0):
    x = MultiHeadAttention(key_dim=head_size, num_heads=num_heads)(inputs, inputs)
    x = Dropout(dropout)(x)
    x = LayerNormalization(epsilon=1e-6)(x)
    res = x + inputs

    x = Dense(ff_dim, activation="relu")(res)
    x = Dropout(dropout)(x)
    x = Dense(inputs.shape[-1])(x)
    x = LayerNormalization(epsilon=1e-6)(x)
    return x + res

def Transformer_Ridge():
    ridge_model = make_pipeline(StandardScaler(), Ridge())
    ridge_model.fit(X_train,y_train)

    train_features = ridge_model.predict(X_train_ridge).reshape(-1, 1, 1)
    test_features = ridge_model.predict(X_test_ridge).reshape(-1, 1, 1)

    input_shape = (1, 1)
    inputs = Input(shape=input_shape)
    x = transformer_encoder(inputs, head_size=256, num_heads=4, ff_dim=4, dropout=0.1)
    x = Flatten()(x)
    x = Dense(n_outputs)(x)

    transformer_model = Model(inputs, x)
    transformer_model.compile(optimizer='adam', loss='mse')
    transformer_model.fit(train_features, y_train, epochs=numEpochs, batch_size=batchSize, verbose=0)

    y_pred = transformer_model.predict(test_features)




# Model 3 - Seq2Seq + Decision Tree
def Seq2_Decision_Tree():
    dt_model = DecisionTreeRegressor()
    dt_model.fit(X_train,y_train)

    train_features = dt_model.predict(X_train).reshape()
    test_features = dt_model.predict(X_test).reshape()

    encoder_inputs = Input(shape(1,1))
    encoder = LSTM(lstm_unit,return_state=True)
    encoder_outputs,state_h,state_c = encoder(encoder_inputs)
    encoder_states = [state_h,state_c]

    decoder_inputs = Input(shape=(1,1))
    decoder_lstm = LSTM(lstm_units,return_sequences=True,return_state=True)
    decoder_outputs, _, _, = decoder_lstm(decoder_inputs,initial_state=encoder_states)
    decoder_dense = Dense(n_outputs,activation=activationFunc)

    seq2seq_model = Model([encoder_inputs,decoder_inputs],decoder_outputs)
    seq2seq_model.compile(optimizer='adams',loss='mse')


# Model 4 - LSTM + Random Forest 
def LSTM_RF():

    rf_model = RandomForestRegressor(n_estimators=estimators)
    rf_model.fit(x_train,y_train)

    train_features = rf_model.predict(X_train).reshape(-1,1)
    testfeatures = rf_model.predict(X_test).reshape(-1,1)

    model = Sequential(lstm_unit,activationFunc,n_timesteps,n_features,dense_unit)
    model.add(LSTM(lstm_unit,activation=activationFunc,input_shape=(n_timesteps,n_features)))
    model.add(Dense(dense_unit))
    model.complie(optimizer='adam',loss='mse')
    model.fit(X_train,y_train,epochs=numEpochs,batch_size=batchSize)

    y_pred = model.predict(test_features)

    print(y_pred)

# Model 5 - Transformer + GRU 
def transformer_encoder(inputs, head_size, num_heads, ff_dim, dropout=0):
    x = MultiHeadAttention(key_dim=head_size, num_heads=num_heads)(inputs, inputs)
    x = Dropout(dropout)(x)
    x = LayerNormalization(epsilon=1e-6)(x)
    res = x + inputs

    x = Dense(ff_dim, activation="relu")(res)
    x = Dropout(dropout)(x)
    x = Dense(inputs.shape[-1])(x)
    x = LayerNormalization(epsilon=1e-6)(x)
    return x + res

input_shape = (n_timesteps, n_features)
inputs = Input(shape=input_shape)
x = transformer_encoder(inputs, head_size=head_size, num_heads=num_heads, ff_dim=ff_dim, dropout=dropout)
x = GRU(gruUnits, activation='relu')(x)
x = Flatten()(x)
outputs = Dense(n_outputs)(x)

model = Model(inputs, outputs)
model.compile(optimizer='adam', loss='mse')
model.fit(X_train, y_train, epochs=numEpochs, batch_size=batchSize, verbose=0)

y_pred = model.predict(X_test)
