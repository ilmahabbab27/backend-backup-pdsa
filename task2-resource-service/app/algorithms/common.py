"""Shared allocation primitives and orchestration for Task 2.

This module is the core model used by the three allocation strategies. It turns
incoming emergency incidents and available vehicles into a single optimization
problem, normalizes the decision criteria, and then produces the final preview
result used by the frontend and API layer.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass
from heapq import heapify, heappop, heappush
from math import isfinite
from random import Random
from threading import RLock
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

# T2DS: Priority ranking for emergency incidents. Lower values mean higher urgency.
PRIORITY = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
# T2DS: Algorithm alternatives available for Task 2 planning.
STRATEGIES = ("greedy", "min_cost_flow", "genetic")

# T2DS: Resource requirement for an incident. Each request can require one or more vehicle types and optional capabilities.
class Requirement(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    vehicle_type: str = Field(min_length=1, max_length=80)
    quantity: int = Field(default=1, ge=1, le=20)
    capabilities: list[str] = Field(default_factory=list, max_length=20)


# T2DS: Weighting factors used by the optimizer to trade off response speed, workload, deadline risk, and station reserve penalties.
class Weights(BaseModel):
    response: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    workload: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    deadline: float = Field(default=5, ge=0, le=1000, allow_inf_nan=False)
    reserve: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)

# T2DS: Runtime settings for a single allocation run. Controls strictness, station reserves, genetic parameters, and cache behavior.
class Options(BaseModel):
    weights: Weights = Field(default_factory=Weights)
    station_reserves: dict[str, int] = Field(default_factory=dict)
    strict_deadlines: bool = False
    population_size: int = Field(default=32, ge=8, le=100)
    generations: int = Field(default=40, ge=1, le=200)
    mutation_rate: float = Field(default=0.15, ge=0, le=1, allow_inf_nan=False)
    seed: int = 42
    use_cache: bool = True

    @model_validator(mode="after")
    def validate_reserves(self):
        if any(not key.strip() or value < 0 for key, value in self.station_reserves.items()):
            raise ValueError("Station reserves must use a station name and non-negative counts.")
        return self


# T2DS: Incident record representing one emergency request needing one or more resources.
@dataclass(frozen=True)
class Incident:
    id: str
    location: str
    priority: str
    deadline: float
    requirements: tuple[Requirement, ...]

# T2DS: Vehicle record representing an available emergency unit that can be assigned to an incident.
@dataclass(frozen=True)
class Vehicle:
    id: str
    kind: str
    location: str
    station: str
    capabilities: frozenset[str]
    response: float
    response_by_location: dict[str, float]
    workload: float = 0
    status: str = "available"
    available_in: float = 0


# T2DS: Response cache used to store travel-time lookups for vehicle-to-location pairs and reuse them across planning runs.
class ResponseCache:
    """Bounded, thread-safe LRU. Profile values are part of each cache key."""

    def __init__(self, limit=64):
        self.limit = limit
        self.values = OrderedDict()
        self.lock = RLock()

    def get(self, vehicle: Vehicle, location: str, enabled=True):
        duration = vehicle.response_by_location.get(location, vehicle.response)
        key = (vehicle.id, vehicle.location, location, duration)
        if not enabled:
            return duration, False
        with self.lock:
            hit = key in self.values
            self.values[key] = duration
            self.values.move_to_end(key)
            if len(self.values) > self.limit:
                self.values.popitem(last=False)
            return duration, hit


COST_CACHE = ResponseCache()


# T2DS: AVL tree node used to keep a sorted, balanced availability index for quick lookup and ordering.
@dataclass
class AVLNode:
    key: tuple[float, str]
    height: int = 1
    left: "AVLNode | None" = None
    right: "AVLNode | None" = None


def height(node):
    return node.height if node else 0


def rotate(node, left):
    top = node.right if left else node.left
    if left:
        node.right, top.left = top.left, node
    else:
        node.left, top.right = top.right, node
    node.height = 1 + max(height(node.left), height(node.right))
    top.height = 1 + max(height(top.left), height(top.right))
    return top


def avl_insert(node, key):
    """Availability index: O(log V) insertion with AVL rotations."""
    if node is None:
        return AVLNode(key)
    if key < node.key:
        node.left = avl_insert(node.left, key)
    elif key > node.key:
        node.right = avl_insert(node.right, key)
    else:
        return node
    node.height = 1 + max(height(node.left), height(node.right))
    balance = height(node.left) - height(node.right)
    if balance > 1:
        if key > node.left.key:
            node.left = rotate(node.left, True)
        return rotate(node, False)
    if balance < -1:
        if key < node.right.key:
            node.right = rotate(node.right, False)
        return rotate(node, True)
    return node


def avl_order(node):
    if node:
        yield from avl_order(node.left)
        yield node.key
        yield from avl_order(node.right)


def canonical(value):
    return " ".join(value.casefold().split())


def vehicle_kind(value):
    name = canonical(value.replace("-", " ").replace("_", " "))
    return {"fire truck": "fire engine", "police car": "police", "police unit": "police"}.get(name, name)


# T2DS: Problem object that converts incidents and vehicles into a normalized assignment matrix with costs, slots, budgets, and penalties.
class Problem:
    """Concrete optimization model derived from incidents, vehicles, and scoring rules."""

    def __init__(self, incidents, vehicles, options, cache):
        # Keep the user-facing configuration and derive the assignment structure
        # once so every algorithm reuses the same normalized search space.
        self.options = options
        self.incidents = {item.id: item for item in incidents}
        self.vehicles = {item.id: item for item in vehicles if item.status == "available"}
        if len(self.incidents) != len(incidents) or len({v.id for v in vehicles}) != len(vehicles):
            raise ValueError("Incident and vehicle IDs must be unique.")
        if any(i.priority not in PRIORITY or i.deadline <= 0 or not isfinite(i.deadline) for i in incidents):
            raise ValueError("Incidents need a supported priority and positive finite deadline.")
        for vehicle in vehicles:
            values = [vehicle.response, vehicle.workload, vehicle.available_in, *vehicle.response_by_location.values()]
            if any(value < 0 or not isfinite(value) for value in values):
                raise ValueError("Vehicle response times, availability and workload must be finite and non-negative.")

        # Station budgets become the hard capacity constraint. Reserves reduce the
        # number of vehicles that may be dispatched from a station in a preview.
        self.budget = Counter(v.station for v in self.vehicles.values())
        for station in self.budget:
            self.budget[station] = max(0, self.budget[station] - options.station_reserves.get(station, 0))

        # Incidents are ordered by urgency: critical first, then high, medium, low.
        queue = [(PRIORITY[i.priority], i.deadline, i.id) for i in incidents]
        heapify(queue)
        self.ordered = [self.incidents[heappop(queue)[2]] for _ in range(len(queue))]

        # Each required vehicle unit becomes a slot; the candidate list for a slot
        # describes all vehicles that can satisfy the requirement.
        self.slots = [(i.id, requirement) for i in self.ordered for requirement in i.requirements for _ in range(requirement.quantity)]
        if len(self.slots) > 200 or len(vehicles) > 200:
            raise ValueError("A plan supports at most 200 required resource units and 200 vehicles.")
        self.candidates = []
        self.costs = {}
        self.times = {}
        self.hits = self.misses = 0
        for slot, (incident_id, requirement) in enumerate(self.slots):
            incident = self.incidents[incident_id]
            candidates = []
            for vehicle in self.vehicles.values():
                required_kind = vehicle_kind(requirement.vehicle_type)
                if required_kind not in ("any", "any suitable vehicle") and required_kind != vehicle_kind(vehicle.kind):
                    continue
                if not {canonical(c) for c in requirement.capabilities}.issubset(vehicle.capabilities):
                    continue
                if not self.budget[vehicle.station]:
                    continue
                response, hit = cache.get(vehicle, incident.location, options.use_cache)
                self.hits += int(hit)
                self.misses += int(not hit)
                if options.strict_deadlines and response > incident.deadline:
                    continue
                w = options.weights
                cost = (w.response * response + w.workload * vehicle.workload
                        + w.deadline * max(0, response - incident.deadline)
                        + w.reserve / self.budget[vehicle.station])
                self.costs[slot, vehicle.id] = round(cost * 1000)
                self.times[slot, vehicle.id] = response
                candidates.append(vehicle.id)
            self.candidates.append(sorted(candidates, key=lambda v: (self.costs[slot, v], v)))

        # Penalties are intentionally higher for urgent incidents so the solver
        # prefers satisfying critical and high-priority requests even if the cost
        # is greater than for lower-priority demand.
        base = 1 + len(self.slots)
        scale = 1 + max(self.costs.values(), default=0) * len(self.slots)
        self.penalties = [scale * base ** (3 - PRIORITY[self.incidents[i].priority]) for i, _ in self.slots]

    def score(self, chromosome):
        # A missing assignment is punished heavily; otherwise, the objective is
        # the cumulative cost of the chosen vehicle matches.
        return sum(self.penalties[s] if v is None else self.costs[s, v] for s, v in enumerate(chromosome))

    def repair(self, chromosome, rng=None):
        """Repair an infeasible chromosome by picking valid vehicles within station limits."""
        used = set()
        station_use = Counter()
        repaired = []
        for slot, preferred in enumerate(chromosome):
            candidates = list(self.candidates[slot])
            if rng:
                rng.shuffle(candidates)
            if preferred in candidates:
                candidates.remove(preferred)
                candidates.insert(0, preferred)
            selected = next((v for v in candidates if v not in used
                             and station_use[self.vehicles[v].station] < self.budget[self.vehicles[v].station]), None)
            repaired.append(selected)
            if selected is not None:
                used.add(selected)
                station_use[self.vehicles[selected].station] += 1
        return repaired


def allocate(incidents, vehicles, strategy, options=None, cache=None):
    """Run the selected algorithm and return a structured preview result."""
    if strategy not in STRATEGIES:
        raise ValueError("Choose greedy, min_cost_flow, or genetic.")
    started = perf_counter()
    options = options or Options()
    from app.algorithms.genetic import genetic
    from app.algorithms.greedy import greedy
    from app.algorithms.min_cost_flow import min_cost_flow

    # Build a common optimization model once so the chosen strategy uses the same
    # candidate list, costs, and station budgets.
    problem = Problem(incidents, vehicles, options, cache or COST_CACHE)
    if strategy == "genetic" and len(problem.slots) * options.population_size * options.generations > 1_000_000:
        raise ValueError("Reduce genetic population or generations: required units x population x generations must not exceed 1,000,000.")
    diagnostics = {}
    if strategy == "genetic":
        chromosome, diagnostics = genetic(problem)
    else:
        chromosome = greedy(problem) if strategy == "greedy" else min_cost_flow(problem)
    assignments = []
    used = [v for v in chromosome if v is not None]
    if len(used) != len(set(used)):
        raise RuntimeError("An allocation attempted to use a vehicle twice.")
    station_use = Counter(problem.vehicles[v].station for v in used)
    if any(count > problem.budget[station] for station, count in station_use.items()):
        raise RuntimeError("An allocation exceeded a station's dispatch capacity.")
    for incident in problem.ordered:
        units = []
        missing = []
        for slot, (incident_id, requirement) in enumerate(problem.slots):
            if incident_id != incident.id:
                continue
            vehicle = chromosome[slot]
            if vehicle is None:
                missing.append(requirement.vehicle_type)
            else:
                units.append({"vehicle": vehicle, "vehicle_type": problem.vehicles[vehicle].kind,
                              "station": problem.vehicles[vehicle].station,
                              "response_minutes": problem.times[slot, vehicle],
                              "cost": problem.costs[slot, vehicle] / 1000,
                              "deadline_met": problem.times[slot, vehicle] <= incident.deadline})
        assignments.append({"request_id": incident.id, "vehicle": units[0]["vehicle"] if units else None,
                            "vehicles": units, "response_minutes": max((u["response_minutes"] for u in units), default=None),
                            "deadline_met": bool(units) and not missing and all(u["deadline_met"] for u in units),
                            "status": "Partial" if units and missing else "Assigned" if units else "Unassigned",
                            "unfulfilled_requirements": missing,
                            "explanation": (f"{len(units)} of {len(units) + len(missing)} required units allocated; "
                                            "vehicle type, capabilities, availability and station reserves checked."
                                            + (" Remaining demand is waiting under the selected constraints." if missing else ""))})
    waiting = [(PRIORITY[problem.incidents[a["request_id"]].priority],
                problem.incidents[a["request_id"]].deadline, a["request_id"])
               for a in assignments if a["unfulfilled_requirements"]]
    heapify(waiting)
    availability = None
    for vehicle in vehicles:
        if vehicle.status == "available" or (vehicle.status == "busy" and vehicle.available_in > 0):
            availability = avl_insert(availability, (0 if vehicle.status == "available" else vehicle.available_in, vehicle.id))
    schedule = list(avl_order(availability))
    served = sum(a["status"] == "Assigned" for a in assignments)
    total = len(incidents)
    units = [unit for a in assignments for unit in a["vehicles"]]
    return {"strategy": strategy, "assignments": assignments, "served": served, "total_requests": total,
            "coverage": round(100 * served / total, 1) if total else 100,
            "unassigned": total - served, "partial": sum(a["status"] == "Partial" for a in assignments),
            "required_units": len(problem.slots), "allocated_units": len(used),
            "requirements_coverage": round(100 * len(used) / len(problem.slots), 1) if problem.slots else 100,
            "total_allocation_cost": round(sum(u["cost"] for u in units), 3),
            "average_response_minutes": round(sum(u["response_minutes"] for u in units) / len(units), 3) if units else None,
            "deadline_violations": sum(not u["deadline_met"] for u in units),
            "critical_served": sum(a["status"] == "Assigned" and problem.incidents[a["request_id"]].priority == "Critical" for a in assignments),
            "processing_time_ms": round((perf_counter() - started) * 1000, 3),
            "incidents": [{"id": i.id, "location": i.location, "priority": i.priority,
                           "deadline_minutes": i.deadline, "requirements": [r.model_dump() for r in i.requirements],
                           "vehicle": ", ".join(f"{r.quantity} x {r.vehicle_type}" for r in i.requirements)} for i in problem.ordered],
            "matching_edges": len(problem.costs), "scheduling_order": [code for _, code in schedule],
            "availability_schedule": [{"vehicle": code, "available_in_minutes": minutes} for minutes, code in schedule],
            "waiting_incidents": [heappop(waiting)[2] for _ in range(len(waiting))],
            "cache_hits": problem.hits, "cache_misses": problem.misses,
            "station_dispatch_limits": dict(problem.budget), "algorithm_details": diagnostics,
            "objective": "Fulfilled resource units by Critical, High, Medium, Low priority; then minimum weighted cost.",
            "preview": True, "warnings": []}


__all__ = [
    "PRIORITY",
    "STRATEGIES",
    "Requirement",
    "Weights",
    "Options",
    "Incident",
    "Vehicle",
    "ResponseCache",
    "COST_CACHE",
    "AVLNode",
    "height",
    "rotate",
    "avl_insert",
    "avl_order",
    "canonical",
    "vehicle_kind",
    "Problem",
    "allocate",
]
