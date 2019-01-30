
import numpy as np
import pandas as pd
# from bayes_opt import BayesianOptimization
from hyperopt import hp, tpe, fmin
from hyperopt import Trials


import algorithms

"""
hyperopt
https://conference.scipy.org/proceedings/scipy2013/pdfs/bergstra_hyperopt.pdf
"""

########################################################################################################################
class Integrator:
    def __init__(self, dict_nets_to_integrate, transformation_function, operation_function):
        self.l_nets_to_integrate = list(dict_nets_to_integrate.values())
        self.network_names = list(dict_nets_to_integrate.keys())
        self.transformation_function = transformation_function
        self.operation_function = operation_function

    def integrate(self, gamma=None):
        if gamma is None:
            n_nets = len(self.l_nets_to_integrate)
            gamma = np.ones(n_nets)/n_nets
        w = self.transformation_function(self.l_nets_to_integrate[0]) * gamma[0]
        for g, net in zip(gamma[1:], self.l_nets_to_integrate[1:]):
            w = self.operation_function(w, self.transformation_function(net) * g)

        w.kind = self.l_nets_to_integrate[0].kind # same kind, laplacian or adjacency as the ones in the combination
        return w


class AdditiveMethods(Integrator):
    def __init__(self, l_nets_to_integrate, transformation_function):
        def operation_function(w, net):
            return w+net
        Integrator.__init__(self, l_nets_to_integrate, transformation_function, operation_function)


class MultiplicativeMethods(Integrator):
    def __init__(self, l_nets_to_integrate, transformation_function):
        def operation_function(w, net):
            return w*net
        Integrator.__init__(self, l_nets_to_integrate, transformation_function, operation_function)


class LaplacianMethods(Integrator):
    """
    This class incorporates the method to recover the possible adjacency matrix that could generate the laplacian.
    """
    def __init__(self, exponent):
        self.exponent = exponent

    def find_adjacency(self, w, max_iter=100):
        if w.strength is None:
            w.strength = np.ones(w.matrix.shape[0]) # initialize all strength in one.

        for i in range(max_iter):
            new_strength = algorithms.normalize_by_strength(w.matrix, -self.exponent, w.strength, exponent_sign=1).sum(axis=0)
            new_strength = new_strength/new_strength.sum()*w.strength.sum()
            if np.allclose(new_strength, w.strength):
                break
            w.strength = new_strength

        w.to_adjacency()
        return w

    def integrate(self, gamma=None, return_laplacian=False):
        w = Integrator.integrate(self, gamma)
        w.exponent = self.exponent
        if not return_laplacian:
            w = self.find_adjacency(w)

        return w


class SimpleMethods(Integrator):
    """
    This class incorporates the method to recover the possible adjacency matrix that could generate the laplacian.

    TODO: code correctly the find adjacency method
    """
    def __init__(self, exponent):
        self.exponent = exponent

    def integrate(self, gamma=None, return_laplacian=False):
        w = Integrator.integrate(self, gamma)
        if return_laplacian:
            w.to_laplacian(self.exponent)

        return w


# ------------------------------------------------------
# integration methods upper classes

class SimpleMultiplicative(MultiplicativeMethods, SimpleMethods):
    def __init__(self, l_nets_to_integrate, exponent=0.5):
        def transformation_function(net):
            net.to_adjacency()
            return net
        MultiplicativeMethods.__init__(self, l_nets_to_integrate, transformation_function)
        SimpleMethods.__init__(self, exponent)


class SimpleAdditive(AdditiveMethods, SimpleMethods):
    def __init__(self, l_nets_to_integrate, exponent=0.5):
        def transformation_function(net):
            net.to_adjacency()
            return net
        AdditiveMethods.__init__(self, l_nets_to_integrate, transformation_function)
        SimpleMethods.__init__(self, exponent)


class LaplacianMultiplicative(MultiplicativeMethods, LaplacianMethods):
    def __init__(self, l_nets_to_integrate, exponent):
        def transformation_function(net):
            net.to_laplacian(exponent)
            return net
        MultiplicativeMethods.__init__(self, l_nets_to_integrate, transformation_function)
        LaplacianMethods.__init__(self, exponent)


