"""Branch and Bound solver for homogeneous fleet allocation, capacity enforcement, and optimal route sequencing."""

import itertools
from typing import Any, Dict, List, Optional, Tuple


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


class BranchAndBoundOptimizer:
    """Exact & Pruned Branch and Bound solver for Capacitated Vehicle Routing with Fixed Depot and Dump."""

    def __init__(
        self,
        depot_id: str,
        dump_id: str,
        bins: List[Dict[str, Any]],
        dist_matrix: Dict[str, Dict[str, float]],
        truck_count: int,
        truck_capacity_kg: int,
        max_search_nodes: int = 10000,
    ) -> None:
        """Initialize optimizer parameters.

        Args:
            depot_id: Start and end depot node ID (e.g., 'D0').
            dump_id: Waste disposal / destination node ID (e.g., 'T1').
            bins: List of bin dicts with 'id' and 'weight_kg'.
            dist_matrix: All-pairs shortest path distance lookup matrix.
            truck_count: Total available trucks in the fleet.
            truck_capacity_kg: Maximum payload capacity per truck in kg.
            max_search_nodes: Search budget to prevent timeout on large instances.
        """
        self.depot_id = depot_id
        self.dump_id = dump_id
        self.dist_matrix = dist_matrix
        self.truck_count = truck_count
        self.truck_capacity_kg = truck_capacity_kg
        self.max_search_nodes = max_search_nodes

        self.bin_weights: Dict[str, int] = {b["id"]: int(b["weight_kg"]) for b in bins}

        # Order bins by proximity to depot and decreasing weight to encourage coherent vehicle clustering
        self.bins = sorted(
            bins,
            key=lambda b: (self.dist_matrix[self.depot_id][b["id"]], -b["weight_kg"]),
        )
        self.bin_ids: List[str] = [b["id"] for b in self.bins]
        self.num_bins: int = len(self.bins)

        # Fixed disposal-to-depot return leg cost
        self.t1_to_d0_dist: float = self.dist_matrix[self.dump_id][self.depot_id]

        # Memoization cache for TSP sequences and minimal distances of bin subsets
        self._tsp_cache: Dict[Tuple[str, ...], Tuple[float, List[str]]] = {}

        # Precompute minimum incoming and outgoing edges for each bin for lower bounding
        self._min_in_out: Dict[str, float] = {}
        all_nodes = [self.depot_id, self.dump_id] + self.bin_ids
        for b_id in self.bin_ids:
            min_in = min(self.dist_matrix[u][b_id] for u in all_nodes if u != b_id)
            min_out = min(self.dist_matrix[b_id][v] for v in all_nodes if v != b_id)
            self._min_in_out[b_id] = (min_in + min_out) / 2.0

        # Global best solution tracker
        self.best_global_distance: float = float("inf")
        self.best_assignment: Optional[List[List[str]]] = None
        self._nodes_evaluated: int = 0

    def _solve_single_truck_tsp(self, bin_subset: Tuple[str, ...]) -> Tuple[float, List[str]]:
        """Compute the exact minimum distance and stop sequence for a single truck visiting bin_subset.

        Route pattern: depot_id -> permutation(bin_subset) -> dump_id -> depot_id.
        """
        if not bin_subset:
            return 0.0, []

        if bin_subset in self._tsp_cache:
            return self._tsp_cache[bin_subset]

        n = len(bin_subset)
        if n == 1:
            cost = (
                self.dist_matrix[self.depot_id][bin_subset[0]]
                + self.dist_matrix[bin_subset[0]][self.dump_id]
                + self.t1_to_d0_dist
            )
            result = (round(cost, 4), [self.depot_id, bin_subset[0], self.dump_id, self.depot_id])
            self._tsp_cache[bin_subset] = result
            return result

        if n <= 8:
            # Exact brute force permutation search for small subsets
            best_cost = float("inf")
            best_perm: Tuple[str, ...] = ()
            for perm in itertools.permutations(bin_subset):
                cost = self.dist_matrix[self.depot_id][perm[0]]
                for i in range(n - 1):
                    cost += self.dist_matrix[perm[i]][perm[i + 1]]
                cost += self.dist_matrix[perm[-1]][self.dump_id] + self.t1_to_d0_dist
                if cost < best_cost:
                    best_cost = cost
                    best_perm = perm
            result = (round(best_cost, 4), [self.depot_id] + list(best_perm) + [self.dump_id, self.depot_id])
            self._tsp_cache[bin_subset] = result
            return result

        elif n <= 14:
            # Exact Held-Karp dynamic programming with bitmask
            nodes = list(bin_subset)
            dp: Dict[Tuple[int, int], Tuple[float, int]] = {}
            for i, node in enumerate(nodes):
                dp[((1 << i), i)] = (self.dist_matrix[self.depot_id][node], -1)

            for size in range(2, n + 1):
                for comb in itertools.combinations(range(n), size):
                    mask = 0
                    for bit in comb:
                        mask |= 1 << bit
                    for curr in comb:
                        prev_mask = mask ^ (1 << curr)
                        min_val = float("inf")
                        min_prev = -1
                        for prev in comb:
                            if prev == curr:
                                continue
                            val = dp[(prev_mask, prev)][0] + self.dist_matrix[nodes[prev]][nodes[curr]]
                            if val < min_val:
                                min_val = val
                                min_prev = prev
                        dp[(mask, curr)] = (min_val, min_prev)

            full_mask = (1 << n) - 1
            best_cost = float("inf")
            best_last = -1
            for last in range(n):
                val = dp[(full_mask, last)][0] + self.dist_matrix[nodes[last]][self.dump_id] + self.t1_to_d0_dist
                if val < best_cost:
                    best_cost = val
                    best_last = last

            path_idx = []
            curr_mask = full_mask
            curr_node = best_last
            while curr_node != -1:
                path_idx.append(curr_node)
                next_node = dp[(curr_mask, curr_node)][1]
                curr_mask ^= 1 << curr_node
                curr_node = next_node
            path_idx.reverse()

            result = (
                round(best_cost, 4),
                [self.depot_id] + [nodes[i] for i in path_idx] + [self.dump_id, self.depot_id],
            )
            self._tsp_cache[bin_subset] = result
            return result

        else:
            # Nearest Insertion + 2-Opt refinement for larger single-truck sets (>14)
            unvisited = list(bin_subset)
            first_node = min(unvisited, key=lambda b: self.dist_matrix[self.depot_id][b])
            unvisited.remove(first_node)
            tour = [first_node]

            while unvisited:
                best_node = None
                best_pos = 0
                best_inc = float("inf")
                for node in unvisited:
                    # Test start
                    inc = (
                        self.dist_matrix[self.depot_id][node]
                        + self.dist_matrix[node][tour[0]]
                        - self.dist_matrix[self.depot_id][tour[0]]
                    )
                    if inc < best_inc:
                        best_inc = inc
                        best_node = node
                        best_pos = 0
                    # Test interior
                    for i in range(len(tour) - 1):
                        inc = (
                            self.dist_matrix[tour[i]][node]
                            + self.dist_matrix[node][tour[i + 1]]
                            - self.dist_matrix[tour[i]][tour[i + 1]]
                        )
                        if inc < best_inc:
                            best_inc = inc
                            best_node = node
                            best_pos = i + 1
                    # Test end
                    inc = (
                        self.dist_matrix[tour[-1]][node]
                        + self.dist_matrix[node][self.dump_id]
                        - self.dist_matrix[tour[-1]][self.dump_id]
                    )
                    if inc < best_inc:
                        best_inc = inc
                        best_node = node
                        best_pos = len(tour)

                if best_node is not None:
                    tour.insert(best_pos, best_node)
                    unvisited.remove(best_node)

            # 2-Opt local search
            improved = True
            while improved:
                improved = False
                for i in range(len(tour) - 1):
                    for j in range(i + 1, len(tour)):
                        prev_node = self.depot_id if i == 0 else tour[i - 1]
                        curr_i = tour[i]
                        curr_j = tour[j]
                        next_node = self.dump_id if j == len(tour) - 1 else tour[j + 1]

                        curr_dist = self.dist_matrix[prev_node][curr_i] + self.dist_matrix[curr_j][next_node]
                        new_dist = self.dist_matrix[prev_node][curr_j] + self.dist_matrix[curr_i][next_node]

                        if new_dist + 1e-6 < curr_dist:
                            tour[i : j + 1] = reversed(tour[i : j + 1])
                            improved = True
                            break
                    if improved:
                        break

            cost = self.dist_matrix[self.depot_id][tour[0]]
            for i in range(len(tour) - 1):
                cost += self.dist_matrix[tour[i]][tour[i + 1]]
            cost += self.dist_matrix[tour[-1]][self.dump_id] + self.t1_to_d0_dist
            result = (round(cost, 4), [self.depot_id] + tour + [self.dump_id, self.depot_id])
            self._tsp_cache[bin_subset] = result
            return result

    def _find_greedy_initial_solution(self) -> None:
        """Compute a fast nearest-neighbor greedy initial solution to set a tight incumbent bound."""
        if not self.bin_ids:
            self.best_global_distance = 0.0
            self.best_assignment = [[] for _ in range(self.truck_count)]
            return

        truck_bins: List[List[str]] = [[] for _ in range(self.truck_count)]
        truck_weights: List[int] = [0 for _ in range(self.truck_count)]

        unassigned = set(self.bin_ids)
        for t_idx in range(self.truck_count):
            if not unassigned:
                break
            current_loc = self.depot_id
            while unassigned:
                candidates = [
                    b
                    for b in unassigned
                    if truck_weights[t_idx] + self.bin_weights[b] <= self.truck_capacity_kg
                ]
                if not candidates:
                    break
                closest_bin = min(candidates, key=lambda b: self.dist_matrix[current_loc][b])
                truck_bins[t_idx].append(closest_bin)
                truck_weights[t_idx] += self.bin_weights[closest_bin]
                unassigned.remove(closest_bin)
                current_loc = closest_bin

        if unassigned:
            # Fallback to First Fit Decreasing
            truck_bins = [[] for _ in range(self.truck_count)]
            truck_weights = [0 for _ in range(self.truck_count)]
            for b_id in sorted(self.bin_ids, key=lambda b: self.bin_weights[b], reverse=True):
                assigned = False
                for t_idx in range(self.truck_count):
                    if truck_weights[t_idx] + self.bin_weights[b_id] <= self.truck_capacity_kg:
                        truck_bins[t_idx].append(b_id)
                        truck_weights[t_idx] += self.bin_weights[b_id]
                        assigned = True
                        break
                if not assigned:
                    return

        total_dist = 0.0
        for subset in truck_bins:
            if subset:
                cost, _ = self._solve_single_truck_tsp(tuple(sorted(subset)))
                total_dist += cost

        self.best_global_distance = total_dist
        self.best_assignment = [list(subset) for subset in truck_bins]

    def solve(self) -> Tuple[List[RouteOptimizationResult], float]:
        """Execute the Branch and Bound search algorithm.

        Returns:
            A tuple of (list of RouteOptimizationResult for dispatched trucks, total fleet distance).
        """
        if self.num_bins == 0:
            return [], 0.0

        # Set initial upper bound using heuristic
        self._find_greedy_initial_solution()
        initial_heuristic_dist = self.best_global_distance

        initial_assignments: List[List[str]] = [[] for _ in range(self.truck_count)]
        initial_weights: List[int] = [0 for _ in range(self.truck_count)]
        self._nodes_evaluated = 0

        # Start recursive branch and bound exploration
        self._branch_and_bound(0, initial_assignments, initial_weights)

        if self.best_assignment is None:
            raise ValueError(
                "No feasible fleet route allocation found within the given truck capacity and count constraints."
            )

        # Build final RouteOptimizationResult objects for all active trucks
        results: List[RouteOptimizationResult] = []
        total_distance = 0.0
        truck_idx = 1

        for subset in self.best_assignment:
            if not subset:
                continue

            cost, stop_seq = self._solve_single_truck_tsp(tuple(sorted(subset)))
            collected_weight = sum(self.bin_weights[b] for b in subset)
            utilization = round((collected_weight / self.truck_capacity_kg) * 100.0, 2)

            results.append(
                RouteOptimizationResult(
                    truck_id=f"TRUCK-{truck_idx}",
                    bins=subset,
                    stop_sequence=stop_seq,
                    collected_weight_kg=collected_weight,
                    capacity_utilization_pct=utilization,
                    route_distance_km=cost,
                )
            )
            total_distance += cost
            truck_idx += 1

        from app.utils.logger import log_branch_and_bound_progress
        log_branch_and_bound_progress(
            initial_heuristic_dist=initial_heuristic_dist,
            optimal_dist=round(total_distance, 4),
            trucks_used=len(results),
        )

        return results, round(total_distance, 4)

    def _branch_and_bound(
        self,
        bin_idx: int,
        current_assignments: List[List[str]],
        current_weights: List[int],
    ) -> None:
        """Recursive Branch and Bound search step with capacity and distance pruning.

        Args:
            bin_idx: Index of current bin in self.bin_ids being assigned.
            current_assignments: Current bins assigned to each truck.
            current_weights: Current total payload weight on each truck.
        """
        self._nodes_evaluated += 1
        if self._nodes_evaluated > self.max_search_nodes:
            return

        # Leaf node: all bins assigned successfully
        if bin_idx == self.num_bins:
            total_cost = 0.0
            for subset in current_assignments:
                if subset:
                    cost, _ = self._solve_single_truck_tsp(tuple(sorted(subset)))
                    total_cost += cost

            if total_cost < self.best_global_distance:
                self.best_global_distance = total_cost
                self.best_assignment = [list(subset) for subset in current_assignments]
            return

        current_bin_id = self.bin_ids[bin_idx]
        current_bin_weight = self.bin_weights[current_bin_id]

        # Remaining capacity feasibility check
        remaining_unassigned_weight = sum(
            self.bin_weights[self.bin_ids[i]] for i in range(bin_idx, self.num_bins)
        )
        total_available_capacity = sum(
            self.truck_capacity_kg - w for w in current_weights
        )
        if remaining_unassigned_weight > total_available_capacity:
            # Capacity Pruning: remaining waste cannot fit into available remaining space
            return

        # Lower bound distance pruning
        lb = 0.0
        for subset in current_assignments:
            if subset:
                cost, _ = self._solve_single_truck_tsp(tuple(sorted(subset)))
                lb += cost
        for idx in range(bin_idx, self.num_bins):
            lb += self._min_in_out[self.bin_ids[idx]]

        if lb >= self.best_global_distance:
            # Distance Bound Pruning: this branch cannot beat current best known solution
            return

        # Order candidate trucks by proximity to this bin for optimal search order
        truck_candidates = []
        for t_idx in range(self.truck_count):
            if current_weights[t_idx] + current_bin_weight <= self.truck_capacity_kg:
                if len(current_assignments[t_idx]) == 0:
                    truck_dist = self.dist_matrix[self.depot_id][current_bin_id]
                else:
                    last_bin = current_assignments[t_idx][-1]
                    truck_dist = self.dist_matrix[last_bin][current_bin_id]
                truck_candidates.append((truck_dist, t_idx))

        truck_candidates.sort(key=lambda x: x[0])

        first_empty_truck_encountered = False

        for _, t_idx in truck_candidates:
            is_empty_truck = len(current_assignments[t_idx]) == 0

            # Symmetry Breaking: only branch once on the first empty truck
            if is_empty_truck:
                if first_empty_truck_encountered:
                    continue
                first_empty_truck_encountered = True

            # Branch: Assign bin to truck t_idx
            current_assignments[t_idx].append(current_bin_id)
            current_weights[t_idx] += current_bin_weight

            self._branch_and_bound(bin_idx + 1, current_assignments, current_weights)

            # Backtrack
            current_assignments[t_idx].pop()
            current_weights[t_idx] -= current_bin_weight


def solve_fleet_routing(
    depot_id: str,
    dump_id: str,
    bins: List[Dict[str, Any]],
    dist_matrix: Dict[str, Dict[str, float]],
    truck_count: int,
    truck_capacity_kg: int,
) -> Tuple[List[RouteOptimizationResult], float]:
    """Helper function to execute Branch and Bound fleet routing optimization."""
    optimizer = BranchAndBoundOptimizer(
        depot_id=depot_id,
        dump_id=dump_id,
        bins=bins,
        dist_matrix=dist_matrix,
        truck_count=truck_count,
        truck_capacity_kg=truck_capacity_kg,
    )
    return optimizer.solve()
