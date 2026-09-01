"""Rich terminal logging and formatted process output utility for the Waste Optimization Service."""

from datetime import datetime
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure stdout and stderr handle utf-8 cleanly across Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class TerminalColors:
    """ANSI escape sequences for styled terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Colors
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def _ts() -> str:
    """Return formatted current time string."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log_startup_banner(
    app_name: str,
    port: int,
    map_path: str,
    node_counts: Dict[str, int],
    edge_count: int,
    total_waste_kg: int,
) -> None:
    """Print a startup banner with road network statistics."""
    c = TerminalColors
    print(flush=True)
    print(f"{c.CYAN}{c.BOLD}{'=' * 80}{c.RESET}", flush=True)
    print(f"{c.CYAN}{c.BOLD}  >> {app_name.upper()}{c.RESET}", flush=True)
    print(f"{c.CYAN}{c.BOLD}{'=' * 80}{c.RESET}", flush=True)
    print(f"  {c.GREEN}[*] Status:{c.RESET}           Service Online & Ready", flush=True)
    print(f"  {c.GREEN}[*] Port:{c.RESET}             http://127.0.0.1:{port}", flush=True)
    print(f"  {c.GREEN}[*] Interactive Docs:{c.RESET} http://127.0.0.1:{port}/docs", flush=True)
    print(f"  {c.GREEN}[*] Map Data File:{c.RESET}    {map_path}", flush=True)
    print(f"  {c.CYAN}{'-' * 80}{c.RESET}", flush=True)
    print(f"  {c.BOLD}[+] Road Network Topology:{c.RESET}", flush=True)
    print(f"     - Start Depot (D0):         {node_counts.get('start', 0)} node", flush=True)
    print(f"     - Disposal Facility (T1):   {node_counts.get('destination', 0)} node", flush=True)
    print(f"     - Smart Waste Bins:         {node_counts.get('bin', 0)} bins (Total: {total_waste_kg:,} kg)", flush=True)
    print(f"     - Road Intersections:       {node_counts.get('intersection', 0)} junctions", flush=True)
    print(f"     - Total Graph Vertices:     {sum(node_counts.values())} nodes", flush=True)
    print(f"     - Navigable Road Segments:  {edge_count} bidirectional edges", flush=True)
    print(f"{c.CYAN}{c.BOLD}{'=' * 80}{c.RESET}\n", flush=True)


def log_request(method: str, path: str, client: str = "") -> None:
    """Print incoming HTTP request notification."""
    c = TerminalColors
    color = c.GREEN if method == "GET" else c.CYAN
    print(f"{c.DIM}[{_ts()}]{c.RESET} {c.BOLD}{color}>> INCOMING REQUEST:{c.RESET} {c.BOLD}{method}{c.RESET} {path} {c.DIM}(from {client}){c.RESET}", flush=True)


