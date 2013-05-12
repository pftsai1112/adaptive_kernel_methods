"""
SLASH - Spike Linear Algebra Subroutines in Hilbert spaces
is a library implementing spike trains inner products in three levels:
    Level I   - single neuron vs single neuron inner products
    Level II  - population vs single neuron inner products
    Level III - population vs population inner products

At Level I function names start with lower case 's', 'p' is used to start Level II functions and finally, we used 'pp' to indicate Level III inner products.
    
    
SLASH was orignally conceived by Eder Santana as a BLAS equivalent for spike train linear algebra using Reproducing Kernel Hilbert Spaces.
    
Disclaimer: Part of this code was adapted from "spiketrainlib" by Il Memming Park. spiketrainlib follows BSD license.

References: Paiva et. al. Reproducing Kernel Hilbert Space Framework for spike train Signal Processing.
    
Author: Eder Santana <twitter/@edersantana>
License: BSD style
"""
import numpy as np
from sklearn.externals.joblib import Parallel
from sklearn.externals.joblib import delayed
from sklearn.externals.joblib.parallel import cpu_count
from sklearn.utils import gen_even_slices


"""
====================
SLASH - Level I
====================
"""

def check_n_spikes(x, y=None, sort_flag=False):
    """
    For the remaining of the code, it is more efficient to use y as the longer spike train.
    If only one spike train is passed as argument, this function defines y as x.
    Also, if the spike times weren't sorted yet, insure that sort is flagged to True
    """
    if y is None:
        y = x
    if sort_flag:
        x = np.sort(x)
        y = np.sort(y)
    
    if x.shape[0]>y.shape[0]:
        return y, x
    else:
        return x, y

def pairwise_l1(x,y):
    d = np.tile(y, [x.shape[0], 1]).T
    d -= x
    d = abs(d)
    return d.flatten()

def sMCI(x, y, ksize, y_neg_cum_sum_exp=None, y_pos_cum_sum_exp=None):
    """
    Memoryless Cross Intensity kernel (mCI)
        Input:
          x: (N1x1) numpy array of sorted spike times
          y: (N2x1) numpy array of sorted spike times
          ksize: kernel size
          y_neg_cum_sum_exp = sum_j exp(-y[-j]/ksize) 
          y_pos_cum_sum_exp = sum_j exp(y[j]/ksize)
        Output:
         v: sum_i sum_j exp(-|x[i] - y[j]|/ksize)
    """
    v = 0.
    if x.shape[0]==0 and y.shape[0]==0:
        return v

    assert (ksize>0. and np.isreal(ksize)), "Kernel size must be non-negative real"        

    if x.shape[0] <= 4 or y.shape[0] <= 4:
        # For small spike trains this can be afforded
        v = pairwise_l1(x, y)
        v = np.exp(-v/ksize)
        v = v.sum()
    else:
        # O( N1 log(N2)) implementation
        x_pos_exp = np.exp(x / ksize)
        x_neg_exp = np.exp(-x / ksize)
        
        if y_pos_cum_sum_exp is None:
            y_pos_cum_sum_exp = np.exp(y / ksize)
            y_pos_cum_sum_exp = np.cumsum(y_pos_cum_sum_exp)
        
        if y_neg_cum_sum_exp is None:
            y_neg_cum_sum_exp = np.exp(-y / ksize)
            y_neg_cum_sum_exp = np.flipud(y_neg_cum_sum_exp)
            y_neg_cum_sum_exp = np.cumsum(y_neg_cum_sum_exp)
            y_neg_cum_sum_exp = np.flipud(y_neg_cum_sum_exp)

        yidx = -1
        for xidx in xrange(x.shape[0]):
            while y[min(yidx+1,y.shape[0]-1)] <= x[xidx] and yidx<y.shape[0]-1:
                yidx += 1

            if yidx == -1:
                v = v + y_neg_cum_sum_exp[0] * x_pos_exp[xidx]
            elif yidx == (y.shape[0]-1):
                v = v + y_pos_cum_sum_exp[-1] * x_neg_exp[xidx]
            else:
                v = v + y_pos_cum_sum_exp[yidx] * x_neg_exp[xidx] + \
                    y_neg_cum_sum_exp[yidx+1] * x_pos_exp[xidx]

    return v

