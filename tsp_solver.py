import copy
import logging
import math
import os

from collections import defaultdict

from itertools import permutations
import pandas as pd
import such_json as json

import gurobipy as gp
from gurobipy import GRB

from data.station import NearestStation
from caching import Cache

FINAL_DESTINATION = (7.44411, 46.9469)
INDEX_OF_ARTIFICAL_NODE = 99


class TspSolver:
    def __init__(self, cache, data, importedDistance, euclidean=False):
        self.euclidean = euclidean
        # Extract latitude, longitude, and Canton information
        self.data = data
        self.cache = cache
        self.latitudes = data['Latitude']
        self.longitudes = data['Longitude']
        self.cantons = data['Canton']
        self.rearranged_tour = None

        self._coordinates = list(importedDistance.keys())
        self.checkpoints = self.determine_checkpoints_to_visit()
        self.nodes = [INDEX_OF_ARTIFICAL_NODE] + list(self.checkpoints.keys())
        # Retrieve the first key matching the value, or None if not found
        self.index_of_final_destination = next(
            (key for key, value in self.checkpoints.items() if tuple(value) == FINAL_DESTINATION), None)
        self.distances = self.augment_distance(importedDistance)
        self.model = gp.Model()

    def determine_checkpoints_to_visit(self):
        checkpoints = {}
        for lon, lat in self._coordinates:
            match = self.data[(self.data['Longitude'] == lon) & (
                self.data['Latitude'] == lat)]
            if not match.empty:
                checkpoints[int(match.index[0])] = [lon, lat]
        return checkpoints

    def augment_distance(self, distances):
        """Augment the distance matrix with a dummy node to handle the TSP with
        a fixed starting point (0) and ending point (n-1)."""

        augmented_distance = {}
        for node_i in self.nodes:
            for node_j in self.nodes:
                if node_i == INDEX_OF_ARTIFICAL_NODE or node_j == INDEX_OF_ARTIFICAL_NODE or node_i == node_j:
                    augmented_distance[node_i, node_j] = 0
                    continue
                pointI = tuple(self.checkpoints[node_i])
                pointJ = tuple(self.checkpoints[node_j])
                if self.euclidean:
                    # Calculate Euclidean distance
                    augmented_distance[node_i, node_j] = math.sqrt(
                        (pointJ[0] - pointI[0]) ** 2 + (pointJ[1] - pointI[1]) ** 2)
                    continue
                augmented_distance[node_i, node_j] = distances[pointI][pointJ]

        # Add the cost to the nearest station for each checkpoint
        # save the cost to the nearest station in the last element of the tuple of each checkpoint (self.checkpoints)
        if not self.euclidean:
            for i in self.nodes:
                if i == INDEX_OF_ARTIFICAL_NODE or i == self.index_of_final_destination:
                    continue
                lon, lat = self.checkpoints[i]
                augmented_distance[INDEX_OF_ARTIFICAL_NODE, i] = NearestStation(
                    self.cache, near_point=(lat, lon)).get_cost()
                self.checkpoints[i].append(
                    augmented_distance[INDEX_OF_ARTIFICAL_NODE, i])
        return augmented_distance

    class _tspCallback:
        """Callback class implementing lazy constraints for the TSP.  At MIPSOL
        callbacks, solutions are checked for subtours and subtour elimination
        constraints are added if needed."""

        def __init__(self, nodes, x):
            self.nodes = nodes
            self.x = x

        def __call__(self, model, where):
            """Callback entry point: call lazy constraints routine when new
            solutions are found. Stop the optimization if there is an exception in
            user code."""
            if where == GRB.Callback.MIPSOL:
                try:
                    self.eliminate_subtours(model)
                except Exception:
                    logging.exception("Exception occurred in MIPSOL callback")
                    model.terminate()

        def shortest_subtour(self, edges):
            """Given a list of edges, return the shortest subtour (as a list of nodes)
            found by following those edges. It is assumed there is exactly one 'in'
            edge and one 'out' edge for every node represented in the edge list."""

            # Create a mapping from each node to its neighbours
            node_neighbors = defaultdict(list)
            for i, j in edges:
                node_neighbors[i].append(j)
                node_neighbors[j].append(i)
            assert all(len(neighbors) ==
                       2 for neighbors in node_neighbors.values())

            # Follow edges to find cycles. Each time a new cycle is found, keep track
            # of the shortest cycle found so far and restart from an unvisited node.
            unvisited = set(node_neighbors)
            shortest = None
            while unvisited:
                cycle = []
                neighbors = list(unvisited)
                while neighbors:
                    current = neighbors.pop()
                    cycle.append(current)
                    unvisited.remove(current)
                    neighbors = [
                        j for j in node_neighbors[current] if j in unvisited]
                if shortest is None or len(cycle) < len(shortest):
                    shortest = cycle

            assert shortest is not None
            return shortest

        def eliminate_subtours(self, model):
            """Extract the current solution, check for subtours, and formulate lazy
            constraints to cut off the current solution if subtours are found.
            Assumes we are at MIPSOL."""
            values = model.cbGetSolution(self.x)
            edges = [(i, j) for (i, j), v in values.items() if v > 0.5]
            tour = self.shortest_subtour(edges)
            if len(tour) < len(self.nodes):
                # add subtour elimination constraint for every pair of cities in tour
                model.cbLazy(
                    gp.quicksum(self.x[i, j] for i, j in permutations(tour, 2))
                    <= len(tour) - 1
                )

    def solve(self):
        """
        Solve a dense asymmetric TSP using the following base formulation:

        min  sum_ij d_ij x_ij
        s.t. sum_j x_ij == 2   forall i in V
            x_ij binary       forall (i,j) in E

        and subtours eliminated using lazy constraints.
        """

        with gp.Env() as env, gp.Model(env=env) as m:
            # Optimize model using lazy constraints to eliminate subtours
            m.Params.LogToConsole = False
            m.Params.LogFile = "gurobi.log"
            m.Params.LazyConstraints = 1
            m.Params.Threads = 1
            # Create variables
            x = m.addVars(self.distances.keys(), obj=self.distances,
                          vtype=GRB.BINARY, name="e")

            # Ensure that Bern is final destination
            m.addConstr(x[self.index_of_final_destination,
                        INDEX_OF_ARTIFICAL_NODE] == 1)

            # Create degree 2 constraints
            for i in self.nodes:
                m.addConstr(gp.quicksum(x[i, j]
                            for j in self.nodes if i != j) == 1)
                m.addConstr(gp.quicksum(x[j, i]
                            for j in self.nodes if i != j) == 1)
                if (i, i) in self.distances:
                    m.addConstr(x[i, i] == 0)
            cb = self._tspCallback(self.nodes, x)
            m.optimize(cb)

            # Extract the solution as a tour
            edges = [(i, j) for (i, j), v in x.items() if v.X > 0.5]
            tour = cb.shortest_subtour(edges)
            # Find the index of INDEX_OF_ARTIFICAL_NODE
            depot_index = tour.index(INDEX_OF_ARTIFICAL_NODE)

            # Rearrange the route to start with 0
            rearranged_tour = tour[depot_index+1:] + tour[:depot_index]

            if rearranged_tour[0] == self.index_of_final_destination:
                rearranged_tour = rearranged_tour[::-1]

            # Calculate the cost of the tour starting with duration to the first checkpoint from the nearest station
            cost = self.checkpoints[rearranged_tour[0]][2]
            tour_with_costs = {rearranged_tour[0]: cost}
            for i in range(len(rearranged_tour)-1):
                cost += self.distances[rearranged_tour[i],
                                       rearranged_tour[i+1]]
                key = rearranged_tour[i+1]
                tour_with_costs[key] = cost

            assert abs(m.ObjVal - cost) < 1e1

            self.rearranged_tour = rearranged_tour

            # In case, we only want to return the tour we should return rearranged_tour
            return tour_with_costs, m.ObjVal


