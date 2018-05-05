#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Author: Bradley Gram-Hansen
Time created:  14:57
Date created:  05/05/2018

License: MIT
'''


import numpy as np
import sys
import os
import pandas as pd
import datetime
from pathlib import Path

def mono_seq_ess(samples, key, normed=False, mu=None, var=None):
    # Estimates effective sample sizes of samples along the specified axis
    # with the monotone positive sequence estimator of "Practical Markov
    # Chain Monte Carlo" by Geyer (1992). The estimator is ONLY VALID for
    # reversible Markov chains. The inputs 'mu' and 'var' are optional
    # and unnecessary for the most cases in practice.
    #
    # Inputs
    # ------
    # mu, var : vectors for the mean E(x) and variance Var(x) if the
    #     analytical (or accurately estimated) value is available. If provided,
    #     it can stabilize the estimate of auto-correlations and hence ESS.
    #     This is intended for research uses when one wants to
    #     accurately quantify the asymptotic efficiency of a MCMC algorithm.
    # req_acorr : bool
    #     If true, a list of estimated auto correlation sequences are returned as the
    #     second output.
    # Returns
    # -------
    # ess : numpy array
    # auto_cor : list of numpy array
    #     auto-correlation estimates of the chain up to the lag beyond which the
    #     auto-correlation can be considered insignificant by the monotonicity
    #     criterion.

    # for key in keys:

    if mu is None:
        mu = samples[key].mean()
    if var is None:
        var = samples[key].var()

    d = len(samples[key]) -1
    ess = np.zeros(d)
    # ess = {}
    auto_cor = []
    for j in range(d):
        x = samples[key][:, j]
        ess_j, auto_cor_j = ess_1d(x, mu, var)
        ess[j] = ess_j
        auto_cor.append(auto_cor_j)

        # if normed:
        #     ess /= samples.shape[axis]
    return ess

def ess_1d(x, mu, var):
    n = len(x)
    auto_cor = []

    lag = 0
    auto_cor_sum = 0
    even_auto_cor = compute_acorr(x, lag, mu, var)
    auto_cor.append(even_auto_cor)
    auto_cor_sum -= even_auto_cor

    lag += 1
    odd_auto_cor = compute_acorr(x, lag, mu, var)
    auto_cor.append(odd_auto_cor)
    running_min = even_auto_cor + odd_auto_cor

    while (even_auto_cor + odd_auto_cor > 0) and (lag + 2 < n):
        running_min = min(running_min, (even_auto_cor + odd_auto_cor))
        auto_cor_sum = auto_cor_sum + 2 * running_min

        lag += 1
        even_auto_cor = compute_acorr(x, lag, mu, var)
        auto_cor.append(even_auto_cor)

        lag = lag + 1
        odd_auto_cor = compute_acorr(x, lag, mu, var)
        auto_cor.append(odd_auto_cor)

    ess = n / auto_cor_sum
    if auto_cor_sum < 0:  # Rare, but can happen when 'x' shows strong negative correlations.
        ess = float('inf')
    return ess, np.array(auto_cor)


def compute_acorr(x, k, mu, var):
    # Returns an estimate of the lag 'k' auto-correlation of a time series 'x'.
    # The estimator is biased towards zero due to the factor (n - k) / n.
    # See Geyer (1992) Section 3.1 and the reference therein for justification.
    n = len(x)
    acorr = (x[:(n - k)] - mu) * (x[k:] - mu)
    acorr = np.mean(acorr) / var * (n - k) / n
    return acorr

# A-NICE-MC
def effective_sample_size(x, mu=None, var=None, logger=None):
    """
    Calculate the effective sample size of sequence generated by MCMC.
    :param x:
    :param mu: mean of the variable
    :param var: variance of the variable
    :param logger: logg
    :return: effective sample size of the sequence
    Make sure that `mu` and `var` are correct!
    """
    b, t, d = x.shape  # batch_number, sample size, dimension of that variable
    if mu is None:
        mu = np.mean(x, axis = (0, 1))
    if var is None:
        var = np.var(x, axis = (0, 1))
    ess_ = np.ones([d])
    for s in range(1, t):
        p = auto_correlation_time(x, s, mu, var)
        if np.sum(p > 0.05) == 0:
            break
        else:
            for j in range(0, d):
                if p[j] > 0.05:
                    ess_[j] += 2.0 * p[j] * (1.0 - float(s) / t)

    # logger.info('ESS: max [%f] min [%f] / [%d]' % (t / np.min(ess_), t / np.max(ess_), t))
    return t / ess_

def auto_correlation_time(x, s, mu, var):
    b, t, d = x.shape
    act_ = np.zeros([d])
    for i in range(0, b):
        y = x[i] - mu
        p, n = y[:-s], y[s:]
        act_ += np.mean(p * n, axis=0) / var
    act_ = act_ / b
    return act_

# ESS for key
# what is the shape for the df with multiple/batches?
# def ess_onekey(df, key):

# A-NICE-MC
def gelman_rubin_diagnostic(x, mu=None, logger=None):
    '''
    Notes
    -----
    The diagnostic is computed by:  math:: \hat{R} = \frac{\hat{V}}{W}

    where :math:`W` is the within-chain variance and :math:`\hat{V}` is
    the posterior variance estimate for the pooled traces.

    :param x: samples
    :param mu, var: true posterior mean and variance; if None, Monte Carlo estimates
    :param logger: None
    :return: r_hat

    References
    ----------
    Brooks and Gelman (1998)
    Gelman and Rubin (1992)
    '''
    m, n = x.shape[0], x.shape[1]
    if m < 2:
        raise ValueError(
            'Gelman-Rubin diagnostic requires multiple chains '
            'of the same length.')
    theta = np.mean(x, axis=1)
    sigma = np.var(x, axis=1)
    # theta_m = np.mean(theta, axis=0)
    theta_m = mu if mu else np.mean(theta, axis=0)

    # Calculate between-chain variance
    b = float(n) / float(m-1) * np.sum((theta - theta_m) ** 2)
    # Calculate within-chain variance
    w = 1. / float(m) * np.sum(sigma, axis=0)
    # Estimate of marginal posterior variance
    v_hat = float(n-1) / float(n) * w + float(m+1) / float(m * n) * b
    r_hat = np.sqrt(v_hat / w)
    # logger.info('R: max [%f] min [%f]' % (np.max(r_hat), np.min(r_hat)))
    return r_hat

def extract_means(dataframe, keys=None):
    """

    :param dataframe: pandas.DataFrame
    :param keys: sring of params
    :return: Samples for each variable

    With a dataframe, the columns correspond to the key names and the
    rows, correspond to sample number.
    To extract all the samples (and chains) use dataframe.loc[<key>]
    If the values stored are arrays, i.e. multiple chains, then use
    dataframe.loc[<key>][i] to extract the exact array
    """
    means = {}
    if keys:
        for key in keys:
            if key is None:
                continue
            else:
                print('Debug statement in utils/eval_stats/means The else branch executed print length of dataframe {0}'.format(print(len(dataframe.index))))
                means[key] = dataframe[key].sum() / len(dataframe.index)
        return means
    else:
        mean = dataframe.values.sum() / len(dataframe)
        print('Debug statement in utils/eval_stats/extract_stats 2nd else branch executed print mean {0}'.format(mean))
        return mean

def extract_stats(dataframe,keys):
    """

    :param dataframe: pandas.DataFrame
    :param keys: sring of required params
    :return: count, mean, std, min, max and confidence intervals

    """
    return dataframe[keys].describe()

def save_data(samples, all_samples, prefix=''):
        # Ensures directory for this data exists for model, if not creates it
    PATH  = sys.path[0]
    os.makedirs(PATH, exist_ok=True)
    PATH_data =  os.path.join(PATH, 'data'+datetime.datetime.now().isoformat())
    os.makedirs(PATH_data, exist_ok=True)
    print(50 * '=')
    print('Saving data in: {0}'.format(PATH_data))
    print(50 * '=')
    path1 = prefix + 'samples_after_burnin' '.csv'
    path2 = prefix + 'all_samples' + '.csv'
    samples.to_csv(os.path.join(PATH_data,path1), index=False, header=True)
    all_samples.to_csv(os.path.join(PATH_data,path2), index=False, header=True)

# def load_data_old(n_chain, var_key, PATH, include_burnin_samples=False):
#     '''
#     2018-01-29
#     :param n_chain: number of chains
#     :param var_key: variable keys
#     :param PATH: PATH to the csv file
#     :param include_burnin_samples: load all samples or samples after burnin
#     :return: dictionary of dictionary, each chain is an entry, all_stats[0]['samples'] is df
#     '''
#     all_stats = {}
#     for i in range(n_chain):
#         all_stats[i] = {}
#         df = pd.DataFrame()
#         for key in var_key:
#             if include_burnin_samples:
#                 samples_file_dir = PATH + '/chain_{}_samples_with_burnin_{}.csv'.format(i, key)
#             else:
#                 samples_file_dir = PATH + '/chain_{}_samples_after_burnin_{}.csv'.format(i, key)
#             df_key = pd.read_csv(samples_file_dir, index_col=None, header=0)
#             df = pd.concat([df, df_key], axis=1)
#         all_stats[i]['samples'] = df
#
#     return all_stats