def sMCIdistance(x, y, ksize, x_neg_exp=None, x_pos_exp=None, \
                 x_neg_cum_sum_exp=None, x_pos_cum_sum_exp=None, mci11=None):
    """
    Squared Memoryless cross intensity (mCI) based distance
    Input:
      st1: (N1x1) sorted spike times
      st2: (N2x1) sorted spike times
      ksize: kernel size
    Output:
      d: mci11 + mci22 - 2*mci12
    """    
    
    d = 0.    
    if x.shape[0]==0 and y.shape[0]==0:
        return

    assert (ksize>0. and np.isreal(ksize)), "Kernel size must be non-negative real"        

    if (x_neg_cum_sum_exp is None) and (x_pos_cum_sum_exp is None):
        x, y = check_n_spikes(x,y) # we are assuming sorted spike trins

    # first, verify if inputs are equal
    if x is y:
        return d

    # The second special case is a empty vector (silent neuron)
    #if x
    # If at least one of the inpusts is small, those options are affodable and faster
    if x.shape[0] <= 4 and y.shape[0] <= 4:
        mci12 = pairwise_l1(x, y) / ksize        
        mci12 = np.sum( np.exp(-mci12) )        
        mci22 = pairwise_l1(y, y) / ksize
        mci22 = np.sum( np.exp(-mci22) ) 
        if mci11 is None:
            mci11 = pairwise_l1(x, x) / ksize
            mci11 = np.sum( np.exp(-mci11) )
        
        
    elif x.shape[0] <= 4:
        mci12 = pairwise_l1(x, y) / ksize
        mci12 = np.sum( np.exp(-mci12) )
        mci22 = sMCI(y, y, ksize)
        if mci11 is None:
            mci11 = pairwise_l1(x, x) / ksize            
            mci11 = np.sum( np.exp(-mci11) )        
            
    elif y.shape[0] <= 4:
        mci12 = pairwise_l1(x, y) / ksize
        mci12 = np.sum( np.exp(-mci12) )
        mci22 = pairwise_l1(y, y) / ksize
        if mci22 is None:
            mci11 = np.sum( np.exp(-mci22) )
            mci11 = sMCI(x, x, ksize)
            
    else:
        # if spike trains are larger enough, we better use the O(N1 log(N2) ) approx.
        
        # I reccomend analyzing mCI formula when exp(-abs(t1-t2)) 
        #    for t1>=t2 and t1<=t2 to understand this
       
        y_pos_exp = np.exp(y / ksize)                    
        y_pos_cum_sum_exp = np.cumsum(y_pos_exp)
        
        y_neg_exp = np.exp(-y / ksize)
        y_neg_cum_sum_exp = np.flipud(y_neg_exp)
        y_neg_cum_sum_exp = np.cumsum(y_neg_cum_sum_exp)
        y_neg_cum_sum_exp = np.flipud(y_neg_cum_sum_exp)        
        
        
        if  x_pos_cum_sum_exp is None:            
            x_pos_exp = np.exp(x / ksize)
            x_pos_cum_sum_exp = np.cumsum(x_pos_exp)     
            
        if x_neg_cum_sum_exp is None:
            x_neg_exp = np.exp(-x / ksize)
            x_neg_cum_sum_exp = np.flipud(x_neg_exp)
            x_neg_cum_sum_exp = np.cumsum(x_neg_cum_sum_exp)
            x_neg_cum_sum_exp = np.flipud(x_neg_cum_sum_exp)            
       
       
        # mci(x , x)
        if mci11 is None:
            mci11 = 0
            for xidx in range(x.shape[0]):
                if xidx == 1:
                    mci11 = mci11 + x_pos_exp[0] * x_neg_cum_sum_exp[0]
                elif xidx == x.shape[0]-1:
                    mci11 = mci11 + x_neg_exp[-1] * x_pos_cum_sum_exp[-1]
                else:
                    mci11 = mci11 + x_pos_cum_sum_exp[xidx] * x_neg_exp[xidx] + \
                        x_pos_exp[xidx] * x_neg_cum_sum_exp[xidx+1]
       
        # Calculate mci's
            
        # mci(x, y) and mci(x, x)
        xidx = -1
        mci12 = 0.
        mci22 = 0.
        for yidx in xrange(y.shape[0]):
             while x[min(xidx+1,x.shape[0]-1)] <= y[yidx] and xidx<x.shape[0]-1:
                 xidx += 1

             if xidx == -1:
                 mci12 = mci12 + x_neg_cum_sum_exp[0] * y_pos_exp[yidx]
             elif xidx == (x.shape[0]-1):
                 mci12 = mci12 + x_pos_cum_sum_exp[-1] * y_neg_exp[yidx]
             else:
                 mci12 = mci12 + x_pos_cum_sum_exp[xidx] * y_neg_exp[yidx] + \
                    x_neg_cum_sum_exp[xidx+1] * y_pos_exp[yidx]
                    
             # mci(st2, st2)
             if yidx == 1:
                 mci22 = mci22 + y_pos_exp[0] * y_neg_cum_sum_exp[0]
             elif yidx == y.shape[0]-1:
                 mci22 = mci22 + y_neg_exp[-1] * y_pos_cum_sum_exp[-1]
             else:
                 mci22 = mci22 + y_pos_cum_sum_exp[yidx] * y_neg_exp[yidx] + \
                            y_pos_exp[yidx] * y_neg_cum_sum_exp[yidx+1]
        
        
        
    #print "mci11 = %f, mci22 = %f, mci12 = %f" % (mci11, mci22, mci12)
    d = mci11 + mci22 - 2*mci12
    return d

