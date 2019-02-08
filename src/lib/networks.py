
import numpy as np
import pandas as pd

# ----
import algorithms


######################################################
#           Constants
DEFAULT_LAPLACIAN_EXPONENT = -0.5


########################################################################################################################
"""

:param adj_matrix: adjacency matrix of the graph. ndarray

TODO: laplacian with D-A
TODO: make laplacians conservative

        :param network_mode:
            "adjacency" if it is the adjacency matrix of the graph
            "lambda-laplacian" if it is the laplacian of the graph by multiplying strength matrix to some exponent
            "laplacian" if it is the laplacian: D-A
        :param laplacian_exponent:
            laplacian laplacian_exponent:
                0 for the random walk laplacian.
                0.5 for the symmetric laplacian.
                1 for the heat laplacian.

"""


class Network:
    def __init__(self, matrix, node_names=None):
        assert type(matrix) == np.ndarray
        assert matrix.shape[0] == matrix.shape[1]
        self.matrix = matrix

        if node_names is None:
            self.node_names = np.arange(self.matrix.shape[0])
        else:
            assert len(node_names) == self.matrix.shape[0]
            self.node_names = node_names

    def __add__(self, other):
        pass

    def __mul__(self, other):
        pass

    def __rmul__(self, other):
        # it is conmutative
        return self.__mul__(other)

    def __str__(self):
        return "Number of nodes: {}\nMatrix: \n {}".format(self.number_of_nodes(), self.matrix)

    def number_of_nodes(self):
        return len(self.node_names)

    def set_nodes(self, new_set_of_nodes):
        """
        TODO: warning, not memory efficient. creating zeros matrix unnecessarily.
        """
        # self.matrix = pd.DataFrame(self.matrix, columns=self.node_names, index=self.node_names)
        # self.matrix = self.matrix.loc[new_set_of_nodes, new_set_of_nodes].fillna(0).values

        common_nodes_ix = [i for i, node in enumerate(self.node_names) if node in new_set_of_nodes]
        number_of_common_nodes = len(common_nodes_ix)
        temp_matrix = np.zeros((len(new_set_of_nodes), len(new_set_of_nodes)))
        temp_matrix[:number_of_common_nodes,:][:,:number_of_common_nodes] = \
            self.matrix[:, common_nodes_ix][common_nodes_ix, :]
        self.matrix = temp_matrix
        self.node_names = list(np.append(np.array(self.node_names)[common_nodes_ix],
                                         np.array(list(set(new_set_of_nodes).difference(self.node_names)))))


class Adjacency(Network):
    def __init__(self, matrix, node_names=None):
        self.__name__ = "adjacency"
        Network.__init__(self, matrix, node_names)

        # degree or strength (in weighted networks) of the network
        self.strength = np.array(np.squeeze(self.matrix.sum(axis=1)), dtype=float)

    def __add__(self, other):
        if type(other) == type(self):
            assert np.all(self.node_names == other.node_names)
            returned_matrix = self.matrix + other.matrix
        else:
            returned_matrix = self.matrix + other
        return Adjacency(returned_matrix, node_names=self.node_names)

    def __mul__(self, other):
        if type(other) == type(self):
            assert np.all(self.node_names == other.node_names)
            returned_matrix = self.matrix * other.matrix
        else:
            returned_matrix = self.matrix * other
        return Adjacency(returned_matrix, node_names=self.node_names)

    def get_laplacian(self, laplacian_exponent=DEFAULT_LAPLACIAN_EXPONENT):
        return Laplacian(matrix=algorithms.DAD(self.matrix, diagonal1=self.strength, exponent1=laplacian_exponent),
                         strength=self.strength,
                         laplacian_exponent=laplacian_exponent,
                         node_names=self.node_names)