class LaplacianAdditive(AdditiveMethods, LaplacianMethods):
    def __init__(self, l_nets_to_integrate, exponent):
        def transformation_function(net):
            net.to_laplacian(exponent)
            return net
        AdditiveMethods.__init__(self, l_nets_to_integrate, transformation_function)
        LaplacianMethods.__init__(self, exponent)


########################################################################################################################
class OptimizeIntegrator:
    """
    TODO: optimization with constraints in gamma. Now there is no sum=1; so normalization should be performed afterwards
    """

    def __init__(self, evaluator):
        self.evaluator = evaluator

    def randomly(self, integrator, max_evals, return_laplacian=True):

        def get_gamma():
            gamma = []
            probability_rest = 1
            for _ in integrator.network_names[:-1]:  # do except the last one
                gamma.append(np.random.uniform(0, 1)*probability_rest)
                probability_rest = probability_rest*(1-gamma[-1])
            gamma.append(probability_rest)  # the remaining probability goes to te last

            return np.array(gamma)

        results_cols = integrator.network_names+[self.evaluator.metric_name]
        tpe_results = pd.DataFrame([], columns=results_cols)
        for i in range(max_evals):
            gamma = get_gamma()
            temp_result = pd.Series(np.nan, index=results_cols)
            temp_result[integrator.network_names] = gamma
            temp_result[self.evaluator.metric_name] = self.evaluator.evaluate(integrator.integrate(gamma, return_laplacian))

            tpe_results = tpe_results.append(temp_result, ignore_index=True)

        best = tpe_results.loc[tpe_results[self.evaluator.metric_name].idxmax(), :]
        return tpe_results, best

    def optimize(self, integrator, max_evals, maximize=True, return_laplacian=True):
        """

        :param integrator:
        :param max_evals:
        :param gamma_bounds:
        :param maximize:
        :return:
        """
        if maximize:
            sign = -1
        else:
            sign = 1

        def get_gamma_from_values(values):
            gamma = []
            probability_rest = 1
            for val in values[:-1]:  # do except the last one
                gamma.append(val*probability_rest)
                probability_rest = probability_rest*(1-val)
            gamma.append(probability_rest)  # the remaining probability goes to te last

            return np.array(gamma)

        def optim_func(space):
            gamma = get_gamma_from_values(list(space.values()))
            return self.evaluator.evaluate(integrator.integrate(gamma, return_laplacian))

        space = {network_name: hp.uniform(network_name, 0, 1) for network_name in integrator.network_names}

        # ojo que hay que maximizar entonces va el -
        tpe_trials = Trials()
        best = fmin(fn=lambda sp: sign*optim_func(sp),
                    space=space,
                    trials=tpe_trials,
                    algo=tpe.suggest,
                    max_evals=max_evals)

        tpe_results = {network_name: gamma_values for network_name, gamma_values in tpe_trials.idxs_vals[1].items()}
        tpe_results[self.evaluator.metric_name] = [sign*x['loss'] for x in tpe_trials.results]
        tpe_results = pd.DataFrame(tpe_results)
        # Warning, normalization so it sums up to 1.
        for ix, row in tpe_results.iterrows():
            tpe_results.loc[ix, list(space.keys())] = get_gamma_from_values(row[list(space.keys())])
        # tpe_results[integrator.network_names] = tpe_results[integrator.network_names].div(tpe_results[integrator.network_names].sum(axis=1), axis=0)

        best = pd.Series(best)
        best[self.evaluator.metric_name] = tpe_results[self.evaluator.metric_name].max()
        best[list(space.keys())] = get_gamma_from_values(best[list(space.keys())])
        return tpe_results, best