def sNCI(x, y, ksize, gamma, x_neg_exp=None, x_pos_exp=None, \
         x_neg_cum_sum_exp=None, x_pos_cum_sum_exp=None, mci11=None):
    """
    nonlinear cross intensity kernel (nCI) - (aka. radial basis function for)
                                             (spike trains)
    Input:
      st1: (N1x1) sorted spike times
      st2: (N2x1) sorted spike times
      ksize: kernel size 
    Output: 
      v: exp(-gamma*squared_MCI_distance)  
    """
    v = sMCIdistance(x, y, ksize, x_neg_exp=x_neg_exp, x_pos_exp=x_pos_exp, \
                     x_neg_cum_sum_exp=x_neg_cum_sum_exp, \
                     x_pos_cum_sum_exp=x_pos_cum_sum_exp, mci11=mci11)
    v *= -gamma
    v = np.exp(v)
    return v

""" 
==========================
SLASH - Level II
==========================
"""


def pMCI(X, y, ksize, y_neg_cum_sum_exp=None, y_pos_cum_sum_exp=None):
    """
    Memoryless Cross Intensity kernel (mCI)
        Input:
          X: is a length M of numpy arrays of sorted spike times
          y: (N2x1) numpy array of sorted spike times
          ksize: kernel size
          y_neg_cum_sum_exp = sum_j exp(-y[-j]/ksize) 
          y_pos_cum_sum_exp = sum_j exp(y[j]/ksize)
        Output:
         V_k: (numpy.array) sum_i sum_j exp(-|x_k[i] - y[j]|/ksize)
    """
    V = np.zeros(len(X));
    if y_pos_cum_sum_exp is None:
       y_pos_cum_sum_exp = np.exp(y / ksize)
       y_pos_cum_sum_exp = np.cumsum(y_pos_cum_sum_exp)
            
    if y_neg_cum_sum_exp is None:
       y_neg_cum_sum_exp = np.exp(-y / ksize)
       y_neg_cum_sum_exp = np.flipud(y_neg_cum_sum_exp)
       y_neg_cum_sum_exp = np.cumsum(y_neg_cum_sum_exp)
       y_neg_cum_sum_exp = np.flipud(y_neg_cum_sum_exp)

    for idx in xrange(len(X)):
        V[idx] = sMCI(X[idx], y, ksize, y_neg_cum_sum_exp, y_pos_cum_sum_exp)

    return V

