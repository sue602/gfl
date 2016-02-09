'''Copyright (C) 2016 by Wesley Tansey

    This file is part of the GFL library.

    The GFL library is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The GFL library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with the GFL library.  If not, see <http://www.gnu.org/licenses/>.
'''
import numpy as np
import matplotlib.pylab as plt
from numpy.ctypeslib import ndpointer
from ctypes import *
from utils import *

'''Load the bayesian GFL library'''
gflbayes_lib = cdll.LoadLibrary('libgraphfl.so')
gflbayes_gaussian_laplace = gflbayes_lib.bayes_gfl_gaussian_laplace
gflbayes_gaussian_laplace.restype = None
gflbayes_gaussian_laplace.argtypes = [c_int, ndpointer(c_double, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS'),
                c_int, ndpointer(c_int, flags='C_CONTIGUOUS'), ndpointer(c_int, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS'),
                c_double, c_double,
                c_int, c_int, c_int,
                ndpointer(dtype=np.uintp, ndim=1, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS')]

gflbayes_lib = cdll.LoadLibrary('libgraphfl.so')
gflbayes_gaussian_doublepareto = gflbayes_lib.bayes_gfl_gaussian_doublepareto
gflbayes_gaussian_doublepareto.restype = None
gflbayes_gaussian_doublepareto.argtypes = [c_int, ndpointer(c_double, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS'),
                c_int, ndpointer(c_int, flags='C_CONTIGUOUS'), ndpointer(c_int, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS'),
                c_double, c_double,
                c_double, c_double, c_double,
                c_int, c_int, c_int,
                ndpointer(dtype=np.uintp, ndim=1, flags='C_CONTIGUOUS'), ndpointer(c_double, flags='C_CONTIGUOUS')]

trunc_norm = gflbayes_lib.rnorm_trunc_norand
trunc_norm.restype = c_double
trunc_norm.argtypes = [c_double, c_double, c_double, c_double]

def double_matrix_to_c_pointer(x):
    return (x.__array_interface__['data'][0] + np.arange(x.shape[0])*x.strides[0]).astype(np.uintp)

def sample_gtf(data, D, k, likelihood='gaussian', prior='laplace',
                           lambda_hyperparams=None, lam_walk_stdev=0.01, lam0=1.,
                           dp_hyperparameter=1.,
                           iterations=7000, burn=2000, thin=10,
                           verbose=False):
    '''Generate samples from the generalized graph trend filtering distribution via a modified Swendsen-Wang slice sampling algorithm.
    Options for likelihood: gaussian, binomial, poisson. Options for prior: laplace, doublepareto.'''
    Dk = get_delta(D, k)
    dk_rows, dk_rowbreaks, dk_cols, dk_vals = decompose_delta(Dk)

    if likelihood == 'gaussian':
        y, w = data
    elif likelihood == 'binomial':
        trials, successes = data
    elif likelihood == 'poisson':
        obs = data
    else:
        raise Exception('Unknown likelihood type: {0}'.format(likelihood))

    if prior == 'laplace':
        if lambda_hyperparams == None:
            lambda_hyperparams = (0.5, 0.5)
    elif prior == 'doublepareto':
        if lambda_hyperparams == None:
            lambda_hyperparams = (0.01, 0.01)
    else:
        raise Exception('Unknown prior type: {0}.'.format(prior))

    # Run the Gibbs sampler
    sample_size = (iterations - burn) / thin
    beta_samples = np.zeros((sample_size, D.shape[1]))
    lam_samples = np.zeros(sample_size)

    if likelihood == 'gaussian':
        if prior == 'laplace':
            gflbayes_gaussian_laplace(len(y), y, w,
                                      dk_rows, dk_rowbreaks, dk_cols, dk_vals,
                                      lambda_hyperparams[0], lambda_hyperparams[1],
                                      iterations, burn, thin,
                                      double_matrix_to_c_pointer(beta_samples), lam_samples)
        elif prior == 'doublepareto':
            gflbayes_gaussian_doublepareto(len(y), y, w,
                                      dk_rows, dk_rowbreaks, dk_cols, dk_vals,
                                      lambda_hyperparams[0], lambda_hyperparams[1],
                                      lam_walk_stdev, lam0, dp_hyperparameter,
                                      iterations, burn, thin,
                                      double_matrix_to_c_pointer(beta_samples), lam_samples)
    elif likelihood == 'binomial':
        pass
    elif likelihood == 'poisson':
        pass
    else:
        raise Exception('Unknown likelihood type: {0}'.format(likelihood))

    print 'Sample size: {0}'.format(sample_size)

    return (beta_samples,lam_samples)

if __name__ == '__main__':
    # Load the data and create the penalty matrix
    k = 0
    y = np.zeros(100)
    y[:25] = 15.
    y[25:50] = 20.
    y[50:75] = 25.
    y[75:] = 10.
    y += np.random.normal(0,1.0,size=len(y))
    mean_offset = y.mean()
    y -= mean_offset
    stdev_offset = y.std()
    y /= stdev_offset
    
    # equally weight each data point
    w = np.ones(len(y))

    # try different weights for each data point
    # w = np.ones(len(y))
    # w[0:len(y)/2] = 100
    # w[len(y)/2:] = 10
    
    D = get_1d_penalty_matrix(len(y))

    z_samples, lam_samples = sample_gtf((y, w), D, k, likelihood='gaussian', prior='doublepareto', verbose=True)
    y *= stdev_offset
    y += mean_offset
    z_samples *= stdev_offset
    z_samples += mean_offset
    z = z_samples.mean(axis=0)
    z_stdev = z_samples.std(axis=0)
    z_lower = z - z_stdev*2
    z_upper = z + z_stdev*2
    assert(len(z) == len(y))


    fig, ax = plt.subplots(3)
    x = np.linspace(0,1,len(y))
    ax[0].plot(np.arange(z_samples.shape[0])+1, np.cumsum(z_samples[:,12]) / (np.arange(z_samples.shape[0])+1.), color='orange')
    ax[0].plot(np.arange(z_samples.shape[0])+1, np.cumsum(z_samples[:,37]) / (np.arange(z_samples.shape[0])+1.), color='skyblue')
    ax[0].plot(np.arange(z_samples.shape[0])+1, np.cumsum(z_samples[:,63]) / (np.arange(z_samples.shape[0])+1.), color='black')
    ax[0].plot(np.arange(z_samples.shape[0])+1, np.cumsum(z_samples[:,87]) / (np.arange(z_samples.shape[0])+1.), color='#009E73')
    ax[0].set_xlim([1,z_samples.shape[0]])
    ax[0].set_ylabel('Sample beta mean values')

    n, bins, patches = ax[1].hist(lam_samples, 50)
    ax[1].set_xlabel('Lambda values')
    ax[1].set_ylabel('Samples')

    ax[2].scatter(x, y, alpha=0.5)
    ax[2].plot(x, z, lw=2, color='orange')
    ax[2].fill_between(x, z_lower, z_upper, alpha=0.3, color='orange')
    ax[2].set_xlim([0,1])
    ax[2].set_ylabel('y')
    
    plt.show()
    plt.clf()