class Laplacian(Network):
    def __init__(self, matrix, strength, laplacian_exponent, node_names=None):
        self.__name__ = "laplacian_{}".format(laplacian_exponent)
        Network.__init__(self, matrix, node_names)

        # degree or strength (in weighted networks) of the network
        self.strength = strength
        self.laplacian_exponent = laplacian_exponent

    def __add__(self, other):
        if type(other) == type(self):
            assert np.all(self.node_names == other.node_names)  # both should in the same order and have the same names.
            assert self.laplacian_exponent == other.laplacian_exponent  # both should have the same laplacian exponent.
            returned_matrix = self.matrix + other.matrix
            strength = None  # we can't tell what will be the strength of the sum of two laplacians... a speciall method
            # is needed.
        else:
            returned_matrix = self.matrix + other
            strength = self.strength
        return Laplacian(returned_matrix,
                         strength=strength,
                         laplacian_exponent=self.laplacian_exponent,
                         node_names=self.node_names)

    def __mul__(self, other):
        if type(other) == type(self):
            assert np.all(self.node_names == other.node_names)  # both should in the same order and have the same names.
            assert self.laplacian_exponent == other.laplacian_exponent  # both should have the same laplacian exponent.
            returned_matrix = self.matrix * other.matrix
            strength = None  # we can't tell what will be the strength of the sum of two laplacians... a speciall method
            # is needed.
        else:
            returned_matrix = self.matrix * other
            strength = self.strength
        return Laplacian(returned_matrix,
                         strength=strength,
                         laplacian_exponent=self.laplacian_exponent,
                         node_names=self.node_names)

    def infer_strength(self, infering_technik="ones", max_iter=100):
        """

        :param infering_technik:
        :return:
        """
        strength = np.ones(self.number_of_nodes())
        if infering_technik is "iterative":
            for i in range(max_iter):
                new_strength = algorithms.DAD(matrix=self.matrix,
                                              diagonal1=strength,
                                              exponent1=-self.laplacian_exponent).sum(axis=0)
                new_strength = new_strength / new_strength.sum() * strength.sum()
                if np.allclose(new_strength, strength):
                    break
                strength = new_strength

        return strength

    def get_adjacency(self, infering_technik="iterative", max_iter=100):
        if self.strength is None:
            self.strength = self.infer_strength(infering_technik, max_iter)
        return Adjacency(matrix=algorithms.DAD(matrix=self.matrix,
                                               diagonal1=self.strength,
                                               exponent1=-self.laplacian_exponent),
                         node_names=self.node_names)


class Bipartite:
    """
    TODO: edgelist or B matrices implement
    """
    def __init__(self, data):
        if type(data) == list:
            print("Assuming data is an adjacency list.")
        elif type(data) == pd.DataFrame:
            print("Assuming data is an edgelist list with first and second column source target and third score")
            self.edgelist = data
        else:
            raise Exception("B matrices or other methods not implemented yet")

        if self.edgelist.shape[1] == 3:
            self.score_column = self.edgelist.columns[-1]
            # if there where many edges repeated with different score values they are summed up together.
            self.edgelist = self.edgelist.groupby(self.edgelist.columns[:-1].tolist()).sum().reset_index()
        else:
            self.score_column = None

    def filter_nodes_by_intersection(self, bipartite_side_column_name, nodes=None):
        if nodes is not None:
            self.edgelist = self.edgelist.loc[self.edgelist[bipartite_side_column_name].isin(nodes)]

    def filter_edges_by_score(self, score_lower_threshold):
        if self.score_column is not None:
            self.edgelist = self.edgelist.loc[self.edgelist.loc[:, self.score_column] >= score_lower_threshold, :]
        else:
            print("There are no columns with score")

    def filter_nodes_by_degree(self, bipartite_side_column_name, degree_lower_threshold, degree_upper_threshold=np.inf):
        """It is not strength. It counts the number of edges"""
        degree = self.edgelist[bipartite_side_column_name].value_counts()
        nodes_set = degree[(degree >= degree_lower_threshold) & (degree <= degree_upper_threshold)].index
        self.edgelist = self.edgelist.loc[self.edgelist[bipartite_side_column_name].isin(nodes_set), :]

    def get_nodes_ids(self, bipartite_side_column_name):
        return self.edgelist[bipartite_side_column_name].unique()

    def get_target_column_name(self, bipartite_source_column_name):
        return self.edgelist.columns[np.where(self.edgelist.columns[:-1] != bipartite_source_column_name)[0]].tolist()

    def get_neighborhood(self, source_node, bipartite_source_column_name):
        target_column_name = self.get_target_column_name(bipartite_source_column_name)
        return self.edgelist.loc[self.edgelist[bipartite_source_column_name].isin([source_node]),target_column_name[0]].unique().tolist()

    def get_proyection(self, bipartite_proyection_column_name, mode="one_mode_proyection", laplacian_exponent=-0.5, simetrize=False):
        """
        laplacian method: normalices the proyection following this methodology:
            w_{ij} = 1/k_{i}^lambda * 1/k_{j}^(1-lambda) * \sum a_{il}a_{lj}/k_{l}
            this could be written in matrix form as:
            D^-lambda*B*K*B^t*D^-(1-lambda)
            where B is the incidence matrix of the bipartite graph.
            K is the diagonal matrix with strengths of the non projecting nodes.
            D is the diagonal amtrix with strengths of the projecting nodes.
        """

        B_matrix = self.edgelist.pivot_table(values=self.edgelist.columns[2],
                                             index=bipartite_proyection_column_name,
                                             columns=self.get_target_column_name(bipartite_proyection_column_name),
                                             aggfunc='sum')
        B_matrix = B_matrix.fillna(0)

        if mode == "one_mode_proyection":
            projection =  pd.DataFrame(np.matmul(B_matrix.values, B_matrix.values.T),
                                       columns=B_matrix.index,
                                       index=B_matrix.index)
        elif "laplacian" in mode:
            k = B_matrix.values.sum(axis=0)  # strengths of not projecting nodes
            d = B_matrix.values.sum(axis=1)  # strengths of projecting nodes

            # B*K
            projection = algorithms.DAD(B_matrix.values,
                                        diagonal1=np.ones(len(d)), exponent1=1,
                                        diagonal2=k, exponent2=-1)
            # B*K*B.T
            projection = np.matmul(projection, B_matrix.values.T)
            # D^-lambda*B*K*B^t*D^-(1-lambda)
            projection = algorithms.DAD(projection,
                                        diagonal1=d, exponent1=laplacian_exponent,
                                        diagonal2=d)  # laplacian exponent 2 is automatically set to 1-laplacianexponent
            projection = pd.DataFrame(projection,
                                      columns=B_matrix.index,
                                      index=B_matrix.index)
        else:
            raise Exception("Projection mode {} not known".format(mode))

        if simetrize:
            projection = (projection + projection.T)/2
        return projection

    def get_similar_nodes(self, projection, similarity_lower_threshold):
        dict_of_nodes = dict()
        dict_of_weights = dict()
        for node, node_neig_similarity in projection.items():
            neighbours_ix = np.where(node_neig_similarity.values >= similarity_lower_threshold)[0]
            dict_of_nodes[node] = projection.index[neighbours_ix].tolist()
            dict_of_weights[node] = node_neig_similarity[neighbours_ix].tolist()

        return dict_of_nodes, dict_of_weights


