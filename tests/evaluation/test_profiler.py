"""
Unit tests for SystemProfiler & StageProfiler (Phase 9).
Verifies:
1. Process memory retrieval on host.
2. Context manager stage duration tracking.
3. Query latency percentiles (cold vs warm).
4. Performance summary formatting.
"""

import time
import pytest
from backend.evaluation.profiler import (
    SystemProfiler,
    StageProfiler,
    get_current_process_memory_mb,
)


def test_get_current_process_memory():
    rss = get_current_process_memory_mb()
    assert isinstance(rss, float)
    assert rss >= 0.0


def test_stage_profiler_context_manager():
    profiler = SystemProfiler()

    with profiler.profile_stage("test_parsing"):
        time.sleep(0.01)  # sleep 10ms

    summary = profiler.get_performance_summary()
    assert "test_parsing" in summary["stages"]
    stage_data = summary["stages"]["test_parsing"]
    assert stage_data["duration_ms"] >= 5.0
    assert "memory_delta_mb" in stage_data
    assert "rss_memory_mb" in stage_data


def test_query_latency_percentiles():
    profiler = SystemProfiler()

    # Record 1 cold query and 9 warm queries
    profiler.record_query_latency(50.0, is_cold=True)
    for lat in [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]:
        profiler.record_query_latency(lat, is_cold=False)

    summary = profiler.get_performance_summary()
    query_perf = summary["query_performance"]

    assert query_perf["total_queries_profiled"] == 10
    assert query_perf["cold_start_mean_ms"] == 50.0
    assert 13.0 <= query_perf["warm_start_mean_ms"] <= 15.0
    assert query_perf["p50_latency_ms"] > 0
    assert query_perf["p95_latency_ms"] >= query_perf["p50_latency_ms"]
    assert query_perf["p99_latency_ms"] >= query_perf["p95_latency_ms"]
    assert summary["hardware_environment"]["system"] == "HP Victus"
