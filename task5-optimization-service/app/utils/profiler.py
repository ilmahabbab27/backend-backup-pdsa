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
        self._was_tracing: bool = False

    def __enter__(self) -> "Profiler":
        self._was_tracing = tracemalloc.is_tracing()
        if not self._was_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        self.start_ns = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.end_ns = time.perf_counter_ns()
        _, peak_bytes = tracemalloc.get_traced_memory()
        if not self._was_tracing:
            tracemalloc.stop()

        self.execution_time_ms = round((self.end_ns - self.start_ns) / 1_000_000.0, 4)
        self.peak_memory_kb = round(peak_bytes / 1024.0, 2)
