'''
Class to solve SROM optimization problem.
'''

import numpy as np
import scipy.optimize as opt
import time

#from srom import SROM
from optimize import ObjectiveFunction
from optimize import Gradient


#------------Helper funcs for scipy optimize-----------------------------
def scipy_obj_fun(x, objfun, grad, samples):
    '''
    Function to pass to scipy minimize defining objective. Wraps the 
    ObjectiveFunction.evaluate() function that defines SROM error. Need to 
    unpack design variables x into samples & probabilities. Handle two cases:

    1) joint optimization over samples & probs (samples=None)
    2) sequential optimization -> optimize probs for fixed samples
    '''

    size = objfun._SROM._size
    dim = objfun._SROM._dim

    #Unpacking simple with samples are fixed:
    probs = x

    error = objfun.evaluate(samples, probs)

    return error

def scipy_grad(x, objfun, grad, samples):
    '''
    Function to pass to scipy minimize defining objective. Wraps the 
    ObjectiveFunction.evaluate() function that defines SROM error. Need to 
    unpack design variables x into samples & probabilities. Handle two cases:

    1) joint optimization over samples & probs (samples=None)
    2) sequential optimization -> optimize probs for fixed samples
    '''

    size = grad._SROM._size
    dim = grad._SROM._dim

    #Unpacking simple with samples are fixed:
    probs = x

    grad = grad.evaluate(samples, probs)
    return grad

#-----------------------------------------------------------------


class Optimizer:
    '''
    Class that delegates the construction of an SROM through the optimization 
    of the SROM parameters (samples/probs) that minimize the error between
    SROM & target random vector
    '''

    def __init__(self, target, srom, obj_weights=None, error='SSE',
                 max_moment=5, cdf_grid_pts=100):
        '''

        inputs:
            -target - initialized RandomVector object (either AnalyticRV or 
                SampleRV) 
            -obj_weights - array of floats defining the relative weight of the 
                terms in the objective function. Terms are error in moments,
                CDFs, and correlation matrix in that order. Default will give
                each term equal weight
            -error - string 'mean' or 'max' defining how error is defined 
                between the statistics of the SROM & target
            -max_moment - int, max order to evaluate moment errors up to
            -cdf_grid_pts - int, # pts to evaluate CDF errors on

        '''

        #TODO Do some error checking on target
        self._target = target
        
        #Get srom size & dimension
        self._sromsize = srom._size
        self._dim = srom._dim

        #Initialize objective function defining SROM vs target error
        self._srom_obj = ObjectiveFunction(srom, target, obj_weights, error,
                                           max_moment, cdf_grid_pts)

        self._srom_grad = Gradient(srom, target, obj_weights, error,
                                           max_moment, cdf_grid_pts)

        #Gradient only available for SSE error obj function
        if error.upper() == "SSE":
            self._grad = scipy_grad
        else:
            self._grad = None

    def get_optimal_params(self, num_test_samples=500, tol=None, options=None,
                           method=None, output_interval=10):
        '''
        Solve the SROM optimization problem - finds samples & probabilities
        that minimize the error between SROM/Target RV statistics.

        inputs:
            -joint_opt, bool, Flag for optimizing jointly for samples & probs 
                rather than sequentially (draw samples then optimize probs in 
                loop - default). 
            -num_test_samples, int, If optimizing sequentially (samples then
                probs), this is number of random sample sets to test in opt
            -tol, float, tolerance of scipy optimization algorithm
            -options, dict, options for scipy optimization algorithm
            -method, str, method specifying scipy optimization algorithm
            -output_interval, int, how often to print optimization progress    

        returns optimal SROM samples & probabilities

        '''

        joint_opt = False #Not implemented yet
        bounds = self.get_param_bounds(joint_opt, self._sromsize)
        constraints = self.get_constraints(joint_opt, self._sromsize, self._dim)
        initial_guess = self.get_initial_guess(joint_opt, self._sromsize)

        #Track optimal func value with corresonding samples/probs
        opt_probs = None
        opt_samples = None        
        opt_fun = 1e6

        print "SROM Sequential Optimizer:"
        t0 = time.time()

        for i in xrange(num_test_samples):
    
            #Randomly draw new 
            srom_samples =  self._target.draw_random_sample(self._sromsize)

            #Optimize using scipy
            opt_res = opt.minimize(scipy_obj_fun, initial_guess,
                                   args=(self._srom_obj, self._srom_grad,
                                            srom_samples),
                                   jac=self._grad,
                                   constraints=(constraints), 
                                   method=method,
                                   bounds=bounds)

            #If error is lower than lowest so far, keep track of results
            if opt_res['fun'] < opt_fun:
                opt_samples = srom_samples
                opt_probs = opt_res['x']
                opt_fun = opt_res['fun']
            
            if i==0 or (i+1)%output_interval==0:
                print "\tIteration",i+1, "Objective Function:", opt_res['fun'],
                print "Optimal:", opt_fun

        #Display final errors in statistics:
        momenterror = self._srom_obj.get_moment_error(opt_samples, opt_probs)
        cdferror = self._srom_obj.get_cdf_error(opt_samples, opt_probs)
        correlationerror = self._srom_obj.get_corr_error(opt_samples, opt_probs)

        print "\tOptimization time: ", time.time()-t0, "seconds"
        print "\tFinal SROM errors:"
        print "\t\tCDF: ", cdferror
        print "\t\tMoment: ", momenterror
        print "\t\tCorrelation: ", correlationerror

        return (opt_samples, opt_probs)

    #-----Helper funcs----
    
    def get_param_bounds(self, joint_opt, sromsize):
        '''
        Get the bounds on parameters for SROM optimization problem. If doing
        joint optimization, need bounds for both samples & probs. If not,
        just need trivial bounds on probabilities
        '''
        
        if not joint_opt:
            bounds = [(0.0,1.0)]*sromsize
        else:
            raise NotImplementedError("SROM joint optimization not implemented")

        return bounds
        
    def get_constraints(self, joint_opt, sromsize, dim):
        '''
        Returns constraint dictionaries for scipy optimize that enforce 
        probabilities summing to 1 for joint or sequential optimize case
        '''

        #A little funky, need to return function as constraint. 
        #TODO - use lambda function instead?

        #Sequential case - unknown vector x is probabilities directly
        def seq_constraint(x):
            return 1.0 - np.sum(x)
        #Joint case - probabilities at end of unknown vector x
        def joint_constraint(x, sromsize, dim):
            return 1.0 - np.sum(x[sromsize*dim:])

        if not joint_opt:
            return {'type':'eq', 'fun':seq_constraint}
        else:
            return {'type':'eq', 'fun':joint_constraint, 'args':(sromsize, dim)}
        
        
    def get_initial_guess(self, joint_opt, sromsize):
        '''
        Return initial guess for optimization. Randomly drawn samples w/ equal
        probability for joint optimization or just equal probabilities for 
        sequential optimization
        '''
    
        if joint_opt:
            #Randomly draw some samples & hstack them with probabilities 
            #TODO - untested
            samples  =  self._target.draw_random_sample(sromsize)
            probs = (1./float(sromsize))*np.ones((sromsize))
            initial_guess = np.hstack((samples.flatten(), probs))
        else:
            initial_guess = (1./float(sromsize))*np.ones((sromsize))

        return initial_guess
