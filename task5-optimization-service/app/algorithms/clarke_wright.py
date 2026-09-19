"""Clarke-Wright Savings Algorithm solver for homogeneous fleet allocation, capacity enforcement, and optimal route sequencing."""

from typing import Any, Dict, List, Optional, Tuple

# T5DS: Result object capturing one truck route, stop sequence, capacity usage, and distance for an optimization solution.
class RouteOptimizationResult:
    """Represents the optimal routing solution for a single truck."""

    def __init__(
        self,
        truck_id: str,
        bins: List[str],
        stop_sequence: List[str],
        collected_weight_kg: int,
        capacity_utilization_pct: float,
        route_distance_km: float,
    ) -> None:
        self.truck_id = truck_id
        self.bins = bins
        self.stop_sequence = stop_sequence
        self.collected_weight_kg = collected_weight_kg
        self.capacity_utilization_pct = capacity_utilization_pct
        self.route_distance_km = route_distance_km

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "truck_id": self.truck_id,
            "bins": self.bins,
            "stop_sequence": self.stop_sequence,
            "collected_weight_kg": self.collected_weight_kg,
            "capacity_utilization_pct": self.capacity_utilization_pct,
            "route_distance_km": self.route_distance_km,
        }


# T5DS: Helper function that measures the full route cost from depot to bins to dump and back.
def calculate_route_distance(
    depot_id: str,
    dump_id: str,
    bin_seq: List[str],
    dist_matrix: Dict[str, Dict[str, float]],
) -> float:
    """Calculate total road distance for route: depot -> bin_1 -> ... -> bin_k -> dump -> depot."""
    if not bin_seq:
        return 0.0
    dist = dist_matrix[depot_id][bin_seq[0]]
    for i in range(len(bin_seq) - 1):
        dist += dist_matrix[bin_seq[i]][bin_seq[i + 1]]
    dist += dist_matrix[bin_seq[-1]][dump_id]
    dist += dist_matrix[dump_id][depot_id]
    return dist


# T5DS: Local-search optimization that improves a delivery order by reversing segments to reduce total route distance.
def two_opt_sequence(
    depot_id: str,
    dump_id: str,
    bin_seq: List[str],
    dist_matrix: Dict[str, Dict[str, float]],
    max_iterations: int = 500,
) -> List[str]:
    """Perform 2-opt local search to find shortest sequence visiting the given bins."""
    if len(bin_seq) <= 1:
        return list(bin_seq)


    best_seq = list(bin_seq)
    best_cost = calculate_route_distance(depot_id, dump_id, best_seq, dist_matrix)
    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1
        for i in range(len(best_seq)):
            for j in range(i + 1, len(best_seq)):
                candidate = best_seq[:i] + best_seq[i : j + 1][::-1] + best_seq[j + 1 :]
                candidate_cost = calculate_route_distance(depot_id, dump_id, candidate, dist_matrix)
                if candidate_cost < best_cost - 1e-6:
                    best_seq = candidate
                    best_cost = candidate_cost
                    improved = True
                    break
            if improved:
                break

    return best_seq