def pMCIdistance(X, y, ksize, X_neg_exp=None, X_pos_exp=None, \
                 X_neg_cum_sum_exp=None, X_pos_cum_sum_exp=None, MCI11=None):
    """
    Memoryless Cross Intensity kernel (mCI) based squared distance 
    Input:
        X: is a length M of numpy arrays of sorted spike times
        y: (N2x1) numpy array of sorted spike times
        ksize: kernel size
        y_neg_cum_sum_exp = sum_j exp(-y[-j]/ksize)
        y_pos_cum_sum_exp = sum_j exp(y[j]/ksize)
    Output:
        V_k: (numpy.array) mci(X_i, X_i) + mci(y, y) - 2*mci(X_i, y)
    """
    V = np.zeros(len(X));
    
    # This avoids repetitive computations at the mci based distance step
    # This current implementations allows full or no knowledge about X    
    # TODO: allows input of knowledge about only few spike trains
    if X_neg_exp is None or X_pos_exp is None or X_neg_cum_sum_exp is None \
    or X_pos_cum_sum_exp is None:     
        X_pos_exp = range(len(X))
        X_neg_exp = range(len(X))
        X_neg_cum_sum_exp = range(len(X))
        X_pos_cum_sum_exp = range(len(X))
        for idx in xrange(len(X)):
            X_pos_exp[idx] = np.exp(-X[idx] / ksize)
            X_pos_cum_sum_exp[idx] = np.cumsum(X_pos_exp[idx])
            
            X_neg_exp[idx] = np.exp(-X[idx] / ksize)
            X_neg_cum_sum_exp[idx] = np.flipud(X_neg_exp[idx])
            X_neg_cum_sum_exp[idx] = np.cumsum(X_neg_cum_sum_exp[idx])
            X_neg_cum_sum_exp[idx] = np.flipud(X_neg_cum_sum_exp[idx])    
    
    if MCI11 is None:
        MCI11 = range(len(X))        
        for idx in xrange(len(X)):
            # This means zero optimization! Sometimes the "population" X is just 
            #     sliding versions os a spike train. This can be exploited to avoid
            #     extra calculations.    
            # TODO: pipeline the calculation of mCI for sliding input spike trains        
            MCI11[idx] = 0.
            for k in xrange((X[idx]).shape[0]):
                if k == 1:
                    MCI11[idx] = MCI11[idx] + X_pos_exp[idx][0] * \
                    X_neg_cum_sum_exp[idx][0]
                elif k == (X[idx]).shape[0]-1:
                    MCI11[idx] = MCI11[idx] + X_neg_exp[idx][-1] * X_pos_cum_sum_exp[idx][-1]
                else:
                    MCI11[idx] = MCI11[idx] + X_pos_cum_sum_exp[idx][k] * \
                    X_neg_exp[idx][k] + X_pos_exp[idx][k] * X_neg_cum_sum_exp[idx][k+1]
        
    for idx in xrange(len(X)):
        V[idx] = sMCIdistance(X[idx], y, ksize, x_neg_exp = X_neg_exp[idx], \
                x_pos_exp=X_pos_exp[idx], x_neg_cum_sum_exp=X_neg_cum_sum_exp[idx],\
                x_pos_cum_sum_exp=X_pos_cum_sum_exp[idx], mci11=MCI11[idx])

    return V
    
