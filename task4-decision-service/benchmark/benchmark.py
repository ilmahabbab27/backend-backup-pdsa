"""Experimental evaluation for Task 4 ranking algorithms.

Measures execution time and scalability of the three techniques
(linear_search, weighted_ranking, heuristic_scoring) as the number of
candidate facilities grows.

For each dataset size we:
  1. generate N synthetic facilities with random but realistic attributes,
  2. run each algorithm REPEATS times and take the best (minimum) time
     to reduce noise from the operating system,
  3. record the per-run time in milliseconds.

The "recommendation" step in the real service also sorts the scored
candidates to produce a ranking, so we measure score + sort together as
"rank time" as well as the raw scoring time. This gives an honest picture:
scoring is O(n), while producing a full ranking is O(n log n).

Outputs:
  - results.csv : the raw measurements (size, algorithm, scoring_ms, rank_ms)
  - scoring_time.png, rank_time.png : line charts of time vs. size

Run:
    python benchmark.py
"""
from __future__ import annotations

import csv
import random
import time
from pathlib import Path

# Import the real algorithms from the app so we benchmark production code,
# not a re-implementation. This file lives in task4-decision-service/benchmark,
# so we add the parent directory to the path.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.algorithms import ranking  # noqa: E402

# Dataset sizes to test. Small sizes reflect the real city; large sizes
# demonstrate scalability well beyond it.
SIZES = [10, 100, 1_000, 5_000, 10_000, 50_000, 100_000]

# How many times to run each measurement; we keep the fastest to cut noise.
REPEATS = 5

WEIGHTS = {"distance": 0.6, "capacity": 0.2, "availability": 0.2}


def make_candidates(n: int) -> list[dict]:
    """Create n synthetic facilities with realistic attribute ranges."""
    rng = random.Random(42)  # fixed seed => reproducible datasets
    candidates = []
    for i in range(n):
        capacity = rng.randint(20, 500)
        current_load = rng.randint(0, capacity)
        candidates.append(
            {
                "location_key": f"loc-{i}",
                "name": f"Facility {i}",
                "facility_type": "hospital",
                "distance_km": round(rng.uniform(0.1, 25.0), 3),
                "capacity": capacity,
                "current_load": current_load,
                "availability": capacity - current_load,
            }
        )
    return candidates


def time_algorithm(func, candidates: list[dict], *, sort: bool) -> float:
    """Return the best time (ms) to run func over a fresh copy of candidates.

    A fresh copy is used each run because the algorithms mutate the list
    (they add a 'score' key), and we do not want ordering effects to carry
    between runs.
    """
    best = float("inf")
    for _ in range(REPEATS):
        data = [dict(c) for c in candidates]  # independent copy
        start = time.perf_counter()
        scored = func(data)
        if sort:
            scored.sort(key=lambda c: (-c["score"], c["distance_km"]))
        elapsed = (time.perf_counter() - start) * 1000.0  # ms
        best = min(best, elapsed)
    return best


def run() -> list[dict]:
    """Run the full benchmark and return a list of result rows."""
    rows: list[dict] = []
    for size in SIZES:
        candidates = make_candidates(size)

        algorithms = {
            "linear_search": lambda d: ranking.linear_search(d),
            "weighted_ranking": lambda d: ranking.weighted_ranking(d, WEIGHTS),
            "heuristic_scoring": lambda d: ranking.heuristic_scoring(d),
        }

        for name, func in algorithms.items():
            scoring_ms = time_algorithm(func, candidates, sort=False)
            rank_ms = time_algorithm(func, candidates, sort=True)
            rows.append(
                {
                    "size": size,
                    "algorithm": name,
                    "scoring_ms": round(scoring_ms, 4),
                    "rank_ms": round(rank_ms, 4),
                }
            )
            print(
                f"n={size:>7} {name:<18} "
                f"scoring={scoring_ms:8.4f} ms  rank={rank_ms:8.4f} ms"
            )
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    """Write results to a CSV file."""
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["size", "algorithm", "scoring_ms", "rank_ms"]
        )
        writer.writeheader()
        writer.writerows(rows)


def make_charts(rows: list[dict], out_dir: Path) -> None:
    """Create line charts of time vs. dataset size (log-log axes).

    Skipped gracefully if matplotlib is not installed.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping charts (CSV still written).")
        return

    algorithms = sorted({r["algorithm"] for r in rows})

    for metric, title, filename in [
        ("scoring_ms", "Scoring time vs. number of facilities", "scoring_time.png"),
        ("rank_ms", "Ranking time (score + sort) vs. number of facilities", "rank_time.png"),
    ]:
        plt.figure(figsize=(8, 5))
        for algo in algorithms:
            sizes = [r["size"] for r in rows if r["algorithm"] == algo]
            times = [r[metric] for r in rows if r["algorithm"] == algo]
            plt.plot(sizes, times, marker="o", label=algo)
        plt.xscale("log")
        plt.yscale("log")
        plt.xlabel("Number of facilities (n)")
        plt.ylabel("Time (ms)")
        plt.title(title)
        plt.legend()
        plt.grid(True, which="both", linestyle="--", alpha=0.4)
        plt.tight_layout()
        plt.savefig(out_dir / filename, dpi=120)
        plt.close()
        print(f"wrote {filename}")


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    print(f"Running benchmark ({REPEATS} repeats per measurement)...\n")
    rows = run()
    write_csv(rows, out_dir / "results.csv")
    print("\nwrote results.csv")
    make_charts(rows, out_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
