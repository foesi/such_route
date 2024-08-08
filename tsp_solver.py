import copy
import logging
import math
import os

from collections import defaultdict

from itertools import permutations
import pandas as pd
import json

import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt


class TspSolver:
    def __init__(self, data, importedDistance, euclidean=False):
        self.euclidean = euclidean
        # Extract latitude, longitude, and Canton information
        self.latitudes = data['Latitude']
        self.longitudes = data['Longitude']
        self.cantons = data['Canton']
        self.rearranged_tour = None

        self.nodes = list(range(0, len(importedDistance)+1))
        self.distances = self.augment_distance(importedDistance)
        self.model = gp.Model()

    def augment_distance(self, distances):
        """Augment the distance matrix with a dummy node to handle the TSP with
        a fixed starting point (0) and ending point (n-1)."""

        if self.euclidean:
            return {(i, j): 0 if i == 0 or j == 0 else math.sqrt((self.longitudes[i-1] - self.longitudes[j-1]) ** 2 + (self.latitudes[i-1] - self.latitudes[j-1]) ** 2) for i, j in permutations(self.nodes, 2)}

        # Create a new distance matrix with a dummy node
        rows = list(distances.keys())
        augmented_distance = {}
        for i in range(len(self.nodes)):
            for j in range(len(self.nodes)):
                if i == 0 or j == 0 or i == j:
                    augmented_distance[i, j] = 0
                    continue
                pointI = rows[i-1]
                pointJ = rows[j-1]
                augmented_distance[i, j] = distances[pointI][pointJ]
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

    def draw_tsp_solution(self):
        # Create the plot
        plt.figure(figsize=(10, 8))
        plt.scatter(self.latitudes, self.longitudes, c='blue', marker='o')

        # Draw edges:
        for i in range(len(self.rearranged_tour)-1):
            cur = self.rearranged_tour[i]
            nex = self.rearranged_tour[i+1]
            # k- bedeutet schwarz, durchgezogene Linie mit Stärke (lw) gleich 1
            plt.plot([self.latitudes[cur], self.latitudes[nex]], [
                self.longitudes[cur], self.longitudes[nex]], 'k-', lw=1)

        # Annotate each point with its Canton name
        for i in range(len(self.cantons)):
            plt.text(self.latitudes[i] + 0.01, self.longitudes[i] +
                     0.01, self.cantons[i], fontsize=9, ha='left')

        # Set the title and labels
        plt.title('Canton Locations')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')

        # Show grid for better readability
        plt.grid(True)

        # Show the plot
        plt.savefig('checkpoints_ordered.png')

    def solve(self):
        """
        Solve a dense symmetric TSP using the following base formulation:

        min  sum_ij d_ij x_ij
        s.t. sum_j x_ij == 2   forall i in V
            x_ij binary       forall (i,j) in E

        and subtours eliminated using lazy constraints.
        """

        with gp.Env() as env, gp.Model(env=env) as m:
            # Create variables, and add symmetric keys to the resulting dictionary
            # 'x', such that (i, j) and (j, i) refer to the same variable.
            x = m.addVars(self.distances.keys(), obj=self.distances,
                          vtype=GRB.BINARY, name="e")
            # x.update({(j, i): v for (i, j), v in x.items()})

            # Assumption: Bern as final destination is always the last node
            indexOfFinalDestination = len(self.nodes)-1
            m.addConstr(x[indexOfFinalDestination, 0] == 1)

            # Create degree 2 constraints
            for i in self.nodes:
                m.addConstr(gp.quicksum(x[i, j]
                            for j in self.nodes if i != j) == 1)
                m.addConstr(gp.quicksum(x[j, i]
                            for j in self.nodes if i != j) == 1)
                if (i, i) in self.distances:
                    m.addConstr(x[i, i] == 0)

            # Optimize model using lazy constraints to eliminate subtours
            m.Params.LazyConstraints = 1
            cb = self._tspCallback(self.nodes, x)
            m.optimize(cb)

            # Extract the solution as a tour
            edges = [(i, j) for (i, j), v in x.items() if v.X > 0.5]
            tour = cb.shortest_subtour(edges)
            # Find the index of 0
            zero_index = tour.index(0)

            # Rearrange the route to start with 0
            rearranged_tour = tour[zero_index+1:] + tour[:zero_index]

            if rearranged_tour[0] == indexOfFinalDestination:
                rearranged_tour = rearranged_tour[::-1]

            # Calculate the cost of the tour
            tour_with_costs = {rearranged_tour[0]-1: 0}
            cost = 0
            for i in range(len(rearranged_tour)-1):
                cost += self.distances[rearranged_tour[i],
                                       rearranged_tour[i+1]]
                tour_with_costs[rearranged_tour[i+1] - 1] = cost

            rearranged_tour = [i - 1 for i in rearranged_tour]
            print("")
            print(f"Optimal tour: {rearranged_tour}")
            print(
                f"Optimal cost returned: {m.ObjVal:g} and calculated cost: {cost}")
            print("")
            assert abs(m.ObjVal - cost) < 1e-5

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

    # Load JSON data from a file
    for _, _, files in os.walk('results'):
        for filename in files:
            with open('results/' + filename, 'r') as file:
                if not filename.endswith('json'):
                    continue
                # Dictionary of Euclidean distance between each pair of points
                importedDistance = json.load(file)

                copied_data = copy.copy(data)
                for i, line in data.iterrows():
                    if str((line['Longitude'], line['Latitude'])) not in importedDistance:
                        copied_data.drop(index=i, inplace=True)

                solver = TspSolver(copied_data, importedDistance)
                tour, cost = solver.solve()

                if lowest_cost:
                    if cost < lowest_cost:
                        lowest_cost = cost
                        shortest_route = tour
                        shortest_filename = filename
                        reduced_data = copied_data
                else:
                    lowest_cost = cost
                    shortest_route = tour
                    shortest_filename = filename
                    reduced_data = copied_data

    # the following code needs to b refactored to be more readable
    # case 1: integrate the following code into the TspSolver class with a new method export_solution or similar
    # case 2: create a new class to handle the export of the solution because we only neeed the best solution from our scrambler

    reduced_data['Order'] = sorted(
        range(len(shortest_route)), key=lambda x: list(shortest_route.keys())[x])
    reduced_data['Time'] = reduced_data['Order'].map(shortest_route)

    reduced_data.to_csv('checkpoints_ordered.csv', sep=';',
                encoding='utf-8', index=False)

    # with open('results/' + shortest_filename, 'r') as file:
    #     importedDistance = json.load(file)
    #
    #     solver = TspSolver(data, importedDistance)
    #     solver.solve()
    #
    #     solver.draw_tsp_solution()
