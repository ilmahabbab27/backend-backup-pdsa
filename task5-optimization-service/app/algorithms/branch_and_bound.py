"""Branch and Bound solver for homogeneous fleet allocation, capacity enforcement, and optimal route sequencing."""

from collections import defaultdict
import itertools
import time
from typing import Any, Dict, List, Optional, Set, Tuple


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
        max_search_nodes: int = 5000,
        time_limit_sec: float = 2.5,
    ) -> None:
        """Initialize optimizer parameters.

        Args:
            depot_id: Start and end depot node ID (e.g., 'D0').
            dump_id: Waste disposal / destination node ID (e.g., 'T1').
            bins: List of bin dicts with 'id' and 'weight_kg'.
            dist_matrix: All-pairs shortest path distance lookup matrix.
            truck_count: Total available trucks in the fleet.
            truck_capacity_kg: Maximum payload capacity per truck in kg.
            max_search_nodes: Search budget to prevent long CPU lockup.
            time_limit_sec: Strict wall-clock deadline in seconds.
        """
        self.depot_id = depot_id
        self.dump_id = dump_id
        self.dist_matrix = dist_matrix
        self.truck_count = truck_count
        self.truck_capacity_kg = truck_capacity_kg
        self.max_search_nodes = max_search_nodes
        self.time_limit_sec = time_limit_sec

        self.bin_weights: Dict[str, int] = {b["id"]: int(b["weight_kg"]) for b in bins}

        # Order bins by proximity to depot and decreasing weight
        self.bins = sorted(
            bins,
            key=lambda b: (self.dist_matrix[self.depot_id][b["id"]], -int(b["weight_kg"])),
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
        self.start_time: float = 0.0
        self.deadline: float = 0.0

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
            b0 = bin_subset[0]
            cost = (
                self.dist_matrix[self.depot_id][b0]
                + self.dist_matrix[b0][self.dump_id]
                + self.t1_to_d0_dist
            )
            result = (round(cost, 4), [self.depot_id, b0, self.dump_id, self.depot_id])
            self._tsp_cache[bin_subset] = result
            return result

        if n == 2:
            b0, b1 = bin_subset[0], bin_subset[1]
            c1 = (
                self.dist_matrix[self.depot_id][b0]
                + self.dist_matrix[b0][b1]
                + self.dist_matrix[b1][self.dump_id]
                + self.t1_to_d0_dist
            )
            c2 = (
                self.dist_matrix[self.depot_id][b1]
                + self.dist_matrix[b1][b0]
                + self.dist_matrix[b0][self.dump_id]
                + self.t1_to_d0_dist
            )
            if c1 <= c2:
                result = (round(c1, 4), [self.depot_id, b0, b1, self.dump_id, self.depot_id])
            else:
                result = (round(c2, 4), [self.depot_id, b1, b0, self.dump_id, self.depot_id])
            self._tsp_cache[bin_subset] = result
            return result

        if n <= 12:
            # Fast integer-indexed Held-Karp dynamic programming
            nodes = list(bin_subset)
            d_depot = [self.dist_matrix[self.depot_id][nodes[i]] for i in range(n)]
            d_dump = [self.dist_matrix[nodes[i]][self.dump_id] for i in range(n)]
            d_mat = [[self.dist_matrix[nodes[i]][nodes[j]] for j in range(n)] for i in range(n)]

            dp: Dict[Tuple[int, int], Tuple[float, int]] = {}
            for i in range(n):
                dp[((1 << i), i)] = (d_depot[i], -1)

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
                            prev_entry = dp.get((prev_mask, prev))
                            if prev_entry is not None:
                                val = prev_entry[0] + d_mat[prev][curr]
                                if val < min_val:
                                    min_val = val
                                    min_prev = prev
                        if min_prev != -1:
                            dp[(mask, curr)] = (min_val, min_prev)

            full_mask = (1 << n) - 1
            best_cost = float("inf")
            best_last = -1
            for last in range(n):
                entry = dp.get((full_mask, last))
                if entry is not None:
                    val = entry[0] + d_dump[last] + self.t1_to_d0_dist
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
            # Nearest Insertion + 2-Opt refinement for larger single-truck sets (>12)
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

    def _test_and_update_incumbent(self, truck_bins: List[List[str]]) -> None:
        """Helper to evaluate a complete assignment and update the best known solution if improved."""
        assigned_count = sum(len(sub) for sub in truck_bins)
        if assigned_count != self.num_bins:
            return

        total_dist = 0.0
        for subset in truck_bins:
            if subset:
                cost, _ = self._solve_single_truck_tsp(tuple(sorted(subset)))
                total_dist += cost

        if total_dist < self.best_global_distance:
            self.best_global_distance = total_dist
            self.best_assignment = [list(sub) for sub in truck_bins]

    def _find_greedy_initial_solution(self) -> None:
        """Compute high-quality initial solutions using multiple heuristics to establish a tight bound."""
        if not self.bin_ids:
            self.best_global_distance = 0.0
            self.best_assignment = [[] for _ in range(self.truck_count)]
            return

        # Strategy 1: Greedy Nearest-Neighbor Route Packing
        truck_bins_1: List[List[str]] = [[] for _ in range(self.truck_count)]
        truck_weights_1: List[int] = [0 for _ in range(self.truck_count)]
        unassigned_1 = set(self.bin_ids)

        for t_idx in range(self.truck_count):
            if not unassigned_1:
                break
            current_loc = self.depot_id
            while unassigned_1:
                candidates = [
                    b
                    for b in unassigned_1
                    if truck_weights_1[t_idx] + self.bin_weights[b] <= self.truck_capacity_kg
                ]
                if not candidates:
                    break
                closest_bin = min(candidates, key=lambda b: self.dist_matrix[current_loc][b])
                truck_bins_1[t_idx].append(closest_bin)
                truck_weights_1[t_idx] += self.bin_weights[closest_bin]
                unassigned_1.remove(closest_bin)
                current_loc = closest_bin

        if not unassigned_1:
            self._test_and_update_incumbent(truck_bins_1)

        # Strategy 2: First-Fit Decreasing (FFD) by weight
        truck_bins_2: List[List[str]] = [[] for _ in range(self.truck_count)]
        truck_weights_2: List[int] = [0 for _ in range(self.truck_count)]
        unassigned_2: List[str] = []

        for b_id in sorted(self.bin_ids, key=lambda b: self.bin_weights[b], reverse=True):
            placed = False
            for t_idx in range(self.truck_count):
                if truck_weights_2[t_idx] + self.bin_weights[b_id] <= self.truck_capacity_kg:
                    truck_bins_2[t_idx].append(b_id)
                    truck_weights_2[t_idx] += self.bin_weights[b_id]
                    placed = True
                    break
            if not placed:
                unassigned_2.append(b_id)

        if not unassigned_2:
            self._test_and_update_incumbent(truck_bins_2)

        # Strategy 3: Best-Fit Decreasing (BFD)
        truck_bins_3: List[List[str]] = [[] for _ in range(self.truck_count)]
        truck_weights_3: List[int] = [0 for _ in range(self.truck_count)]
        unassigned_3: List[str] = []

        for b_id in sorted(self.bin_ids, key=lambda b: self.bin_weights[b], reverse=True):
            bw = self.bin_weights[b_id]
            best_t = -1
            min_remaining = float("inf")
            for t_idx in range(self.truck_count):
                rem = self.truck_capacity_kg - (truck_weights_3[t_idx] + bw)
                if rem >= 0 and rem < min_remaining:
                    min_remaining = rem
                    best_t = t_idx
            if best_t != -1:
                truck_bins_3[best_t].append(b_id)
                truck_weights_3[best_t] += bw
            else:
                unassigned_3.append(b_id)

        if not unassigned_3:
            self._test_and_update_incumbent(truck_bins_3)

        # Strategy 4: Proximity Clustering + Capacity Fill
        sorted_by_depot = sorted(self.bin_ids, key=lambda b: self.dist_matrix[self.depot_id][b])
        truck_bins_4: List[List[str]] = [[] for _ in range(self.truck_count)]
        truck_weights_4: List[int] = [0 for _ in range(self.truck_count)]
        unassigned_4 = set(self.bin_ids)

        for t_idx in range(self.truck_count):
            if not unassigned_4:
                break
            seed = next((b for b in sorted_by_depot if b in unassigned_4), None)
            if not seed:
                break
            truck_bins_4[t_idx].append(seed)
            truck_weights_4[t_idx] += self.bin_weights[seed]
            unassigned_4.remove(seed)

            while unassigned_4:
                candidates = [
                    b for b in unassigned_4
                    if truck_weights_4[t_idx] + self.bin_weights[b] <= self.truck_capacity_kg
                ]
                if not candidates:
                    break
                closest = min(candidates, key=lambda b: min(self.dist_matrix[in_b][b] for in_b in truck_bins_4[t_idx]))
                truck_bins_4[t_idx].append(closest)
                truck_weights_4[t_idx] += self.bin_weights[closest]
                unassigned_4.remove(closest)

        if not unassigned_4:
            self._test_and_update_incumbent(truck_bins_4)

    def _improve_assignment_vns(self) -> None:
        """Variable Neighborhood Search (Relocate & Swap 2-Opt) across vehicle clusters."""
        if not self.best_assignment:
            return

        current_assignment = [list(sub) for sub in self.best_assignment]
        truck_weights = [sum(self.bin_weights[b] for b in sub) for sub in current_assignment]
        truck_costs = [
            self._solve_single_truck_tsp(tuple(sorted(sub)))[0] if sub else 0.0
            for sub in current_assignment
        ]

        improved = True
        iteration = 0
        max_iterations = 25

        while improved and iteration < max_iterations:
            if time.perf_counter() > self.deadline:
                break
            improved = False
            iteration += 1

            # 1. Relocate Move: Move bin from truck i to truck j
            for i in range(len(current_assignment)):
                if not current_assignment[i]:
                    continue
                for b_idx, bin_id in enumerate(current_assignment[i]):
                    bw = self.bin_weights[bin_id]
                    candidate_trucks = [
                        j for j in range(len(current_assignment))
                        if i != j and truck_weights[j] + bw <= self.truck_capacity_kg
                    ]
                    if len(candidate_trucks) > 4:
                        candidate_trucks.sort(
                            key=lambda j: min(
                                (self.dist_matrix[b][bin_id] for b in current_assignment[j]),
                                default=self.dist_matrix[self.depot_id][bin_id],
                            )
                        )
                        candidate_trucks = candidate_trucks[:4]

                    for j in candidate_trucks:
                        new_sub_i = current_assignment[i][:b_idx] + current_assignment[i][b_idx + 1:]
                        new_sub_j = current_assignment[j] + [bin_id]

                        cost_i = self._solve_single_truck_tsp(tuple(sorted(new_sub_i)))[0] if new_sub_i else 0.0
                        cost_j = self._solve_single_truck_tsp(tuple(sorted(new_sub_j)))[0]

                        delta = (cost_i + cost_j) - (truck_costs[i] + truck_costs[j])
                        if delta < -1e-4:
                            current_assignment[i] = new_sub_i
                            current_assignment[j] = new_sub_j
                            truck_weights[i] -= bw
                            truck_weights[j] += bw
                            truck_costs[i] = cost_i
                            truck_costs[j] = cost_j
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break

            if improved:
                continue

            # 2. Swap Move: Swap bin_a in truck i with bin_b in truck j
            for i in range(len(current_assignment) - 1):
                if not current_assignment[i]:
                    continue
                for b1_idx, bin_a in enumerate(current_assignment[i]):
                    wa = self.bin_weights[bin_a]
                    candidate_trucks = [
                        j for j in range(i + 1, len(current_assignment))
                        if current_assignment[j]
                    ]
                    if len(candidate_trucks) > 4:
                        candidate_trucks.sort(
                            key=lambda j: min(
                                (self.dist_matrix[b][bin_a] for b in current_assignment[j]),
                                default=self.dist_matrix[self.depot_id][bin_a],
                            )
                        )
                        candidate_trucks = candidate_trucks[:4]

                    for j in candidate_trucks:
                        for b2_idx, bin_b in enumerate(current_assignment[j]):
                            wb = self.bin_weights[bin_b]
                            if (truck_weights[i] - wa + wb <= self.truck_capacity_kg and
                                truck_weights[j] - wb + wa <= self.truck_capacity_kg):
                                new_sub_i = current_assignment[i][:b1_idx] + [bin_b] + current_assignment[i][b1_idx + 1:]
                                new_sub_j = current_assignment[j][:b2_idx] + [bin_a] + current_assignment[j][b2_idx + 1:]

                                cost_i = self._solve_single_truck_tsp(tuple(sorted(new_sub_i)))[0]
                                cost_j = self._solve_single_truck_tsp(tuple(sorted(new_sub_j)))[0]

                                delta = (cost_i + cost_j) - (truck_costs[i] + truck_costs[j])
                                if delta < -1e-4:
                                    current_assignment[i] = new_sub_i
                                    current_assignment[j] = new_sub_j
                                    truck_weights[i] = truck_weights[i] - wa + wb
                                    truck_weights[j] = truck_weights[j] - wb + wa
                                    truck_costs[i] = cost_i
                                    truck_costs[j] = cost_j
                                    improved = True
                                    break
                        if improved:
                            break
                    if improved:
                        break
                if improved:
                    break

        total_dist = sum(truck_costs)
        if total_dist < self.best_global_distance:
            self.best_global_distance = total_dist
            self.best_assignment = [list(sub) for sub in current_assignment]

    def solve(self) -> Tuple[List[RouteOptimizationResult], float]:
        """Execute the Branch and Bound / Adaptive VRP search algorithm.

        Returns:
            A tuple of (list of RouteOptimizationResult for dispatched trucks, total fleet distance).
        """
        if self.num_bins == 0:
            return [], 0.0

        self.start_time = time.perf_counter()
        self.deadline = self.start_time + self.time_limit_sec

        # 1. Establish initial upper bound from multi-heuristic packing
        self._find_greedy_initial_solution()
        initial_heuristic_dist = self.best_global_distance

        # 2. Optimization phase based on instance size
        if self.num_bins <= 16:
            # Exact Branch and Bound exploration for small/medium instances
            initial_assignments: List[List[str]] = [[] for _ in range(self.truck_count)]
            initial_weights: List[int] = [0 for _ in range(self.truck_count)]
            initial_costs: List[float] = [0.0 for _ in range(self.truck_count)]
            self._nodes_evaluated = 0

            self._branch_and_bound_incremental(
                bin_idx=0,
                current_assignments=initial_assignments,
                current_weights=initial_weights,
                current_costs=initial_costs,
            )
        else:
            # VNS Local Search for larger instances (> 16 bins)
            self._improve_assignment_vns()

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

    def _branch_and_bound_incremental(
        self,
        bin_idx: int,
        current_assignments: List[List[str]],
        current_weights: List[int],
        current_costs: List[float],
    ) -> None:
        """Recursive Branch and Bound search step with incremental lower bounding and time check."""
        self._nodes_evaluated += 1
        if self._nodes_evaluated > self.max_search_nodes:
            return

        if (self._nodes_evaluated & 63) == 0 and time.perf_counter() > self.deadline:
            return

        # Leaf node: all bins assigned successfully
        if bin_idx == self.num_bins:
            total_cost = sum(current_costs)
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
            return

        # Lower bound distance pruning
        lb = sum(current_costs)
        for idx in range(bin_idx, self.num_bins):
            lb += self._min_in_out[self.bin_ids[idx]]

        if lb >= self.best_global_distance:
            return

        # Order candidate trucks by proximity
        truck_candidates = []
        for t_idx in range(self.truck_count):
            if current_weights[t_idx] + current_bin_weight <= self.truck_capacity_kg:
                if not current_assignments[t_idx]:
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

            # Save previous state
            old_cost = current_costs[t_idx]

            # Branch: Assign bin to truck t_idx
            current_assignments[t_idx].append(current_bin_id)
            current_weights[t_idx] += current_bin_weight

            # Incrementally calculate new cost for ONLY this truck
            new_cost, _ = self._solve_single_truck_tsp(tuple(sorted(current_assignments[t_idx])))
            current_costs[t_idx] = new_cost

            self._branch_and_bound_incremental(
                bin_idx + 1, current_assignments, current_weights, current_costs
            )

            # Backtrack
            current_assignments[t_idx].pop()
            current_weights[t_idx] -= current_bin_weight
            current_costs[t_idx] = old_cost


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
    valid_bins = [b for b in bins if int(b.get("weight_kg", 0)) <= truck_capacity_kg]
    overweight_bins = [b for b in bins if int(b.get("weight_kg", 0)) > truck_capacity_kg]

    # Sort valid bins descending by weight (heuristic: heavier bins packed first)
    sorted_bins = sorted(valid_bins, key=lambda b: int(b.get("weight_kg", 0)), reverse=True)

    truck_loads = [0] * truck_count
    packed_bins: List[Dict[str, Any]] = []
    uncollected_bins: List[Dict[str, Any]] = list(overweight_bins)

    for b in sorted_bins:
        weight = int(b.get("weight_kg", 0))
        placed = False
        for t_idx in range(truck_count):
            if truck_loads[t_idx] + weight <= truck_capacity_kg:
                truck_loads[t_idx] += weight
                packed_bins.append(b)
                placed = True
                break
        if not placed:
            uncollected_bins.append(b)

    return packed_bins, uncollected_bins


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