def log_response(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Print completed HTTP response status."""
    c = TerminalColors
    color = c.GREEN if status_code < 400 else c.RED
    print(f"{c.DIM}[{_ts()}]{c.RESET} {color}<< COMPLETED RESPONSE:{c.RESET} {method} {path} -> {c.BOLD}{status_code}{c.RESET} ({duration_ms:.2f} ms)\n", flush=True)


def log_step(step_num: int, total_steps: int, title: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Print structured step in the optimization pipeline."""
    c = TerminalColors
    print(f"  {c.CYAN}{c.BOLD}[STEP {step_num}/{total_steps}]{c.RESET} {c.BOLD}{title}{c.RESET}", flush=True)
    if details:
        for k, v in details.items():
            print(f"    {c.DIM}|-{c.RESET} {c.WHITE}{k}:{c.RESET} {c.BRIGHT_CYAN}{v}{c.RESET}", flush=True)


def log_optimization_start(truck_count: int, truck_capacity_kg: int, total_bins: int, total_waste_kg: int) -> None:
    """Print optimization run start header."""
    c = TerminalColors
    print(flush=True)
    print(f"{c.YELLOW}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"{c.YELLOW}{c.BOLD}|           [OPTIMIZATION] WASTE COLLECTION FLEET OPTIMIZATION INITIATED      |{c.RESET}", flush=True)
    print(f"{c.YELLOW}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"  {c.BOLD}Parameters Received:{c.RESET}", flush=True)
    print(f"    * Available Fleet Size:     {c.BRIGHT_YELLOW}{truck_count} trucks{c.RESET}", flush=True)
    print(f"    * Payload Capacity/Truck:   {c.BRIGHT_YELLOW}{truck_capacity_kg:,} kg{c.RESET}", flush=True)
    print(f"    * Max Fleet Total Capacity: {c.BRIGHT_YELLOW}{truck_count * truck_capacity_kg:,} kg{c.RESET}", flush=True)
    print(f"    * Smart Bins to Collect:    {c.BRIGHT_YELLOW}{total_bins} bins{c.RESET}", flush=True)
    print(f"    * Total Waste Payload:      {c.BRIGHT_YELLOW}{total_waste_kg:,} kg{c.RESET}", flush=True)
    print(f"{c.YELLOW}{'-' * 79}{c.RESET}", flush=True)


def log_dijkstra_matrix(poi_count: int, sample_routes: List[Tuple[str, str, float]]) -> None:
    """Print Dijkstra all-pairs distance matrix summary."""
    c = TerminalColors
    print(f"    {c.DIM}|-{c.RESET} Precomputed {c.BRIGHT_GREEN}{poi_count}x{poi_count}{c.RESET} ({poi_count * poi_count} pairs) all-pairs shortest road distance matrix", flush=True)
    for src, dst, dist in sample_routes:
        print(f"    {c.DIM}|-{c.RESET} Path {src} -> {dst}: {c.GREEN}{dist:.2f} km{c.RESET}", flush=True)


def log_clarke_wright_progress(
    initial_routes_count: int,
    savings_pairs_evaluated: int,
    initial_distance: float,
    optimal_dist: float,
    trucks_used: int,
) -> None:
    """Print Clarke-Wright Savings Algorithm route merging metrics."""
    c = TerminalColors
    print(f"    {c.DIM}|-{c.RESET} Initial Single-Customer Routes: {c.YELLOW}{initial_routes_count} routes ({initial_distance:.2f} km total){c.RESET}", flush=True)
    print(f"    {c.DIM}|-{c.RESET} Clarke-Wright Savings Pairs:   Evaluated {c.BRIGHT_CYAN}{savings_pairs_evaluated}{c.RESET} candidate merges & enforced capacity", flush=True)
    print(f"    {c.DIM}\\-{c.RESET} Consolidated Fleet Solution:   {c.BRIGHT_GREEN}{optimal_dist:.2f} km{c.RESET} across {c.BRIGHT_GREEN}{trucks_used} active trucks{c.RESET}", flush=True)


def log_truck_route_details(
    truck_id: str,
    truck_num: int,
    total_trucks: int,
    bins: List[str],
    collected_weight_kg: int,
    capacity_kg: int,
    utilization_pct: float,
    distance_km: float,
    stop_sequence: List[str],
    full_path_nodes: List[str],
) -> None:
    """Print detailed breakdown of an individual truck's schedule and route path."""
    c = TerminalColors
    seq_str = " -> ".join(stop_sequence)
    path_summary = f"{full_path_nodes[0]} -> ... ({len(full_path_nodes)} road waypoints) -> {full_path_nodes[-1]}"
    
    print(f"  {c.BRIGHT_CYAN}[+] [{truck_id}] (Vehicle {truck_num}/{total_trucks}){c.RESET}", flush=True)
    print(f"     * Assigned Bins ({len(bins)}):  {c.WHITE}{', '.join(bins)}{c.RESET}", flush=True)
    print(f"     * Payload Collected:    {c.BRIGHT_GREEN}{collected_weight_kg:,} kg{c.RESET} / {capacity_kg:,} kg ({c.BOLD}{utilization_pct:.1f}% capacity{c.RESET})", flush=True)
    print(f"     * Route Road Distance:  {c.BRIGHT_GREEN}{distance_km:.2f} km{c.RESET}", flush=True)
    print(f"     * Key Stop Sequence:    {c.CYAN}{seq_str}{c.RESET}", flush=True)
    print(f"     * Turn-by-Turn Path:    {c.DIM}{path_summary}{c.RESET}", flush=True)


def log_fallback_initiated(
    reason: str,
    selected_bins: int,
    total_bins: int,
    collected_weight_kg: int,
    total_waste_kg: int,
    fleet_capacity_kg: int,
    uncollected_bins_count: int,
) -> None:
    """Print visual banner when capacity fallback is triggered."""
    c = TerminalColors
    print(flush=True)
    print(f"{c.YELLOW}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"{c.YELLOW}{c.BOLD}|              [FALLBACK] CAPACITY EXCEEDED - PARTIAL COLLECTION TRIGGERED     |{c.RESET}", flush=True)
    print(f"{c.YELLOW}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"  {c.BOLD}Fallback Execution Rationale:{c.RESET}", flush=True)
    print(f"    * Trigger Reason:            {c.BRIGHT_YELLOW}{reason}{c.RESET}", flush=True)
    print(f"    * Total City Waste:          {c.BRIGHT_YELLOW}{total_waste_kg:,} kg{c.RESET} ({total_bins} bins)", flush=True)
    coverage_pct = round((collected_weight_kg / total_waste_kg) * 100.0, 1) if total_waste_kg > 0 else 100.0
    print(f"    * Scheduled for Collection:  {c.BRIGHT_GREEN}{collected_weight_kg:,} kg{c.RESET} ({selected_bins}/{total_bins} bins, {coverage_pct}% coverage)", flush=True)
    print(f"    * Deferred to Next Cycle:    {c.YELLOW}{total_waste_kg - collected_weight_kg:,} kg{c.RESET} ({uncollected_bins_count} bins)", flush=True)
    print(f"{c.YELLOW}{'-' * 79}{c.RESET}\n", flush=True)


def log_optimization_summary(
    total_distance_km: float,
    total_waste_collected_kg: int,
    total_waste_available_kg: int,
    trucks_used: int,
    total_trucks_available: int,
    execution_time_ms: float,
    peak_memory_kb: float,
    is_fallback: bool = False,
    uncollected_count: int = 0,
) -> None:
    """Print comprehensive summary box of the completed optimization."""
    c = TerminalColors
    box_color = c.YELLOW if is_fallback else c.GREEN
    status_label = "[PARTIAL SUCCESS - FALLBACK APPLIED]" if is_fallback else "[SUCCESS] OPTIMIZATION SOLUTION COMPLETE"
    
    print(flush=True)
    print(f"{box_color}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"{box_color}{c.BOLD}|{status_label.center(77)}|{c.RESET}", flush=True)
    print(f"{box_color}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"  {c.BOLD}Fleet Performance Summary:{c.RESET}", flush=True)
    print(f"    * Total Cumulative Road Distance:  {box_color}{c.BOLD}{total_distance_km:.2f} km{c.RESET}", flush=True)
    
    if is_fallback:
        coverage_pct = round((total_waste_collected_kg / total_waste_available_kg) * 100.0, 1) if total_waste_available_kg > 0 else 100.0
        print(f"    * Total Waste Collected:          {box_color}{c.BOLD}{total_waste_collected_kg:,} kg / {total_waste_available_kg:,} kg{c.RESET} ({coverage_pct}% coverage)", flush=True)
        print(f"    * Bins Deferred / Uncollected:    {c.YELLOW}{c.BOLD}{uncollected_count} bins{c.RESET} ({total_waste_available_kg - total_waste_collected_kg:,} kg deferred)", flush=True)
    else:
        print(f"    * Total Waste Collected:          {c.BRIGHT_GREEN}{c.BOLD}{total_waste_collected_kg:,} kg{c.RESET} (100% of all smart bins)", flush=True)
        
    print(f"    * Fleet Deployment:               {box_color}{c.BOLD}{trucks_used}{c.RESET} dispatched of {total_trucks_available} available", flush=True)
    print(f"    * Algorithm Execution Time:       {c.BRIGHT_CYAN}{c.BOLD}{execution_time_ms:.2f} ms{c.RESET}", flush=True)
    print(f"    * Peak Dynamic Memory Used:       {c.BRIGHT_CYAN}{c.BOLD}{peak_memory_kb:.2f} KB{c.RESET}", flush=True)
    print(f"{box_color}{'=' * 79}{c.RESET}\n", flush=True)


def log_info(msg: str) -> None:
    """Print informational log."""
    c = TerminalColors
    print(f"{c.DIM}[{_ts()}]{c.RESET} {c.BLUE}[INFO]{c.RESET} {msg}", flush=True)


def log_success(msg: str) -> None:
    """Print success log."""
    c = TerminalColors
    print(f"{c.DIM}[{_ts()}]{c.RESET} {c.GREEN}[SUCCESS]{c.RESET} {msg}", flush=True)


def log_warning(msg: str) -> None:
    """Print warning log."""
    c = TerminalColors
    print(f"{c.DIM}[{_ts()}]{c.RESET} {c.YELLOW}[WARNING]{c.RESET} {msg}", flush=True)


def log_error(title: str, detail: str = "", suggestions: Optional[List[str]] = None) -> None:
    """Print formatted error alert with suggestions."""
    c = TerminalColors
    print(flush=True)
    print(f"{c.RED}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"{c.RED}{c.BOLD}|                            [ERROR] OPTIMIZATION ERROR                       |{c.RESET}", flush=True)
    print(f"{c.RED}{c.BOLD}+-----------------------------------------------------------------------------+{c.RESET}", flush=True)
    print(f"  {c.RED}{c.BOLD}{title}{c.RESET}", flush=True)
    if detail:
        print(f"  {c.DIM}Detail: {detail}{c.RESET}", flush=True)
    if suggestions:
        print(f"\n  {c.BOLD}Recommended Action / Recovery:{c.RESET}", flush=True)
        for s in suggestions:
            print(f"    {c.BRIGHT_YELLOW}* {s}{c.RESET}", flush=True)
    print(f"{c.RED}{'=' * 79}{c.RESET}\n", flush=True)
