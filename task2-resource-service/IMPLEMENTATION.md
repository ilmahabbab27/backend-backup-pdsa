# Task 2: emergency resource allocation

This implementation produces **proposed plans**, not live dispatches. Comparing
strategies does not modify incident or vehicle statuses. Administrative status
changes remain explicit actions. Atomic dispatch/reservation across concurrent
operators would require a separate transactional database operation.

## Code map

| Feature | Implementation |
| --- | --- |
| Incident/resource input and JSON metadata compatibility | `app/main.py`: `RequestCreate`, `VehicleCreate`, `record_body`, `load_live_data` |
| API selection, validation, preview, optional history | `app/main.py`: `OptimizationRequest`, `optimize_resources` |
| Incident priority queue and demand nodes | `app/allocation.py`: `Problem.__init__` |
| ID hash maps, capability sets, station counters | `Problem.incidents`, `Problem.vehicles`, `Vehicle.capabilities`, `Problem.budget` |
| Greedy allocation and cost min-heaps | `greedy` |
| Residual adjacency-list graph and Min-Cost Max-Flow | `Edge`, `min_cost_flow` |
| Genetic population, tournament selection, crossover, mutation, repair, elitism | `genetic`, `Problem.repair`, `Problem.score` |
| Availability AVL tree with rotations | `AVLNode`, `avl_insert`, `rotate`, `avl_order` |
| Bounded thread-safe LRU response-estimate cache | `ResponseCache` (64 entries by default) |
| Priority-ordered waiting list, explanations, partial demand | `allocate` |
| Measured experiments on seeded synthetic datasets | `main.py`: `benchmark_dataset`, `benchmark_resources` |
| Correctness/API regression tests | `tests/test_allocation.py`, `tests/test_api.py` |

## Allocation model

Each incident specifies one or more requirements, each with vehicle type,
quantity, and required capabilities. Each individual required unit becomes a
demand node. Vehicles must be available and satisfy type and capability checks.
Each vehicle can be used once per plan. A station can dispatch at most its selected
available count minus its configured reserve. Reserves are enforced across the
**selected fleet**, conservatively retaining selected vehicles even when other
unselected vehicles may exist at that station.

Vehicle type matching ignores case and separators and recognizes legacy
fire-truck/fire-engine and police-car/police-unit aliases. Specialist types such
as Advanced Ambulance remain distinct from a basic Ambulance.

The flow graph is:

`Source -> Demand unit -> Compatible vehicle -> Station -> Sink`

Demand and vehicle capacities are one; station-to-sink capacities implement
reserves. Each demand also has a direct unfulfilled-demand edge to the sink with
a priority penalty. Reverse residual edges permit earlier choices to be changed.
The solver uses successive shortest paths with heap Dijkstra and vertex
potentials. Forward initial costs are nonnegative. Costs are rounded to 0.001.

All strategies use the same objective: lexicographically maximize the number of
fulfilled **resource units** at Critical, High, Medium, then Low severity, followed
by minimizing weighted assignment cost. The flow solver finds an optimum for
this encoded objective. This is not an all-or-nothing optimization of the number
of fully covered incidents: an incident can be partially served. Greedy and
genetic are heuristics and do not guarantee the flow optimum. Genetic uses a
fixed seed by default and preserves the best chromosome each generation.

Weighted cost is:

`response_weight * response_minutes + workload_weight * workload`

`+ deadline_weight * max(0, response_minutes - deadline_minutes)`

`+ reserve_weight / station_dispatch_capacity`

Capabilities are a hard constraint, not a mismatch penalty. Setting
`strict_deadlines` rejects late edges; otherwise lateness is penalized and shown.
Priority penalties dominate all possible lower-priority gains and cost savings
within the request. Thus a lower-cost low-priority assignment cannot displace a
feasible higher-priority unit in the exact solver.

## Stored data and defaults

No schema migration is needed: new attributes are in existing JSON `metadata`.
Legacy incidents default to one unit of `required_vehicle_type`. Legacy vehicles
use `response_minutes` (10 minutes when absent), their location as their station,
no specialist capabilities, and zero workload. Only `open` and `unassigned`
incidents enter planning. Only `available` vehicles enter allocation; busy
vehicles with a known positive `available_in_minutes` can appear in the AVL
availability schedule but are never assigned early.