def load_data(n_chain, PATH, inference='dhmc', include_burnin_samples=False):
    '''
        2018-01-30
        :param n_chain: number of chains
        :param PATH: PATH to the csv file
        :param include_burnin_samples: load all samples or samples after burnin
        :return: dictionary of df, each key(chain number) contains the dataframe of posterior samples
        '''
    all_stats = {}
    for i in range(n_chain):
        if include_burnin_samples:
            samples_file_dir = PATH + '/{}_chain_{}_all_samples.csv'.format(inference, i+1)
        else:
            samples_file_dir = PATH + '/{}_chain_{}_samples_after_burnin.csv'.format(inference, i+1)
        if Path(samples_file_dir).exists():
            df = pd.read_csv(samples_file_dir, index_col=None, header=0)
            all_stats[i] = df
        else: all_stats[i+1] = None
    return all_stats

def get_keys(file_name):
    '''
    :param file_name: csv file name
    :return: list of str: header of all columns
    '''
    header = pd.read_csv(file_name, header=None, nrows=1)
    var_key = header.as_matrix()[0]
    return var_key

# for HMM model
def samples_heatmap(num_state, T, samples):
    heatmap =  np.zeros((num_state, T+1))
    for i in range(T+1):
        heatmap[0, i] = np.mean(samples[:, i] == 0)
        heatmap[1, i] = np.mean(samples[:, i] == 1)
        heatmap[2, i] = np.mean(samples[:, i] == 2)
    return heatmap

def l2_norm(samples_post, true_post):
    result = np.sum((samples_post - true_post)**2)
    return result

def multi_l2norm_hmm(each_num, total_num, l2_norm, true_post, raw_samples, num_state, T):
    group_num = int(total_num/each_num)
    l2norm_result = np.zeros(group_num)
    for i in range(group_num):
        heatmap = samples_heatmap(num_state, T, raw_samples[:each_num * (i + 1), :])
        l2norm_result[i] = l2_norm(heatmap, true_post.transpose())
    return l2norm_result