def pNCI(X, y, ksize, gamma, X_neg_exp=None, X_pos_exp=None, \
                 X_neg_cum_sum_exp=None, X_pos_cum_sum_exp=None, MCI11=None):
    """
    Nonlinear Cross Intensity kernel (mCI) based distance
    Input:
        X: is a length M of numpy arrays of sorted spike times
        y: (N2x1) numpy array of sorted spike times
        ksize: kernel size
        y_neg_cum_sum_exp = sum_j exp(-y[-j]/ksize)
        y_pos_cum_sum_exp = sum_j exp(y[j]/ksize)
    Output:
        V_k: exp(-gamma*squared_MCI_distance(X_k, y))  
    """
    #if X is numpy array, then X = [X]    
    V = np.zeros(len(X));
    
    V = pMCIdistance(X, y, ksize, X_neg_exp=X_neg_exp, X_pos_exp=X_pos_exp,\
                     X_neg_cum_sum_exp=X_neg_cum_sum_exp, \
                     X_pos_cum_sum_exp=X_pos_cum_sum_exp)
    V *= -gamma
    V = np.exp(V)
    return V
    
    
"""
==========================
SLASH - Inner product call
==========================
"""

# Helper functions - distance
SPIKE_KERNEL_FUNCTIONS = {
    # If updating this dictionary, update the doc in both distance_metrics()
    # and also in pairwise_distances()!
    'mci': pMCI,
    'nci': pNCI,
    'mcidistance': pMCIdistance
    }

def spike_kernels():
    """ Valid kernels for inner_prod

    This function simply returns the valid spike kernsl.
    It exists, however, to allow for a verbose description of the mapping for
    each of the valid strings.

    The valid distance metrics, and the function they map to, are:
      ===============   ========================================
      metric            Function
      ===============   ========================================
      'mci'             slash.MCI
      'nci'             slash.NCI
      ===============   ========================================
    """
    return SPIKE_KERNEL_FUNCTIONS
    
KERNEL_PARAMS = {
    "mci": frozenset(["ksize"]),
    "nci": frozenset(["ksize", "gamma"]),
    "mcidistance": frozenset(["ksize"])
}

def inner_prod(X, Y=None, spike_kernel="mci", filter_params=False, n_jobs=1, \
               **kwds):
    """Compute the spike kernel between spike trains X and optional array Y.

    This method takes either a spike trains or a kernel matrix, and returns a 
    kernel matrix. If the input is a vector array, the kernels are computed. 
    If the input is a kernel matrix, it is returned instead.

    This method provides a safe way to take a kernel matrix as input, while
    preserving compatibility with many other algorithms that take a vector
    array.

    If Y is given (default is None), then the returned matrix is the pairwise
    kernel between the arrays from both X and Y.

    Valid values for spike_kernel are::
        ['mci', 'nci']

    Parameters
    ----------
    X : array [n_samples_a, n_samples_a] if spike_kernel == "precomputed", or,
              [n_samples_a, n_features] otherwise
        Array of pairwise kernels between samples, or a feature array.

    Y : array [n_samples_b, n_features]
        A second feature array only if X has shape [n_samples_a, n_features].

    spike_kernel : string, or callable
        The spike kernel to use when calculating inner product between instances 
        in a spike train. If spike_kernel is a string, it must be one of the ones
        in slash.SPIKE_KERNEL_FUNCTIONS.
        If spike_kernel is "precomputed", X is assumed to be a kernel matrix.
        Alternatively, if metric is a callable function, it is called on each
        pair of instances (rows) and the resulting value recorded. The callable
        should take two arrays from X as input and return a value indicating
        the distance between them.

    n_jobs : int
        The number of jobs to use for the computation. This works by breaking
        down the pairwise matrix into n_jobs even slices and computing them in
        parallel.

        If -1 all CPUs are used. If 1 is given, no parallel computing code is
        used at all, which is useful for debuging. For n_jobs below -1,
        (n_cpus + 1 + n_jobs) are used. Thus for n_jobs = -2, all CPUs but one
        are used.

    filter_params: boolean
        Whether to filter invalid parameters or not.

    `**kwds` : optional keyword parameters
        Any further parameters are passed directly to the kernel function. For
        example, the kernel size ksize or gamma value for nCI

    Returns
    -------
    K : array [n_samples_a, n_samples_a] or [n_samples_a, n_samples_b]
        A kernel matrix K such that K_{i, j} is the kernel between the
        ith and jth spike trains of the given list X, if Y is None.
        If Y is not None, then K_{i, j} is the kernel between the ith spike 
        train X and the jth spike train from Y.

    Notes
    -----
    If metric is 'precomputed', Y is ignored and X is returned.

    """
    if spike_kernel == "precomputed":
        return X
    elif spike_kernel in SPIKE_KERNEL_FUNCTIONS:
        if filter_params:
            kwds = dict((k, kwds[k]) for k in kwds
                        if k in KERNEL_PARAMS[spike_kernel])
        func = SPIKE_KERNEL_FUNCTIONS[spike_kernel]
        if n_jobs == 1:
            return func(X, Y, **kwds)
        else:
            return _parallel_inner_prod(X, Y, func, n_jobs, **kwds)
    elif callable(spike_kernel):
        # Check matrices first (this is usually done by the metric).
        #X, Y = check_pairwise_arrays(X, Y)
        n_x, n_y = len(X), len(Y)
        # Calculate kernel for each element in X and Y.
        K = np.zeros((n_x, n_y), dtype='float')
        for i in range(n_x):
            start = 0
            if X is Y:
                start = i
            for j in range(start, n_y):
                # Kernel assumed to be symmetric.
                K[i][j] = spike_kernel(X[i], Y[j], **kwds)
                if X is Y:
                    K[j][i] = K[i][j]
        return K
    else:
        raise ValueError("Unknown kernel %r" % spike_kernel)
    return

    