# T5DS: Main Clarke-Wright optimizer that merges routes by savings and enforces truck capacity constraints.
class ClarkeWrightOptimizer:
    """Clarke-Wright Savings heuristic solver for Capacitated Vehicle Routing with Fixed Start Depot and Dump Destination."""

    def __init__(
        self,
        depot_id: str,
        dump_id: str,
        bins: List[Dict[str, Any]],
        dist_matrix: Dict[str, Dict[str, float]],
        truck_count: int,
        truck_capacity_kg: int,
    ) -> None:
        """Initialize Clarke-Wright optimizer parameters.

        Args:
            depot_id: Start and return depot node ID (e.g., 'D0').
            dump_id: Waste disposal / destination node ID (e.g., 'T1').
            bins: List of bin dicts with 'id' and 'weight_kg'.
            dist_matrix: All-pairs shortest path distance lookup matrix.
            truck_count: Total available trucks in the fleet.
            truck_capacity_kg: Maximum payload capacity per truck in kg.
        """
        self.depot_id = depot_id
        self.dump_id = dump_id
        self.bins = bins
        self.dist_matrix = dist_matrix
        self.truck_count = max(1, truck_count)
        self.truck_capacity_kg = max(1, truck_capacity_kg)

        self.bin_weights: Dict[str, int] = {b["id"]: int(b.get("weight_kg", 0)) for b in bins}
        self.bin_ids: List[str] = [b["id"] for b in bins]
        self.t1_to_d0_dist: float = self.dist_matrix[self.dump_id][self.depot_id]

    def _route_distance(self, bin_seq: List[str]) -> float:
        """Calculate total road travel distance for a sequence of bins: depot -> bins -> dump -> depot."""
        return calculate_route_distance(self.depot_id, self.dump_id, bin_seq, self.dist_matrix)

    def _two_opt(self, bin_seq: List[str]) -> List[str]:
        """Perform 2-opt local search to find the shortest stop sequence for a given set of bins."""
        return two_opt_sequence(self.depot_id, self.dump_id, bin_seq, self.dist_matrix)

    def solve(self) -> Tuple[List[RouteOptimizationResult], float]:
        """Execute the Clarke-Wright Savings Algorithm to generate vehicle routes.

        Returns:
            A tuple of (List of RouteOptimizationResult, total cumulative fleet distance in km).
        """
        if not self.bins:
            return [], 0.0

        # Validate that no individual bin exceeds single truck capacity
        overweight = [b_id for b_id, w in self.bin_weights.items() if w > self.truck_capacity_kg]
        if overweight:
            raise ValueError(
                f"Bins {overweight} exceed single truck capacity ({self.truck_capacity_kg} kg)."
            )

        # 1. Initialize each bin in its own individual route: D0 -> bin -> T1 -> D0
        # routes: list of dicts: {"bins": [b_id], "weight": int}
        routes: List[Dict[str, Any]] = [
            {"bins": [b_id], "weight": self.bin_weights[b_id]} for b_id in self.bin_ids
        ]

        # bin_to_route maps bin_id -> route index in routes list
        bin_to_route: Dict[str, int] = {b_id: idx for idx, b_id in enumerate(self.bin_ids)}

        # 2. Calculate savings for all pairs of distinct bins (i, j)
        # In D0 -> i -> ... -> j -> T1 -> D0, savings is:
        # S(i, j) = dist(i, T1) + dist(D0, j) + dist(T1, D0) - dist(i, j)
        savings: List[Tuple[float, str, str]] = []
        for i in self.bin_ids:
            for j in self.bin_ids:
                if i != j:
                    s_val = (
                        self.dist_matrix[i][self.dump_id]
                        + self.dist_matrix[self.depot_id][j]
                        + self.t1_to_d0_dist
                        - self.dist_matrix[i][j]
                    )
                    savings.append((s_val, i, j))

        # Sort savings descending
        savings.sort(key=lambda item: item[0], reverse=True)

        initial_route_count = len(routes)
        initial_heuristic_dist = sum(self._route_distance(r["bins"]) for r in routes)

        # 3. Iteratively merge routes according to savings list
        for s_val, i, j in savings:
            route_i_idx = bin_to_route[i]
            route_j_idx = bin_to_route[j]

            # Condition 1: i and j must be in different routes
            if route_i_idx == route_j_idx:
                continue

            route_i = routes[route_i_idx]
            route_j = routes[route_j_idx]

            # If either route has already been merged into another (empty bins), skip
            if not route_i["bins"] or not route_j["bins"]:
                continue

            # Condition 2: Combined weight must not exceed truck capacity
            combined_weight = route_i["weight"] + route_j["weight"]
            if combined_weight > self.truck_capacity_kg:
                continue

            # Condition 3: Check endpoint/exterior merge configurations
            seq_i = route_i["bins"]
            seq_j = route_j["bins"]

            candidate_merges: List[List[str]] = []

            # Tail of i to Head of j: ... -> i -> j -> ...
            if seq_i[-1] == i and seq_j[0] == j:
                candidate_merges.append(seq_i + seq_j)

            # Tail of j to Head of i: ... -> j -> i -> ...
            if seq_j[-1] == j and seq_i[0] == i:
                candidate_merges.append(seq_j + seq_i)

            # Tail of i to Tail of j: ... -> i -> reversed(j)
            if seq_i[-1] == i and seq_j[-1] == j:
                candidate_merges.append(seq_i + seq_j[::-1])

            # Head of i to Head of j: reversed(i) -> j -> ...
            if seq_i[0] == i and seq_j[0] == j:
                candidate_merges.append(seq_i[::-1] + seq_j)

            if not candidate_merges:
                continue

            # Find the best candidate merge that strictly maximizes distance savings
            original_cost = self._route_distance(seq_i) + self._route_distance(seq_j)
            best_candidate: Optional[List[str]] = None
            best_saving = -float("inf")

            for cand in candidate_merges:
                cand_cost = self._route_distance(cand)
                saving_gain = original_cost - cand_cost
                if saving_gain > best_saving:
                    best_saving = saving_gain
                    best_candidate = cand

            # Accept merge if it saves distance OR if we still need to reduce routes to meet fleet size
            active_route_count = sum(1 for r in routes if r["bins"])
            accept_merge = False
            if best_candidate is not None:
                if best_saving > 1e-6:
                    accept_merge = True
                elif active_route_count > self.truck_count and best_saving >= -1e-4:
                    accept_merge = True

            if accept_merge and best_candidate is not None:
                # Perform the merge: place combined sequence into route_i, clear route_j
                routes[route_i_idx]["bins"] = best_candidate
                routes[route_i_idx]["weight"] = combined_weight
                routes[route_j_idx]["bins"] = []
                routes[route_j_idx]["weight"] = 0

                # Update bin_to_route mapping for all bins in the merged route
                for b_id in best_candidate:
                    bin_to_route[b_id] = route_i_idx

        # Filter active non-empty routes
        active_routes = [r for r in routes if r["bins"]]

        # 4. Multi-pass iterative consolidation if routes still exceed truck_count
        while len(active_routes) > self.truck_count:
            active_routes.sort(key=lambda r: r["weight"])
            consolidated_in_pass = False

            for r_idx in range(len(active_routes)):
                if len(active_routes) <= self.truck_count:
                    break
                r_a = active_routes[r_idx]
                if not r_a["bins"]:
                    continue

                best_target_idx: Optional[int] = None
                best_add_cost = float("inf")

                for r_b_idx in range(r_idx + 1, len(active_routes)):
                    r_b = active_routes[r_b_idx]
                    if not r_b["bins"]:
                        continue
                    if r_a["weight"] + r_b["weight"] <= self.truck_capacity_kg:
                        # Evaluate merge cost
                        merged_seq = r_b["bins"] + r_a["bins"]
                        added_cost = self._route_distance(merged_seq) - (self._route_distance(r_b["bins"]) + self._route_distance(r_a["bins"]))
                        if added_cost < best_add_cost:
                            best_add_cost = added_cost
                            best_target_idx = r_b_idx

                if best_target_idx is not None:
                    r_target = active_routes[best_target_idx]
                    r_target["bins"] = r_target["bins"] + r_a["bins"]
                    r_target["weight"] += r_a["weight"]
                    r_a["bins"] = []
                    r_a["weight"] = 0
                    consolidated_in_pass = True

            active_routes = [r for r in active_routes if r["bins"]]
            if not consolidated_in_pass:
                break

        if len(active_routes) > self.truck_count:
            raise ValueError(
                f"Clarke-Wright routing requires {len(active_routes)} trucks, but only {self.truck_count} trucks are available."
            )

        # 5. Refine routes with 2-opt and construct RouteOptimizationResult objects
        results: List[RouteOptimizationResult] = []
        total_fleet_distance = 0.0

        for truck_idx, route in enumerate(active_routes, 1):
            refined_bins = self._two_opt(route["bins"])
            route_dist = self._route_distance(refined_bins)
            collected_weight = route["weight"]
            utilization_pct = round((collected_weight / self.truck_capacity_kg) * 100.0, 2)
            stop_seq = [self.depot_id] + refined_bins + [self.dump_id, self.depot_id]

            results.append(
                RouteOptimizationResult(
                    truck_id=f"TRUCK-{truck_idx}",
                    bins=refined_bins,
                    stop_sequence=stop_seq,
                    collected_weight_kg=collected_weight,
                    capacity_utilization_pct=utilization_pct,
                    route_distance_km=round(route_dist, 2),
                )
            )
            total_fleet_distance += route_dist

        total_fleet_distance = round(total_fleet_distance, 2)

        # Log search resolution metrics
        try:
            from app.utils.logger import log_clarke_wright_progress

            log_clarke_wright_progress(
                initial_routes_count=initial_route_count,
                savings_pairs_evaluated=len(savings),
                initial_distance=initial_heuristic_dist,
                optimal_dist=total_fleet_distance,
                trucks_used=len(results),
            )
        except Exception:
            pass

        return results, total_fleet_distance


