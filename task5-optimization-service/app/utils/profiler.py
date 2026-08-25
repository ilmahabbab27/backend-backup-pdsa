"""Performance profiling utilities for execution time and memory monitoring."""

import time
import tracemalloc
from types import TracebackType
from typing import Optional, Type


class Profiler:
    """Context manager measuring wall-clock execution time and peak heap memory usage."""

    def __init__(self) -> None:
        self.start_ns: int = 0
        self.end_ns: int = 0
        self.execution_time_ms: float = 0.0
        self.peak_memory_kb: float = 0.0
        self._initial_peak: int = 0

    def __enter__(self) -> "Profiler":
        self.start_ns = time.perf_counter_ns()
        if tracemalloc.is_tracing():
            _, peak_bytes = tracemalloc.get_traced_memory()
            self._initial_peak = peak_bytes
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.end_ns = time.perf_counter_ns()
        self.execution_time_ms = round((self.end_ns - self.start_ns) / 1_000_000.0, 4)

        if tracemalloc.is_tracing():
            _, peak_bytes = tracemalloc.get_traced_memory()
            delta = max(0, peak_bytes - self._initial_peak)
            self.peak_memory_kb = round(delta / 1024.0, 2)
        else:
            self.peak_memory_kb = 0.0