if __name__ == "__main__":
    data = pd.read_csv('checkpoints.csv', sep=';', encoding='utf-8')

    lowest_cost = None
    shortest_route = None
    shortest_filename = None
    shortest_matrix = None
    copied_data = None

    cache = Cache('.such_route_cache', "valhalla")
    cache.load()

    # Load JSON data from a file
    for root, dir, files in os.walk('results'):
        for idx, filename in enumerate(files):
            # Very dump speed up, because no better solution is found after the 1491th file
            # update if distance matrices change!
            if idx > 5000:
                break

            with open(f"{root}/" + filename, 'r') as file:
                if not filename.endswith('json'):
                    continue
                # Dictionary of Euclidean distance between each pair of points
                importedDistance = json.load(file)
                copied_data = copy.copy(data)
                for i, line in data.iterrows():
                    if (line['Longitude'], line['Latitude']) not in importedDistance:
                        copied_data.drop(index=i, inplace=True)

                solver = TspSolver(cache, copied_data, importedDistance)
                tour, cost = solver.solve()

                if lowest_cost:
                    if cost < lowest_cost:
                        with open("solution.log", 'a') as file:
                            file.write(
                                f"File {idx}: New best solution with {cost} found! Name:{filename}\n")
                        lowest_cost = cost
                        shortest_route = tour
                        shortest_filename = filename
                        reduced_data = copied_data
                else:
                    with open("solution.log", 'w') as file:
                        file.write(
                            f"File {idx}: New best solution with {cost} found! Name:{filename}\n")
                    lowest_cost = cost
                    shortest_route = tour
                    shortest_filename = filename
                    reduced_data = copied_data

    # the following code needs to b refactored to be more readable
    # case 1: integrate the following code into the TspSolver class with a new method export_solution or similar
    # case 2: create a new class to handle the export of the solution because we only neeed the best solution from our scrambler

    reduced_data['Order'] = sorted(
        range(len(shortest_route)), key=lambda x: list(shortest_route.keys())[x])
    # reduced_data['Order'].map(shortest_route)
    reduced_data['Time'] = [shortest_route[i] for i in reduced_data.index]

    reduced_data.to_csv('checkpoints_ordered.csv', sep=';',
                        encoding='utf-8', index=False)