# T5DS: First-fit decreasing bin packing used as a fallback to assign waste bins to trucks under capacity.
def partition_bins_ffd(
    bins: List[Dict[str, Any]],
    truck_count: int,
    truck_capacity_kg: int,
) -> Tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Partition bins across trucks using First-Fit Decreasing heuristic.

    Args:
        bins: List of dicts with 'id' and 'weight_kg'.
        truck_count: Number of trucks available.
        truck_capacity_kg: Capacity limit per truck.

    Returns:
        A tuple of (truck_partitions, uncollected_bins) where truck_partitions is a list
        of lists containing bins assigned to each truck (up to truck_count trucks).
    """
    valid_bins = [b for b in bins if int(b.get("weight_kg", 0)) <= truck_capacity_kg]
    overweight_bins = [b for b in bins if int(b.get("weight_kg", 0)) > truck_capacity_kg]

    # Sort valid bins descending by weight for true First-Fit Decreasing (FFD) packing
    valid_bins.sort(key=lambda b: int(b.get("weight_kg", 0)), reverse=True)

    # Allocate bins across trucks using First-Fit (FF) order
    truck_loads = [0] * max(1, truck_count)
    truck_bins: List[List[Dict[str, Any]]] = [[] for _ in range(max(1, truck_count))]
    uncollected_bins: List[Dict[str, Any]] = list(overweight_bins)

    for b in valid_bins:
        weight = int(b.get("weight_kg", 0))
        placed = False
        for t_idx in range(len(truck_loads)):
            if truck_loads[t_idx] + weight <= truck_capacity_kg:
                truck_loads[t_idx] += weight
                truck_bins[t_idx].append(b)
                placed = True
                break
        if not placed:
            uncollected_bins.append(b)

    # Filter out trucks that received 0 bins
    active_truck_bins = [tb for tb in truck_bins if tb]
    return active_truck_bins, uncollected_bins


# T5DS: Selects the feasible set of bins that can be assigned without exceeding truck capacities.
def select_feasible_bins_ffd(
    bins: List[Dict[str, Any]],
    truck_count: int,
    truck_capacity_kg: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Select the maximal feasible subset of bins that can be packed into truck_count trucks.

    Uses First-Fit Decreasing (FFD) bin packing algorithm.
    Filters out any individual bins that exceed single truck capacity.

    Args:
        bins: List of dicts with 'id' and 'weight_kg'.
        truck_count: Number of trucks available.
        truck_capacity_kg: Maximum payload capacity per truck in kg.

    Returns:
        A tuple of (packed_bins, uncollected_bins).
    """
    truck_partitions, uncollected_bins = partition_bins_ffd(bins, truck_count, truck_capacity_kg)
    packed_bins: List[Dict[str, Any]] = []
    for partition in truck_partitions:
        packed_bins.extend(partition)
    return packed_bins, uncollected_bins


