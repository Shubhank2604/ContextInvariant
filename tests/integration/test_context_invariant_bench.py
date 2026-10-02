"""End-to-end Phase 4A benchmark execution."""

from pathlib import Path

from context_invariant.benchmarks.artifacts import load_dataset
from context_invariant.benchmarks.runner import run_context_invariant_bench
from context_invariant.tokenization import TiktokenTokenizer


def test_all_fifty_base_cases_produce_raw_results_and_confidence_intervals() -> None:
    dataset = load_dataset(Path("benchmarks/datasets/context_invariant_bench.json"))
    run = run_context_invariant_bench(dataset, tokenizer=TiktokenTokenizer())

    assert run.metadata["case_count"] == 50
    assert run.metadata["base_case_count"] == 50
    assert len(run.measurements) == 300
    assert len(run.aggregates) == 6
    assert all(aggregate.case_count == 50 for aggregate in run.aggregates)
    assert all(aggregate.task_score_ci95 is not None for aggregate in run.aggregates)
    assert all(aggregate.cir_ci95 is not None for aggregate in run.aggregates)
    assert all(aggregate.total_optimizer_wall_time_ms > 0.0 for aggregate in run.aggregates)
    assert all(aggregate.p50_optimizer_latency_ms > 0.0 for aggregate in run.aggregates)
    assert all(aggregate.p95_optimizer_latency_ms > 0.0 for aggregate in run.aggregates)
    assert all(aggregate.mean_embedding_time_ms >= 0.0 for aggregate in run.aggregates)
    assert all(aggregate.mean_compression_time_ms >= 0.0 for aggregate in run.aggregates)
    assert run.peak_process_memory_bytes is not None and run.peak_process_memory_bytes > 0
    assert len(run.paired_comparisons) == 27
    assert all(comparison.case_count == 50 for comparison in run.paired_comparisons)
    assert all(comparison.delta_ci95 is not None for comparison in run.paired_comparisons)
    assert {
        comparison.reference_strategy
        for comparison in run.paired_comparisons
        if comparison.candidate_strategy == "context_invariant"
    } == {
        "full_context",
        "last_n",
        "naive_extractive",
        "relevance_only",
        "sliding_window",
    }
    context_invariant = next(
        aggregate for aggregate in run.aggregates if aggregate.strategy == "context_invariant"
    )
    assert context_invariant.successful_case_count == 50
    assert context_invariant.mean_task_specific_score >= 0.0
    assert context_invariant.mean_critical_information_recall >= 0.0
