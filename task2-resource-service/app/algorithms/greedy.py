"""Greedy allocation strategy for Task 2.

This strategy walks each required resource slot in order and picks the cheapest
available vehicle that also respects the dispatch budget of that station.
"""

from __future__ import annotations

from collections import Counter
from heapq import heapify, heappop

from app.algorithms.common import Problem


def greedy(problem: Problem):
    """Choose the lowest-cost feasible eligible vehicle for each demand slot."""
    used = set()  # tracks vehicles already assigned to avoid reusing them
    station_use = Counter()  # counts how many units each station has already dispatched
    result = []
    for slot, candidates in enumerate(problem.candidates):
        # Keep the cheapest candidates near the front of the heap to prefer
        # lower response and lower total cost assignment choices.
        heap = [(problem.costs[slot, v], v) for v in candidates if v not in used]
        heapify(heap)
        selected = None
        while heap:
            _, candidate = heappop(heap)
            station = problem.vehicles[candidate].station
            # Respect the station budget before finalising a match.
            if station_use[station] < problem.budget[station]:
                selected = candidate
                used.add(candidate)
                station_use[station] += 1
                break
        result.append(selected)
    return result


__all__ = ["greedy"]