if __name__ == "__main__":

    # ------ Test Bipartite ------
    edgelist = pd.DataFrame([["A", "B", 0.2], ["A", "C", 0.5], ["A", "B", 0.2], ["D", "B", 0.8]], columns=["source", "target", "score"])

    bi_net = Bipartite(edgelist)
    print(bi_net.get_neighborhood("A", "source"))
    print(bi_net.get_nodes_ids("source"))
    print(bi_net.get_nodes_ids("target"))

    bi_net.filter_edges_by_score(0.2)
    print(bi_net.get_neighborhood("A", "source"))
    print(bi_net.get_nodes_ids("source"))
    print(bi_net.get_nodes_ids("target"))

    bi_net.filter_nodes_by_degree("source", degree_lower_threshold=2)
    print(bi_net.get_neighborhood("A", "source"))
    print(bi_net.get_nodes_ids("source"))
    print(bi_net.get_nodes_ids("target"))

    bi_net.filter_nodes_by_intersection("source", ["A", "B", "C"])
    print(bi_net.get_neighborhood("A", "source"))
    print(bi_net.get_nodes_ids("source"))
    print(bi_net.get_nodes_ids("target"))

    edgelist = pd.DataFrame([["A", "1", 1], ["A", "2", 1], ["B", "2", 1], ["B", "3", 1]],
                            columns=["source", "target", "score"])
    bi_net = Bipartite(edgelist)

    assert (bi_net.get_proyection("source", "one_mode_proyection").values == np.array([[2, 1], [1, 2]])).all()
    print(bi_net.get_proyection("source", "one_mode_proyection"))
    assert (bi_net.get_proyection("source", "laplacian_1", -1, False).values == np.array([[3.0/4, 1/4], [1/4, 3/4]])).all()
    print(bi_net.get_proyection("source", "laplacian_1", -1, False))

    # ------ Test Adjacency ------
    N = 5
    x = np.roll(np.eye(N), 1, axis=0)
    network_1 = Adjacency(x + x.T)
    print(network_1)
    print(network_1.get_laplacian(-0.4))

    x=np.array([[0, 1, 1, 0],
                [1, 0, 1, 0],
                [1, 1, 0, 1],
                [0, 0, 1, 0]])

    network_2 = Adjacency(x)
    print(network_2)

    laplacian2 = network_2.get_laplacian(-0.5)
    print(laplacian2)
    assert np.allclose(laplacian2.matrix[0], np.array([ 0, 1/2, 1/np.sqrt(6), 0]))
    assert np.allclose(laplacian2.matrix[1][2:], np.array([1/np.sqrt(6), 0]))
    assert np.allclose(laplacian2.matrix[2][-1], np.array([1/np.sqrt(3)]))

    laplacian2 = network_2.get_laplacian(-0.25)
    print(laplacian2)
    assert np.allclose(laplacian2.matrix[0], np.array([0, 1 / 2, 1 / (np.power(2, 1 / 4) * np.power(3, 3 / 4)), 0]))
    assert np.allclose(laplacian2.matrix[1][2:], np.array([1 / (np.power(2, 1 / 4) * np.power(3, 3 / 4)), 0]))
    assert np.allclose(laplacian2.matrix[2][-1], np.array([1 / np.power(3, 1 / 4)]))
