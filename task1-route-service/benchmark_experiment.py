"""Performance experiment runner measuring empirical BFS, Dijkstra, and A* performance."""

import json
from app.services.route_service import RouteService

if __name__ == "__main__":
    service = RouteService()
    print("Running systematic benchmark experiment across Small, Medium, Large graphs...")
    benchmark = service.run_benchmarks(iterations=50)

    print("\n================ BENCHMARK RESULTS (Averaged over 50 runs) ================")
    for tier in benchmark.tiers:
        print(f"\n--- {tier.tier_name} (|V|={tier.node_count}, |E|={tier.edge_count}) ---")
        print(f"  BFS:      Time = {tier.bfs_time_ms:.4f} ms | Nodes Explored = {tier.bfs_nodes}")
        print(f"  Dijkstra: Time = {tier.dijkstra_time_ms:.4f} ms | Nodes Explored = {tier.dijkstra_nodes}")
        print(f"  A*:       Time = {tier.astar_time_ms:.4f} ms | Nodes Explored = {tier.astar_nodes}")

    print("\n--- Direct Comparison on Smart City Graph: city-hall -> central-hospital ---")
    comp = service.compare_algorithms("city-hall", "central-hospital")
    for r in comp.results:
        print(f"  Algorithm: {r.algorithm:10} | Distance: {r.distance:5.1f} km | Hops: {r.hops} | Nodes Explored: {r.nodes_explored:2} | Time: {r.execution_time_ms:.4f} ms | Optimal: {r.is_optimal_distance}")

    print(f"\nAnalysis: {comp.analysis}")
    print(f"\nConclusion: {benchmark.conclusion}")
