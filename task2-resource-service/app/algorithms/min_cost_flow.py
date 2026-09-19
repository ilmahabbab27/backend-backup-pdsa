"""Min-cost flow formulation for Task 2 allocations.

This strategy models each required resource unit as demand and each vehicle as a
capacity-constrained flow source. A shortest-path based residual network then
chooses assignments that minimize cost while respecting station dispatch caps.
"""

from __future__ import annotations

from heapq import heappop, heappush

from app.algorithms.common import Problem


class Edge:
    """Residual-network edge used by the min-cost flow solver."""

    def __init__(self, to: int, reverse: int, capacity: int, cost: int):
        self.to = to
        self.reverse = reverse
        self.capacity = capacity
        self.cost = cost


def min_cost_flow(problem: Problem):
    """Successive shortest paths with potentials, heap Dijkstra and residual edges."""
    # Build a flow graph where source -> demand -> vehicle -> station -> sink
    # captures the assignment constraints and station capacities.
    graph = []

    def node():
        graph.append([])
        return len(graph) - 1

    def add(start, end, capacity, cost):
        forward = Edge(end, len(graph[end]), capacity, cost)
        reverse = Edge(start, len(graph[start]), 0, -cost)
        graph[start].append(forward)
        graph[end].append(reverse)
        return forward

    source, sink = node(), node()
    stations = {station: node() for station in problem.budget}
    vehicles = {vehicle: node() for vehicle in problem.vehicles}
    for station, vertex in stations.items():
        add(vertex, sink, problem.budget[station], 0)
    for vehicle, vertex in vehicles.items():
        add(vertex, stations[problem.vehicles[vehicle].station], 1, 0)
    assignment_edges = {}
    for slot, candidates in enumerate(problem.candidates):
        demand = node()
        add(source, demand, 1, 0)
        add(demand, sink, 1, problem.penalties[slot])
        for vehicle in candidates:
            assignment_edges[slot, vehicle] = add(demand, vehicles[vehicle], 1, problem.costs[slot, vehicle])

    # Potentials keep reduced costs non-negative so the shortest-path search stays
    # efficient and stable across repeated augmenting paths.
    potentials = [0] * len(graph)
    for _ in problem.slots:
        distances = [float("inf")] * len(graph)
        distances[source] = 0
        previous = [None] * len(graph)
        queue = [(0, source)]
        while queue:
            distance, vertex = heappop(queue)
            if distance != distances[vertex]:
                continue
            for index, edge in enumerate(graph[vertex]):
                candidate = distance + edge.cost + potentials[vertex] - potentials[edge.to]
                if edge.capacity and candidate < distances[edge.to]:
                    distances[edge.to] = candidate
                    previous[edge.to] = (vertex, index)
                    heappush(queue, (candidate, edge.to))
        if previous[sink] is None:
            raise RuntimeError("Demand graph has no unfulfilled-demand path.")
        for vertex, distance in enumerate(distances):
            if distance != float("inf"):
                potentials[vertex] += distance
        vertex = sink
        while vertex != source:
            parent, index = previous[vertex]
            edge = graph[parent][index]
            edge.capacity -= 1
            graph[vertex][edge.reverse].capacity += 1
            vertex = parent
    result = [None] * len(problem.slots)
    for (slot, vehicle), edge in assignment_edges.items():
        if edge.capacity == 0:
            result[slot] = vehicle
    return result


__all__ = ["min_cost_flow"]