def _parallel_inner_prod(X, Y, func, n_jobs, **kwds):
    """Break the pairwise matrix in n_jobs even slices
    and compute them in parallel"""
    if n_jobs < 0:
        n_jobs = max(cpu_count() + 1 + n_jobs, 1)

    if Y is None:
        Y = X

    ret = Parallel(n_jobs=n_jobs, verbose=0)(
        delayed(func)(X[s], Y, **kwds)
        for s in gen_even_slices(len(X), n_jobs))

    return np.hstack(ret)


"""
====================
TESTS
====================
"""
def test_sMCI():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    v = sMCI(x, y, .01)
    print "Test_sMCI v = %10.5e" % v
    return

def test_sMCIdistance():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    v = sMCIdistance(x, y, .01)
    print "Test_sMCIdistance v = %10.5e" % v
    return

def test_sNCI():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    v = sNCI(x, y, .01, .01)
    print "Test_sNCI v = %10.5e" % v
    return

def test_pMCI():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    X = [np.array([]), x]
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    V = pMCI(X, y, .01)
    print "Test_pMCI V = [%10.5e, %10.5e]" % (V[0], V[1])
    return

def test_pMCIdistance():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    X = [np.array([]), x]
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    V = pMCIdistance(X, y, .01)
    print "Test_pMCIdistance V = [%10.5e, %10.5e]" % (V[0], V[1])
    return
    
def test_pNCI():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    X = [np.array([]), x]
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])
    V = pNCI(X, y, .01, .01)
    print "Test_pNCI V = [%10.5e, %10.5e]" % (V[0], V[1])
    return

def test_InnerProd():
    x = np.array([0.0010, 0.0020, 0.0200,  0.0300, 0.3000,])
    X = [np.array([]), x]
    y = np.array([0.0040, 0.0050, 0.0200, 0.4000, 0.5000, 0.6000])

    params = {"gamma": .01,
              "ksize": .01}
    
    V = inner_prod(X, y, spike_kernel="nci", n_jobs=1, filter_params=True \
                  **params)
    print "Test_InnerProd V = [%10.5e, %10.5e]" % (V[0], V[1])
    return
    