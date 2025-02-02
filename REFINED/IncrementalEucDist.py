import numpy as np
import pandas as pd
from scipy.spatial.distance import euclidean
from sklearn.metrics.pairwise import euclidean_distances
def IncrementalEucDist(n, filename): # сделать с меммап
    Euc_Dist = np.zeros(shape=(n, n))
    for i in range(n):
        x = pd.read_csv(filename, usecols=[i])
        x = x.iloc[:, 0].to_list()
        for j in range(n):
            if i <= j:
                continue
            y = pd.read_csv(filename, usecols=[j])
            y = y.iloc[:, 0].to_list()
            Euc_Dist[i][j] = euclidean(x, y)
    Euc_Dist = np.maximum(Euc_Dist, Euc_Dist.T)
    return Euc_Dist


mmapped_array = np.memmap("memmapped.dat", mode = "r", shape=(100, 19), dtype='float64')
Euc_Dist = euclidean_distances(mmapped_array)

