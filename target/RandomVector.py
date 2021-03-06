import abc

'''
Abstract class defining the target random vector being matched by an SROM.
Inherited by AnalyticRV and SampleRV to define analytically specified and 
sample-based random vectors, respectively.
'''

#Any overlapping functions/variables that make this necessary?

class RandomVector(object):

    def __init__(self, dim):

        self._dim = int(dim)

    @abc.abstractmethod
    def compute_moments(self, max_order):
        return
    
    @abc.abstractmethod
    def compute_CDF(self, x_grid):
        return

    @abc.abstractmethod
    def compute_corr_mat(self):
        return

    @abc.abstractmethod
    def draw_random_sample(self, sample_size):
        return