########################################################################################################################
if __name__=="__main__":
    # simple = Simple(False)
    # simple.integrate([0, 1, 2])

    # n = Network(np.array([[0, 1, 1, 0],
    #                       [1, 0, 1, 0],
    #                       [1, 1, 0, 1],
    #                       [0, 0, 1, 0]]))
    #
    # m = Network(np.array([[1, 0, 1, 0],
    #                       [0, 0, 1, 1],
    #                       [1, 1, 0, 1],
    #                       [0, 1, 1, 0]]))
    #
    # # print(n.matrix)
    # # a = n*n
    # #
    # # print(a.get_strength())
    # # print(a)
    # # a.to_laplacian(1)
    # # print(a)
    # # a.to_adjacency()
    # # print(a)
    #
    # # -------------------
    # gamma = [0.5, 0.5]
    # exponent = 1
    #
    # n.to_laplacian(exponent)
    # print(n)
    #
    # add = SimpleAdditive([n, m])
    # w_add = add.integrate(gamma, return_laplacian=False)
    # add_lap = LaplacianAdditive([n, m], exponent=exponent)
    # w_addlap = add_lap.integrate(gamma, return_laplacian=False)
    #
    # mul = SimpleMultiplicative([n, m])
    # w_mul = mul.integrate(return_laplacian=False)
    # mul_lap = LaplacianMultiplicative([n, m], exponent=exponent)
    # w_mullap = mul_lap.integrate(return_laplacian=False)
    #
    # # print(w_add)
    # print(w_addlap)
    # n.to_laplacian(exponent)
    # print(n)
    # m.to_laplacian(exponent)
    # print(m)
    #
    # # print(w_mul)
    # # print(w_mullap)

    ###################################################3
    import numpy as np
    from evaluators import AUROClinkage

    p1 = 0.6
    n_targets = 2
    alpha = 0.5
    N = 1000
    max_evals = 1
    max_fpr = (1-p1)/2

    laplacian_exponent = -0.5
    max_iter = 100
    auroc_normalized = False

    # --------------------------
    # x = np.random.uniform(size=(N, N))
    # network = algorithms.Network(1*((x + x.T) >= 1))
    x = np.roll(np.eye(N), 1, axis=0)
    network_1 = algorithms.Network(x + x.T)
    network_2 = algorithms.Network(x)
    x = np.random.uniform(size=(N, N))
    network_3 = algorithms.Network(1*((x + x.T) > 1))
    # print(network)

    d_networks = {"Net1": network_1, "Net2": network_2}#, "Net3": network_3}
    integrator = SimpleAdditive(d_networks)
    integrator = LaplacianAdditive(d_networks, -0.5)

    # --------------------------
    seeds_matrix = np.eye(N)
    targets_list = [np.roll(np.arange(N), -n)[1:(n_targets + 1)] for n in range(N)]

    p = np.repeat((1 - p1) / (n_targets - 1), n_targets - 1)
    p = np.insert(p, 0, p1)
    print(p)
    true_targets = [[int(np.random.choice(targets, size=1, p=p))] for targets in targets_list]


    # seeds_matrix = np.eye(N)
    # targets_list = np.array([np.roll(np.arange(N), -n)[1:] for n in range(N)]).T
    # targets_list = targets_list[:n_targets, :]
    # true_targets = np.zeros(targets_list.shape)
    # true_targets[1, :] = 1

    # x = np.roll(np.eye(N), 1, axis=0)
    # network_1 = algorithms.Network(x)

    # --------------------------
    evaluator = AUROClinkage(seeds_matrix,
                             targets_list,
                             true_targets,
                             alpha=alpha,
                             tol=1e-08,
                             max_iter=max_iter,
                             max_fpr=max_fpr,
                             laplacian_exponent=laplacian_exponent,
                             auroc_normalized=auroc_normalized)
    # evaluator = AUROClinkage(seeds_matrix, targets_list, true_targets, alpha, tol=1e-08, max_iter=100, max_fpr=max_fpr)
    print(evaluator.metric_name)
    optimizeAUClinkage = OptimizeIntegrator(evaluator)
    tpe_trials, best = optimizeAUClinkage.optimize(integrator=integrator, max_evals=max_evals, maximize=True)
    print(tpe_trials)
    print(best)

    tpe_trials, best = optimizeAUClinkage.randomly(integrator=integrator, max_evals=max_evals)
    print(tpe_trials)
    print(best)

    # print((5*p1-4*p1**2)/8)
    print(p1*(1-p1)/8)

