"""
System Profiler & Performance Benchmarking Engine (Phase 9).
Measures duration and memory consumption across all 11 indexing and query pipeline stages:
1. Repository cloning
2. File discovery and filtering
3. Tree-sitter parsing
4. Code chunk generation
5. Embedding generation
6. ChromaDB vector indexing
7. SQLite FTS5 keyword indexing
8. NetworkX knowledge graph construction
9. Hybrid retrieval
10. Context assembly
11. Gemini generation (when enabled)
Tracks cold-start vs warm-start query latency, p50/p95/p99 percentiles, and hardware memory.
"""

import os
import sys
import time
import ctypes
from typing import Dict, Any, List, Optional
from backend.evaluation.metrics import calculate_percentile


def get_current_process_memory_mb() -> float:
    """Retrieves current process working set memory (RSS) in megabytes."""
    try:
        if sys.platform == "win32":
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.c_ulong),
                    ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


class StageProfiler:
    """Context manager for timing individual pipeline stages and tracking memory changes."""

    def __init__(self, stage_name: str, profiler: 'SystemProfiler'):
        self.stage_name = stage_name
        self.profiler = profiler
        self.start_time: float = 0.0
        self.start_mem: float = 0.0

    def __enter__(self):
        self.start_mem = get_current_process_memory_mb()
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        end_mem = get_current_process_memory_mb()
        self.profiler.record_stage(
            stage=self.stage_name,
            duration_ms=round(duration_ms, 2),
            mem_delta_mb=round(end_mem - self.start_mem, 2),
            final_mem_mb=end_mem,
        )


class SystemProfiler:
    """
    Coordinates end-to-end latency profiling, stage breakdown, and memory tracking.
    """

    def __init__(self):
        self.stage_timings: Dict[str, Dict[str, float]] = {}
        self.cold_start_latencies: List[float] = []
        self.warm_start_latencies: List[float] = []

    def profile_stage(self, stage_name: str) -> StageProfiler:
        return StageProfiler(stage_name, self)

    def record_stage(
        self, stage: str, duration_ms: float, mem_delta_mb: float, final_mem_mb: float
    ):
        self.stage_timings[stage] = {
            "duration_ms": duration_ms,
            "memory_delta_mb": mem_delta_mb,
            "rss_memory_mb": final_mem_mb,
        }

    def record_query_latency(self, latency_ms: float, is_cold: bool = False):
        if is_cold:
            self.cold_start_latencies.append(latency_ms)
        else:
            self.warm_start_latencies.append(latency_ms)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Aggregates end-to-end performance metrics."""
        total_indexing_ms = sum(
            data["duration_ms"] for stage, data in self.stage_timings.items()
            if "query" not in stage and "retrieval" not in stage
        )

        all_query_latencies = self.cold_start_latencies + self.warm_start_latencies
        p50 = calculate_percentile(all_query_latencies, 50) if all_query_latencies else 0.0
        p95 = calculate_percentile(all_query_latencies, 95) if all_query_latencies else 0.0
        p99 = calculate_percentile(all_query_latencies, 99) if all_query_latencies else 0.0
        mean_query = sum(all_query_latencies) / len(all_query_latencies) if all_query_latencies else 0.0

        current_mem = get_current_process_memory_mb()

        return {
            "hardware_environment": {
                "system": "HP Victus",
                "cpu_mode": True,
                "ram_total_gb": 24,
                "gpu_detected": "NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)",
                "python_version": sys.version.split()[0],
            },
            "total_indexing_duration_ms": round(total_indexing_ms, 2),
            "stages": self.stage_timings,
            "query_performance": {
                "total_queries_profiled": len(all_query_latencies),
                "cold_start_mean_ms": round(sum(self.cold_start_latencies) / len(self.cold_start_latencies), 2) if self.cold_start_latencies else 0.0,
                "warm_start_mean_ms": round(sum(self.warm_start_latencies) / len(self.warm_start_latencies), 2) if self.warm_start_latencies else 0.0,
                "overall_mean_ms": round(mean_query, 2),
                "p50_latency_ms": round(p50, 2),
                "p95_latency_ms": round(p95, 2),
                "p99_latency_ms": round(p99, 2),
            },
            "current_process_rss_mb": current_mem,
        }


system_profiler = SystemProfiler()