Incident metadata example:

```json
{
  "deadline_minutes": 15,
  "requirements": [
    {"vehicle_type": "Ambulance", "quantity": 2, "capabilities": ["oxygen"]},
    {"vehicle_type": "Fire Engine", "quantity": 1, "capabilities": []}
  ]
}
```

Vehicle metadata example:

```json
{
  "station": "central-hospital",
  "capabilities": ["oxygen"],
  "response_minutes": 12,
  "response_times": {"city-hall": 6, "shopping-center": 14},
  "workload": 2,
  "available_in_minutes": 0
}
```

Response times use a location-specific stored estimate when present, otherwise
the vehicle's typical estimate. These are **not live GPS/routing times**. Old
synthetic `resource_cost_cache` records are not reused. In-memory cache keys
include the estimate and source location so edited profiles cannot return stale
durations. Caching a simple stored estimate may not improve runtime; the cache
provides bounded reusable cost lookup and should be evaluated, not assumed faster.

`POST /api/resource/optimize` accepts `greedy`, `min_cost_flow`, or `genetic`.
The old `backtracking` label is deliberately rejected rather than silently
executing a different algorithm. `persist_history` defaults to false. If true,
only a summary is written and any history-write failure is returned as a warning.
The existing history table must allow the new strategy string `min_cost_flow`.

`served`/`coverage` count fully satisfied incidents. `partial` counts incidents
with some but not all resources; `unassigned` includes every incident with unmet
demand. `requirements_coverage` separately reports the fraction of units assigned.
The legacy `vehicle` field contains the first assigned vehicle; new clients use
the complete `vehicles` array. `matching_edges` counts feasible unit-to-vehicle
edges, not all theoretical combinations. The availability schedule orders readiness,
not fastest travel to a particular incident.

## Complexity of the implemented algorithms

Let I be incidents, D required units, V selected vehicles, S stations, C the
largest candidate list, P population, and G generations. The graph has
N = O(D + V + S) vertices and E = O(DV + D + V + S) residual edges.

- Shared candidate construction: O(DV log V) worst case due to sorting candidate
  lists; memory O(DV + I + V). Capability checks also depend on capability count.
- Incident priority heap: O(I) heap construction and O(I log I) total pops.
- Greedy phase: O(DV log V) upper bound; each candidate is popped at most once per demand.
- Flow phase: O(D E log N), plus shared preprocessing; at most D augmentations.
- Genetic phase: O(G [P D C + P log(P) D]) upper bound with the current repair
  and score functions; O(PD + DV) memory.
- AVL availability index: O(V log V) construction, O(V) ordered traversal.
- LRU operations: expected O(1), with a fixed 64-entry capacity.
- Result formatting currently scans D units for each incident: O(ID).

Plans are bounded to 200 demand units and 200 vehicles. Genetic search additionally
limits D * P * G to 1,000,000. This is a coursework prototype, not a production
dispatch engine, and large dataset claims should respect those bounds.

## Experiments and verification

`POST /api/resource/benchmark` runs all three algorithms on the same reproducible
synthetic datasets with 10, 25, 50 and 100 incidents and roughly 75% as many
heterogeneous vehicles. Each runtime is the median of three actual executions.
Genetic runs use population 16, generations 20 and seeds 41/42/43. Solution-quality
columns refer to seed 43. Memory is peak Python allocation measured by
`tracemalloc` in a separate execution, not process RSS and not native-library memory.
No benchmark writes incident, vehicle or history records.

Tests include an exhaustive small-instance oracle for the flow objective, greedy
counterexamples, type/capability constraints, quantities, priorities, station
reserves, deadline rejection, empty inputs, LRU invalidation/eviction, AVL balance,
genetic reproducibility/elitism, legacy metadata preservation, API validation,
history failure reporting and preview isolation.

Run from this service directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

The report should describe these actual implementations and measurements.
Automatic dispatch status changes, transactional reservation, live travel routing,
direct distance penalties, and larger-scale datasets remain outside this change.
