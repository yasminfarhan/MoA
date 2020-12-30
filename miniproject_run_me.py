#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 22 16:05:41 2020

@author: yasmin
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 21 14:58:01 2020

@author: yasmin
"""
num_tgt_to_tst = 206

from sklearn import preprocessing
from sklearn.model_selection import train_test_split as tts
from sklearn.linear_model import LogisticRegression
from sklearn.feature_selection import VarianceThreshold
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA

import numpy as np

import pandas as pd
from pandas import DataFrame as df

from imblearn.over_sampling import SMOTE

import matplotlib.pyplot as plt

from keras.models import Sequential
from keras.layers import Dense

#class to access original and transformed data depending on what's needed
class dat_obj():
    def __init__(self):
        super(dat_obj, self).__init__()    
        
        self.orig_train, self.orig_test, self.orig_train_tgt_scored, self.orig_train_tgt_nonscored = self._load_data()
        self.sig_id_train = self.orig_train['sig_id']
        self.sig_id_test = self.orig_test['sig_id']
        self.train_tgt_concat = pd.concat([self._preprocess_df(self.orig_train_tgt_scored), self._preprocess_df(self.orig_train_tgt_nonscored)], axis=1)
        self.real_train = self.binarize_categorical_ft(self._preprocess_df(self.orig_train))
        self.real_test = self.binarize_categorical_ft(self._preprocess_df(self.orig_test))
        
    def _load_data(self, dat_path="../../Data/"):       
        orig_train = pd.read_csv(dat_path+"train_features.csv")
        orig_test = pd.read_csv(dat_path+"test_features.csv")
        orig_train_tgt_scored = pd.read_csv(dat_path+"train_targets_scored.csv")
        orig_train_tgt_nonscored = pd.read_csv(dat_path+"train_targets_nonscored.csv")
        
        #return self._preprocess_df(orig_train), self._preprocess_df(orig_test), self._preprocess_df(orig_train_tgt_scored), self._preprocess_df(orig_train_tgt_nonscored)
        return orig_train, orig_test, self._preprocess_df(orig_train_tgt_scored), self._preprocess_df(orig_train_tgt_nonscored)
    
    def _preprocess_df(self, df):
        #Drop null values if there are any
        df = df.dropna()
        
        #removing sig_id col
        df = df.iloc[:, 1:]    
        
        return df
        
    def dim_reduction(self, df, num_ft=200):
        #Dimensionality Reduction - PCA
        pca = PCA(n_components=num_ft)
        pca.fit(df)
        df = pca.fit_transform(df)      
        
        return df    
    
    def ft_selection(self, df, thresh=0.8):
        sel = VarianceThreshold(threshold=(thresh * (1 - thresh)))
        sel.fit_transform(df)
        
        return df
    
    #binarizing known cp categorical variables - must happen before dim reduction/ft selection, to both test and train dat
    def binarize_categorical_ft(self, df_cat):       
        #making categorical ft into real valued data
        #ft 1: cp_type - turn into 1 or 0, where ctl_vehicle is 0, given that cp_type == ctl_vehicle has no effect on MoA
        cp_type_col = (df_cat['cp_type']).tolist()
        
        for i in range(len(cp_type_col)):
            if(cp_type_col[i] == "trt_cp"):
                cp_type_col[i] = 1
            else:
                cp_type_col[i] = 0
        cp_type_col = pd.DataFrame(cp_type_col)
        
        #ft 2: cp_time - one hot encode this feature, assuming that each value is of equal effect
        cp_time_col = np.asarray(df_cat['cp_time'])
        new_cp_time_cols = []
        
        for el in cp_time_col:
            if(int(el) == 24):
                new_cp_time_cols.append([1,0,0])
            elif(int(el) == 48):
                new_cp_time_cols.append([0,1,0])
            else:
                new_cp_time_cols.append([0,0,1])
                
        cp_time_matrix = pd.DataFrame(new_cp_time_cols)
        
        #ft 3: cp_dose - high == 1, low == -1; one hot encode this feature, assuming that each value is of equal effect
        cp_dose_col = np.asarray(df_cat['cp_dose'])
        new_cp_dose_cols = []
    
        for el in cp_dose_col:
            if(el == "high"):
                new_cp_dose_cols.append([1,0])
            else:
                new_cp_dose_cols.append([0,1]) 
        cp_dose_matrix = pd.DataFrame(new_cp_dose_cols)
        
        new_df = pd.concat([cp_type_col, cp_time_matrix, cp_dose_matrix, df_cat.iloc[:, 3:]], axis=1)
        
        return new_df     

#Our evaluation metric - log loss across N*M predictions
def binary_log_loss(probs, y, N):
    epsilon = 1e-5 #preventing divide by 0 errors
    log_loss = -np.average(y*np.log(probs + epsilon) + (1-y)*np.log(1-probs+epsilon))
    
    return log_loss

#performs traditional binary class prediction  for one target given test data
def binary_clf(train, tr_tgt_col, model, is_nn=0, do_smp=1):    
    smp = SMOTE(random_state=42)    

    neg_class_only = (tr_tgt_col.sum() < 2) #if our classes are too extremely imbalanced, they cannot be properly oversampled
    pos_class_only = ((tr_tgt_col.sum() == tr_tgt_col.shape[0]))
    
    if(not(neg_class_only or pos_class_only) and do_smp):
        train, tr_tgt_col = smp.fit_resample(np.matrix(train), (tr_tgt_col))
    
    # evaluate pipeline    
    X_train, X_test, y_train, y_test = tts(np.array(train), np.array(tr_tgt_col), random_state=42, shuffle=True)
    
    if(not(neg_class_only or pos_class_only)): #if our classes are too extremely imbalanced, the LogisticRegression model throws an error, so we manually provide predictions/probabilities
        if(is_nn):
            model.fit(X_train, y_train)
            y_pred = model.predict_classes(X_test)
            y_prob_pos = model.predict(X_test)
        else:
            model = model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_probs = model.predict_proba(X_test)
            y_prob_pos = y_probs.transpose()[1]
        # print("We have both classes", y_test.shape)
        
        loss = binary_log_loss(y_prob_pos, y_test, y_test.shape[0])    

    else:
        # print("One class only")
        
        if(neg_class_only):
            y_prob_pos = np.zeros((y_test.shape)) #0% probability of being predicted 1 if all test values are 0
            y_pred = np.zeros((y_test.shape)) #predicted values are all zeroes
        else:
            y_prob_pos = np.ones((y_test.shape))  #100% probability of being predicted 1 if all test values are 0
            y_pred = np.ones((y_test.shape)) #predicted values are all ones
        loss = 0
        
    return model, y_pred, y_test, y_prob_pos, loss

#Given a classifier, performs multilabel classification across all targets
def multilabel_clf(X, Y, clf, is_nn=0, rand_tgts=[], do_smp=0, scale_dat=1):
    kaggle_score = 0
    model_lst = []
    loss_lst = []
    y_pred_matrix = df([])
    y_probs_matrix = df([])
    y_true_matrix = df([])
    M = Y.shape[1]
        
    if(scale_dat):
        scaler = preprocessing.StandardScaler().fit(X)
        X = scaler.transform(X)
        
        
    if(rand_tgts == []):
        tgts_to_tst = list(range(num_tgt_to_tst))
    else:
        tgts_to_tst = rand_tgts
    
    #for tgt_idx in range(M):
    #for tgt_idx in range(num_tgt_to_tst):
    for tgt_idx in tgts_to_tst:
            
        label_col = Y.iloc[:, tgt_idx] 
        #print("tgt:", tgt_idx, label_col.shape, label_col.sum())
            
        print("do_smp:", do_smp)
        model, y_pred, y_true, y_probs, log_loss = binary_clf(X, label_col, clf, is_nn, do_smp)
            
        y_pred_matrix = pd.concat([y_pred_matrix, df(y_pred)], axis=1)
        y_probs_matrix = pd.concat([y_probs_matrix, df(y_probs)], axis=1)
        y_true_matrix = pd.concat([y_true_matrix, df(y_true)], axis=1)
        model_lst.append(model)
        loss_lst.append(log_loss)

        kaggle_score += log_loss
                
        print("loss", tgt_idx, ":", log_loss)  
            
    kaggle_score = (1/M)*kaggle_score
    return kaggle_score, model_lst, y_pred_matrix, y_probs_matrix, y_true_matrix, loss_lst

#create NN model using keras module with final output as sigmoid activation
def create_nn_model(num_ft=878):
	# create model
	model = Sequential()
	model.add(Dense(12, input_dim=num_ft, activation='relu'))
	model.add(Dense(1, activation='sigmoid'))
    
	# Compile model
	model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
	return model

#evaluate each classifier across all scored targets and plot their losses across targets
def eval_clfs(clf_lst, clf_names, num_ft=200):
    dat = dat_obj()
    X_dat, y_dat = dat.real_train, dat.orig_train_tgt_scored
    is_nn = 0
    ft_lst = [100, 300, 300]
    do_smp = [0, 1, 0]
    loss_lsts = []
    
    for i in range(len(clf_lst)):        
        if(clf_names[i] == "NeuralNet"):
            is_nn=1
        
        X_transformed = dat.dim_reduction(X_dat, ft_lst[i])
            
        kaggle_score, model_lst, y_pred_matrix, y_probs_matrix, y_true_matrix, loss_lst = multilabel_clf(X_transformed, y_dat, clf_lst[i], is_nn, [], do_smp[i])
        loss_lsts.append(loss_lst)
        print("kaggle score:", kaggle_score)
    
    plot_clfs(loss_lsts, clf_names, "Target Index", "Log Loss", "Scored Targets Loss Comparison Across Classifiers")

#evaluate a list of parameters for a given classifier
def eval_same_clf(clf, param_lst, param_name='pc', is_nn=0, do_dr=1, num_ft=200, title=''):
    dat = dat_obj()
    X_dat, y_dat = dat.real_train, dat.orig_train_tgt_scored
    num_pc = num_ft
    og_title = title
    
    tgts_to_tst = []
    for i in range(num_tgt_to_tst):
        tgts_to_tst.append(np.random.randint(0, 206))
            
    for smp_val in range(1):
        loss_lsts = []
        best_param = 0
        best_loss = 1000
        
        #smp_val = not(smp_val)
        
        if(smp_val):
            title = og_title+" with Oversampling"
        else:
            title = og_title+" without Oversampling"
            
        for i in range(len(param_lst)):        
            param = param_lst[i]
       
            if(param_name == 'pc'):
                num_pc = param
                
                if(is_nn):
                    clf = create_nn_model(num_pc)      
            elif(param_name == 'c'):
                clf = LogisticRegression(C=param)
            elif(param_name == 'md'):
                RandomForestClassifier(max_depth=param, n_estimators=50, n_jobs=-1)
                
            if(do_dr):
                X_transformed = dat.dim_reduction(X_dat, num_pc)
            else:
                X_transformed = X_dat
                        
            kaggle_score, model_lst, y_pred_matrix, y_probs_matrix, y_true_matrix, loss_lst = multilabel_clf(X_transformed, y_dat, clf, is_nn, tgts_to_tst, smp_val)
            loss_lsts.append(loss_lst)
            avg_loss = np.average(loss_lst)
            
            if(avg_loss < best_loss):
                best_loss = avg_loss
                best_param = param
                
            print("kaggle score:", kaggle_score)
        
        print("best param is:", best_param, "loss:", best_loss)
    
        plot_clfs(loss_lsts, param_lst, "Target Index", "Log Loss", title)        
        
#Plot given metric for all classifiers given in list across targets being tested
def plot_clfs(val_lsts, clf_names, xlabel='', ylabel='', title=''):
    tgt_lst = list(range(num_tgt_to_tst))
    
    for i in range(len(val_lsts)):
        lst = val_lsts[i]
        clf_name = clf_names[i]
        
        plt.plot(tgt_lst, lst, label=clf_name)
    
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.show()

#write probability matrix to submission csv file
def write_preds_to_file(probs, sig_id, header):                
    dat_to_write = pd.concat([sig_id, probs], axis=1)
    cols = ['sig_id'] + list(header[:num_tgt_to_tst])
    dat_to_write.columns = pd.Index(cols)
    dat_to_write.to_csv('../Predictions/submission.csv', index=False)
    
#predict positive class probabilities given fitted classifier
def predict_classes(model, X_test, is_nn):
    y_probs_new = []

    if(is_nn):
        y_prob_pos = model.predict(X_test)
    else:
        y_probs = model.predict_proba(X_test)
        y_prob_pos = y_probs.transpose()[1] 
            
    for p in y_prob_pos:
        eps = 10e-15
        val = max(min(p,1-eps),eps)
        y_probs_new.append(val)
        
    return y_probs_new

#constructing probability matrix using best clf per target
def get_best_clf(clf_lst):
    dat = dat_obj()
    X, Y, X_test = dat.real_train, dat.orig_train_tgt_scored, dat.real_test
    y_probs_matrix = df([])

    #parameter lists depending on which classifier we're testing
    is_nn_lst = [0, 0, 1]
    do_smp_lst = [0, 1, 0]
    
    scaler = preprocessing.StandardScaler().fit(X)
    X = (scaler.transform(X))
        
    #concatenating training and testing data so dim reduction can be correctly applied
    X_concat = df(np.concatenate((X, np.array(X_test)), axis=0))
    
    X_lst = [dat.dim_reduction(X_concat, 100), dat.dim_reduction(X_concat, 300)]
            
    #splicing datasets according to dimensions we want
    X_dat_100 = X_lst[0][:23814]
    X_tst_100 = X_lst[0][23814:]
    X_dat_300 = X_lst[1][:23814]
    X_tst_300 = X_lst[1][23814:]
    
    X_dat_lst = [X_dat_100, X_dat_300, X_dat_300]
    X_tst_lst = [X_tst_100, X_tst_300, X_tst_300]
        
    for i in range(num_tgt_to_tst):
        print("testing tgt:", i)
        label_col = Y.iloc[:, i] 
        best_loss = 1000
        best_model = None
        
        for j in range(len(clf_lst)):
            print("clf:", j, is_nn_lst[j], X_dat_lst[j].shape)
            model, y_pred, y_test, y_prob_pos, loss = binary_clf(X_dat_lst[j], label_col, clf_lst[j], is_nn_lst[j], do_smp_lst[j])
            
            if(loss < best_loss):
                best_loss = loss
                best_model = model
                is_nn_mod = is_nn_lst[j]
                X_tst = X_tst_lst[j]
            
        #predict using test data, write predictions
        y_probs = predict_classes(best_model, X_tst, is_nn_mod)
        y_probs_matrix = pd.concat([y_probs_matrix, df(y_probs)], axis=1)
        print("tgt:", i, y_probs_matrix.shape, best_loss)
        
    header = Y.columns
    write_preds_to_file(y_probs_matrix, dat.sig_id_test, header)
    
    return y_probs_matrix

def main():
    np.random.seed(1)
    
    #define classifier list over which to iterate per target    
    clf_lst = [LogisticRegression(C=0.2), RandomForestClassifier(n_estimators=50, n_jobs=-1, max_depth=150), create_nn_model(300)]
    
    #apply fitted clf model to each target, use best one to get prediction, write to file
    get_best_clf(clf_lst)
    
main()


