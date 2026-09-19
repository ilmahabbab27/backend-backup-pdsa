from itertools import product
from random import Random

import pytest

from app.allocation import (AVLNode, Incident, Options, Problem, Requirement,
                            ResponseCache, STRATEGIES, Vehicle, allocate,
                            avl_insert, avl_order, height)


def incident(code="E1", kind="Ambulance", priority="Critical", quantity=1, capabilities=()):
    return Incident(code, code, priority, 10,
                    (Requirement(vehicle_type=kind, quantity=quantity, capabilities=list(capabilities)),))


def vehicle(code="A1", kind="Ambulance", times=None, capabilities=(), station="S1", status="available"):
    return Vehicle(code, kind, "base", station, frozenset(capabilities), 8, times or {}, status=status)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_types_capabilities_multi_resource_and_uniqueness(strategy):
    incidents = [incident(quantity=2, capabilities=("oxygen",)), incident("E2", "Fire Engine")]
    vehicles = [vehicle("A1", capabilities=("oxygen",)), vehicle("A2"),
                vehicle("A3", capabilities=("oxygen",)), vehicle("F1", "Fire Engine"),
                vehicle("F2", "Fire Engine", status="busy")]
    result = allocate(incidents, vehicles, strategy)
    codes = [u["vehicle"] for a in result["assignments"] for u in a["vehicles"]]
    assert set(codes) == {"A1", "A3", "F1"}
    assert len(codes) == len(set(codes))
    assert result["served"] == 2
    assert result["allocated_units"] == 3


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_priority_reserve_and_waiting_queue(strategy):
    incidents = [incident("low", priority="Low"), incident("high", priority="High"),
                 incident("critical", priority="Critical")]
    result = allocate(incidents, [vehicle("A1"), vehicle("A2")], strategy,
                      Options(station_reserves={"S1": 1}))
    assert result["assignments"][0]["request_id"] == "critical"
    assert result["assignments"][0]["status"] == "Assigned"
    assert result["allocated_units"] == 1
    assert result["waiting_incidents"] == ["high", "low"]


def test_flow_reroutes_greedy_choice_for_global_cost():
    incidents = [incident("E1"), incident("E2")]
    vehicles = [vehicle("A1", times={"E1": 1, "E2": 2}), vehicle("A2", times={"E1": 2, "E2": 100})]
    simple = allocate(incidents, vehicles, "greedy")
    flow = allocate(incidents, vehicles, "min_cost_flow")
    assert flow["total_allocation_cost"] < simple["total_allocation_cost"]
    assert [a["vehicle"] for a in flow["assignments"]] == ["A2", "A1"]


def test_flow_matches_exhaustive_optimum_with_shortages_and_station_capacities():
    rng = Random(45)
    for _ in range(20):
        incidents = [incident(f"E{i}", priority=rng.choice(["Critical", "High", "Low"])) for i in range(4)]
        vehicles = [vehicle(f"A{i}", times={f"E{j}": rng.randint(1, 20) for j in range(4)},
                            station=f"S{i % 2}") for i in range(3)]
        options = Options(station_reserves={"S0": 1})
        problem = Problem(incidents, vehicles, options, ResponseCache())
        scores = []
        for chromosome in product(*[[None, *c] for c in problem.candidates]):
            used = [v for v in chromosome if v]
            if len(used) != len(set(used)):
                continue
            if any(sum(problem.vehicles[v].station == station for v in used) > limit
                   for station, limit in problem.budget.items()):
                continue
            scores.append(problem.score(chromosome))
        from app.allocation import min_cost_flow
        assert problem.score(min_cost_flow(problem)) == min(scores)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_deadlines_and_partial_coverage(strategy):
    result = allocate([incident(quantity=2)], [vehicle(times={"E1": 15}), vehicle("A2")], strategy,
                      Options(strict_deadlines=True))
    assert result["served"] == 0
    assert result["partial"] == 1
    assert result["requirements_coverage"] == 50
    assert result["assignments"][0]["status"] == "Partial"
    assert result["assignments"][0]["deadline_met"] is False


def test_genetic_is_reproducible_and_elitism_preserves_fitness():
    incidents = [incident(f"E{i}") for i in range(5)]
    vehicles = [vehicle(f"A{i}", times={f"E{j}": abs(i - j) + 3 for j in range(5)}) for i in range(5)]
    first = allocate(incidents, vehicles, "genetic", Options(seed=17))
    second = allocate(incidents, vehicles, "genetic", Options(seed=17))
    assert first["assignments"] == second["assignments"]
    history = first["algorithm_details"]["fitness_history"]
    assert all(later <= earlier for earlier, later in zip(history, history[1:]))
    assert len(history) == 41


def test_lru_evicts_oldest_and_does_not_reuse_changed_estimates():
    cache = ResponseCache(2)
    assert cache.get(vehicle("A1"), "E1") == (8, False)
    cache.get(vehicle("A2"), "E1")
    assert cache.get(vehicle("A1"), "E1")[1]
    cache.get(vehicle("A3"), "E1")
    assert not cache.get(vehicle("A2"), "E1")[1]
    assert cache.get(vehicle("A1", times={"E1": 4}), "E1") == (4, False)
    assert len(cache.values) == 2


def test_avl_balances_sorted_inserts_and_orders_availability():
    root = None
    for i in range(100):
        root = avl_insert(root, (i, str(i)))
    assert list(avl_order(root)) == [(i, str(i)) for i in range(100)]
    def check(node):
        if node:
            assert abs(height(node.left) - height(node.right)) <= 1
            assert node.height == 1 + max(height(node.left), height(node.right))
            check(node.left)
            check(node.right)
    check(root)
    assert root.height < 10


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_empty_inputs_and_no_compatible_vehicles(strategy):
    assert allocate([], [], strategy)["coverage"] == 100
    result = allocate([incident()], [vehicle(kind="Police")], strategy)
    assert result["served"] == 0
    assert result["matching_edges"] == 0
    assert result["waiting_incidents"] == ["E1"]


def test_planning_does_not_mutate_inputs():
    incidents, vehicles = [incident()], [vehicle()]
    for strategy in STRATEGIES:
        allocate(incidents, vehicles, strategy)
    assert vehicles[0].status == "available"
    assert incidents[0].requirements[0].quantity == 1


def test_size_bound_and_validation():
    with pytest.raises(ValueError, match="200"):
        allocate([incident(f"E{i}", quantity=20) for i in range(11)], [], "greedy")
    with pytest.raises(ValueError, match="unique"):
        allocate([incident(), incident()], [], "greedy")


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_legacy_type_aliases_and_specialist_types(strategy):
    incidents = [incident("E1", "Fire Engine"), incident("E2", "Police Unit"), incident("E3", "Advanced Ambulance")]
    vehicles = [vehicle("F1", "fire-truck"), vehicle("P1", "police-car"), vehicle("A1", "ambulance")]
    result = allocate(incidents, vehicles, strategy)
    assert result["served"] == 2
    assert result["assignments"][-1]["status"] == "Unassigned"