# T5DS: Fallback route optimizer that solves each truck partition independently with 2-opt sequencing.
def solve_by_truck_partition(
    depot_id: str,
    dump_id: str,
    truck_partitions: List[List[Dict[str, Any]]],
    dist_matrix: Dict[str, Dict[str, float]],
    truck_capacity_kg: int,
) -> Tuple[List[RouteOptimizationResult], float]:
    """Direct fallback routing solver: sequences each pre-partitioned truck load using 2-opt TSP.

    Guarantees a valid, capacity-feasible routing solution whenever bin packing succeeds.

    Args:
        depot_id: Start depot node ID (e.g., 'D0').
        dump_id: Destination facility node ID (e.g., 'T1').
        truck_partitions: List of bin lists assigned to each active truck.
        dist_matrix: Pairwise road distance matrix.
        truck_capacity_kg: Maximum truck capacity in kg.

    Returns:
        Tuple of (List of RouteOptimizationResult, total cumulative fleet distance in km).
    """
    results: List[RouteOptimizationResult] = []
    total_fleet_dist = 0.0

    for truck_idx, bin_list in enumerate(truck_partitions, 1):
        if not bin_list:
            continue
        bin_ids = [b["id"] for b in bin_list]
        collected_weight = sum(int(b.get("weight_kg", 0)) for b in bin_list)

        # Optimize sequence with 2-opt
        optimized_bins = two_opt_sequence(depot_id, dump_id, bin_ids, dist_matrix)
        route_dist = calculate_route_distance(depot_id, dump_id, optimized_bins, dist_matrix)
        utilization_pct = round((collected_weight / truck_capacity_kg) * 100.0, 2) if truck_capacity_kg > 0 else 0.0
        stop_seq = [depot_id] + optimized_bins + [dump_id, depot_id]

        results.append(
            RouteOptimizationResult(
                truck_id=f"TRUCK-{truck_idx}",
                bins=optimized_bins,
                stop_sequence=stop_seq,
                collected_weight_kg=collected_weight,
                capacity_utilization_pct=utilization_pct,
                route_distance_km=round(route_dist, 2),
            )
        )
        total_fleet_dist += route_dist

    return results, round(total_fleet_dist, 2)


def solve_fleet_routing(
    depot_id: str,
    dump_id: str,
    bins: List[Dict[str, Any]],
    dist_matrix: Dict[str, Dict[str, float]],
    truck_count: int,
    truck_capacity_kg: int,
    allow_fallback: bool = True,
) -> Tuple[List[RouteOptimizationResult], float]:
    """Execute Clarke-Wright Savings fleet routing optimization with partition fallback support."""
    try:
        optimizer = ClarkeWrightOptimizer(
            depot_id=depot_id,
            dump_id=dump_id,
            bins=bins,
            dist_matrix=dist_matrix,
            truck_count=truck_count,
            truck_capacity_kg=truck_capacity_kg,
        )
        return optimizer.solve()
    except ValueError as exc:
        if not allow_fallback:
            raise
        # Fallback to direct FFD truck partitioning + 2-opt sequence optimization
        partitions, _ = partition_bins_ffd(bins, truck_count, truck_capacity_kg)
        if not partitions and bins:
            raise
        return solve_by_truck_partition(
            depot_id=depot_id,
            dump_id=dump_id,
            truck_partitions=partitions,
            dist_matrix=dist_matrix,
            truck_capacity_kg=truck_capacity_kg,
        )

