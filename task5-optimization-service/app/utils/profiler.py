"""Performance profiling utilities for execution time and memory monitoring."""

import time
import tracemalloc
from types import TracebackType
from typing import Optional, Type


class Profiler:
    """Context manager measuring wall-clock execution time and peak heap memory usage."""

    def __init__(self, trace_memory: bool = True) -> None:
        self.trace_memory = trace_memory
        self.start_ns: int = 0
        self.end_ns: int = 0
        self.execution_time_ms: float = 0.0
        self.peak_memory_kb: float = 0.0
        self._initial_peak: int = 0
        self._started_tracemalloc: bool = False

    def __enter__(self) -> "Profiler":
        self.start_ns = time.perf_counter_ns()
        if self.trace_memory:
            if not tracemalloc.is_tracing():
                try:
                    tracemalloc.start()
                    self._started_tracemalloc = True
                except Exception:
                    pass
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

        if self.trace_memory and tracemalloc.is_tracing():
            try:
                _, peak_bytes = tracemalloc.get_traced_memory()
                delta = max(0, peak_bytes - self._initial_peak)
                # If delta is 0 but peak is non-zero, report peak_bytes
                mem_bytes = delta if delta > 0 else peak_bytes
                self.peak_memory_kb = round(mem_bytes / 1024.0, 2)
            except Exception:
                self.peak_memory_kb = 0.0
            finally:
                if self._started_tracemalloc:
                    try:
                        tracemalloc.stop()
                    except Exception:
                        pass
        else:
            self.peak_memory_kb = 0.0

