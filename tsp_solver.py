import copy
import logging
import math
import multiprocessing
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
    def __init__(self, cache, stations, data, importedDistance, euclidean=False):
        self.euclidean = euclidean
        # Extract latitude, longitude, and Canton information
        self.data = data
        self.cache = cache
        self.stations = stations
        self.latitudes = data['Latitude']
        self.longitudes = data['Longitude']
        self.cantons = data['Canton']
        self.rearranged_tour = None
        self.cost = {}

        self._coordinates = list(importedDistance.keys())
        self.checkpoints = self.determine_checkpoints_to_visit()
        self.nodes = [INDEX_OF_ARTIFICAL_NODE] + list(self.checkpoints.keys())
        # Retrieve the first key matching the value, or None if not found
        self.index_of_final_destination = next(
            (key for key, value in self.checkpoints.items() if value == FINAL_DESTINATION), None)
        self.distances = self.augment_distance(importedDistance)
        self.model = gp.Model()

    def determine_checkpoints_to_visit(self):
        checkpoints = {}
        try:
            for lon, lat in self._coordinates:
                match = self.data[(self.data['Longitude'] == lon) & (
                    self.data['Latitude'] == lat)]
                if not match.empty:
                    checkpoints[int(match.index[0])] = (lon, lat)
        except ValueError as e:
            print(self._coordinates)
            raise e
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
                pointI = self.checkpoints[node_i]
                pointJ = self.checkpoints[node_j]
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
                augmented_distance[INDEX_OF_ARTIFICAL_NODE, i] = self.stations[(lat, lon)].get_cost()
                self.cost[i] = augmented_distance[INDEX_OF_ARTIFICAL_NODE, i]
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
            cost = self.cost[rearranged_tour[0]]
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

    cache = Cache('.such_route_cache', "valhalla")
    cache.load()

    stations = {}

    for index, row in data.iterrows():
        station_position = None
        checkpoint_position = (row['Latitude'], row['Longitude'])
        if row['Station_Lat'] and row['Station_Lon'] and not math.isnan(row['Station_Lat']) and not math.isnan(
                row['Station_Lon']):
            station_position = (row['Station_Lat'], row['Station_Lon'])
        stations[checkpoint_position] = NearestStation(cache, checkpoint_position, station_position)

    def solve_tsp(arguments):
        directory, filename = arguments
        with open(f"{directory}/" + filename, 'r') as f:
            if not filename.endswith('json'):
                return None, None
            # Dictionary of Euclidean distance between each pair of points
            imported_distance = json.load(f)
            reduced_data = copy.copy(data)
            for i, line in data.iterrows():
                if (line['Longitude'], line['Latitude']) not in imported_distance:
                    reduced_data.drop(index=i, inplace=True)

            solver = TspSolver(cache, stations, reduced_data, imported_distance)
            tour, cost = solver.solve()

            reduced_data['Order'] = sorted(
                range(len(tour)), key=lambda x: list(tour.keys())[x])
            reduced_data['Time'] = [tour[i] for i in reduced_data.index]
            return cost, reduced_data

    results = []
    for root, _, files in os.walk('results'):
        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as p:
            for (cost, result_data) in p.imap_unordered(solve_tsp, zip([root for _ in files], files)):
                if cost and result_data is not None:
                    results.append((cost, result_data))

    results = sorted(results, key=lambda x: x[0])

    results[0][1].to_csv('checkpoints_ordered.csv', sep=';', encoding='utf-8', index=False)

