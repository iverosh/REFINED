import csv
import numpy as np
import pandas as pd
import os
import scipy as sp
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
import cv2
import pickle
from Toolbox import NRMSE, Random_Image_Gen, two_d_norm, two_d_eq, Assign_features_to_pixels, MDS_Im_Gen, Bias_Calc, REFINED_Im_Gen

##########################################
#                                        #                                              
#                                        #                               
#               Data Cleaning            #   
#                                        #   
##########################################

cell_lines = ["HCC_2998","MDA_MB_435", "SNB_78", "NCI_ADR_RES","DU_145", "786_0", "A498","A549_ATCC","ACHN","BT_549","CAKI_1","DLD_1","DMS_114","DMS_273","CCRF_CEM","COLO_205","EKVX"]
Results_Dic = {}
#%%
for SEL_CEL in cell_lines:
	# Loading the the drug responses and their IDs (NSC)
    DF = pd.read_csv("/home/obazgir/REFINED/NCI/NCI60_GI50_normalized_April.csv")
    FilteredDF = DF.loc[DF.CELL==SEL_CEL]											# Pulling out the selected cell line responses
    FilteredDF = FilteredDF.drop_duplicates(['NSC'])                                # Dropping out the duplicates


    Feat_DF = pd.read_csv("/home/obazgir/REFINED/NCI/normalized_padel_feats_NCI60_672.csv")	# Load the drug descriptors of the drugs applied on the selected cell line 
    Cell_Features = Feat_DF[Feat_DF.NSC.isin(FilteredDF.NSC)]
    TargetDF = FilteredDF[FilteredDF.NSC.isin(Cell_Features.NSC)]
    
    Y = np.array(TargetDF.NORMLOG50)
    # Features
    X = Cell_Features.values
    X = X[:,2:]
    # fix random seed for reproducibility
    seed = 10
    np.random.seed(seed)
    # split training, validation and test sets based on each sample NSC ID
    NSC_All = np.array(TargetDF['NSC'],dtype = int)
    Train_Ind, Rest_Ind, Y_Train, Y_Rest = train_test_split(NSC_All, Y, test_size= 0.2, random_state=seed)
    Validation_Ind, Test_Ind, Y_Validation, Y_Test = train_test_split(Rest_Ind, Y_Rest, test_size= 0.5, random_state=seed)
    # Sort the NSCs
    Train_Ind = np.sort(Train_Ind)
    Validation_Ind = np.sort(Validation_Ind)
    Test_Ind = np.sort(Test_Ind)
    # Extracting the drug descriptors of each set based on their associated NSCs
    X_Train_Raw = Cell_Features[Cell_Features.NSC.isin(Train_Ind)]
    X_Validation_Raw = Cell_Features[Cell_Features.NSC.isin(Validation_Ind)]
    X_Test_Raw = Cell_Features[Cell_Features.NSC.isin(Test_Ind)]
    
    Y_Train = TargetDF[TargetDF.NSC.isin(Train_Ind)];  Y_Train = np.array(Y_Train['NORMLOG50']) 
    Y_Validation = TargetDF[TargetDF.NSC.isin(Validation_Ind)];  Y_Validation = np.array(Y_Validation['NORMLOG50']) 
    Y_Test = TargetDF[TargetDF.NSC.isin(Test_Ind)];  Y_Test = np.array(Y_Test['NORMLOG50']) 
    
    X_Dummy = X_Train_Raw.values;     X_Train = X_Dummy[:,2:]
    X_Dummy = X_Validation_Raw.values;     X_Validation = X_Dummy[:,2:]
    X_Dummy = X_Test_Raw.values;      X_Test = X_Dummy[:,2:]
    
    #%% REFINED coordinates
    import math
    with open('/home/obazgir/REFINED/NCI/Image_Generation/theMapping_Init_LE.pickle','rb') as file:
        gene_names,coords,map_in_int = pickle.load(file)
        

    # Convert data into images using the coordinates generated by REFINED    
    nn = 26																									# Image size = sqrt(#features (drug descriptors))																		

    X_Train_REFINED = REFINED_Im_Gen(X_Train,nn, map_in_int, gene_names,coords)
    X_Val_REFINED = REFINED_Im_Gen(X_Validation,nn, map_in_int, gene_names,coords)
    X_Test_REFINED = REFINED_Im_Gen(X_Test,nn, map_in_int, gene_names,coords)

    #%% importing tensorflow    
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras.callbacks import EarlyStopping

    #%% Defining the CNN Model
    Results_Data = np.zeros((1,4))
        
	sz = X_Train_REFINED.shape
	Width = int(math.sqrt(sz[1]))
	Height = int(math.sqrt(sz[1]))
	CNN_Train = X_Train_REFINED.reshape(-1,Width,Height,1)
	CNN_Val = X_Val_REFINED.reshape(-1,Width,Height,1)
	CNN_Test = X_Test_REFINED.reshape(-1,Width,Height,1)

	def CNN_model(Width,Height):
		nb_filters = 64
		nb_conv = 7
		
		model = models.Sequential()
		# Convlolutional layers
		model.add(layers.Conv2D(nb_filters*1, (nb_conv, nb_conv),padding='valid',strides=2,dilation_rate=1,input_shape=(Width, Height,1)))
		model.add(layers.BatchNormalization())
		model.add(layers.Activation('relu'))
		model.add(layers.Conv2D(nb_filters*1, (nb_conv, nb_conv),padding='valid',strides=2,dilation_rate=1))
		model.add(layers.BatchNormalization())
		model.add(layers.Activation('relu'))

		model.add(layers.Flatten())
		# Dense layers
		model.add(layers.Dense(256))
		model.add(layers.BatchNormalization())
		model.add(layers.Activation('relu'))
		
		model.add(layers.Dense(64))
		model.add(layers.BatchNormalization())
		model.add(layers.Activation('relu'))
		model.add(layers.Dropout(1-0.7))
	
		model.add(layers.Dense(1))

		opt = tf.keras.optimizers.Adam(lr=0.0001)
		
		model.compile(loss='mse', optimizer = opt)
		return model
	# Training the CNN Model
	model = CNN_model(Width,Height)
	ES = EarlyStopping(monitor='val_loss', mode='min', verbose=0, patience=30)
	CNN_History = model.fit(CNN_Train, Y_Train, batch_size= 128, epochs = 250, verbose=0, validation_data=(CNN_Val, Y_Validation), callbacks = [ES])
	Y_Val_Pred_CNN = model.predict(CNN_Val, batch_size= 128, verbose=1)
	Y_Pred_CNN = model.predict(CNN_Test, batch_size= 128, verbose=1)
	
	print(model.summary())
	# Plot the Model
	plt.plot(CNN_History.history['loss'], label='train')
	plt.plot(CNN_History.history['val_loss'], label='Validation')
	plt.legend()
	plt.show()
	
	# Measuring the REFINED-CNN performance (NRMSE, R2, PCC, Bias)
	CNN_NRMSE, CNN_R2 = NRMSE(Y_Test, Y_Pred_CNN)
	print(CNN_NRMSE,"NRMSE of "+SEL_CEL)
	print(CNN_R2,"R2 of " +SEL_CEL)
	Y_Test = np.reshape(Y_Test, (Y_Pred_CNN.shape))
	CNN_ER = Y_Test - Y_Pred_CNN
	CNN_PCC, p_value = pearsonr(Y_Test, Y_Pred_CNN)

	print(CNN_PCC,"PCC of " + SEL_CEL)
	Y_Validation = Y_Validation.reshape(len(Y_Validation),1)
	Y_Test = Y_Test.reshape(len(Y_Test),1)
	Bias = Bias_Calc(Y_Test, Y_Pred_CNN)

	Results_Data[0,:] = [CNN_NRMSE,CNN_PCC,CNN_R2,Bias]
    Results = pd.DataFrame(data = Results_Data , columns = ["NRMSE","PCC","R2","Bias"], index = Model_Names)
   
    Results_Dic[SEL_CEL] = Results

print(Results_Dic)


