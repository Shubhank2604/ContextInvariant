# Known limitations

- The 90-case constraint benchmark is a controlled development set that co-evolved with the
  Phase 5 implementation. Its strong result requires confirmation on a newly authored,
  frozen held-out set before it becomes a paper-level generalization claim.
- At an 80% budget, Full Phase 5 explicitly rejects all ten multi-hop cases because their
  protected closure cannot fit. It preserves every required value on the 80 feasible cases,
  but reliability is obtained partly by trading coverage for safe failure.
- The retained LongBench evaluation covers 100 examples from four tasks and one OpenAI model
  snapshot. Results are mixed: Phase 5 significantly trails Full Context on HotpotQA and does
  not consistently outperform frozen v0.4.
- Both model-backed constraint evaluations use snapshots from the same OpenAI model family.
  Cross-provider or open-weight validation has not been performed.
- The real-provider positional benchmark reaches 100% exact match for every strategy,
  position, and 4K-32K context length. This ceiling effect does not reproduce or measure a
  mitigation of the degradation reported in *Lost in the Middle*.
- The cumulative Phase 5 variants tie at the primary feasible budget points, so the current
  ablation does not isolate a causal contribution for each individual mechanism.
- Controlled constraint runs measure approximately 4-6 ms p95 optimizer overhead locally,
  whereas LongBench p95 ranges from approximately 188-325 ms because of longer inputs and
  embedding/deduplication work. No universal sub-10-ms claim is valid.
- LongBench contains two legitimate Full Context RepoBench-P overflows. Failed or infeasible
  cases remain raw and are not assigned invented quality scores.
- The deterministic local embedding provider supports reproducibility, not a semantic-quality
  claim. Sentence-transformer embeddings require the optional `semantic` dependency and may
  download model weights.
- LLM summarization is lossy, disabled by default, and requires an explicitly injected
  provider. Protected system, tool-definition, code, mandatory, non-compressible,
  identifier-bearing, and secret-like content is rejected.
- The allocator is deterministic and auditable but is not claimed to be globally optimal.
- SQLite is the only durable backend; distributed stores and vector databases are outside the
  current scope.
- ContextOS constructs input context. It does not verify model answers, provide prompt-injection
  security, or guarantee that a downstream model will follow retained instructions.

See the [v0.5.0 research-readiness report](../benchmarks/reports/v0.5.0-research-readiness.md)
for the complete evidence interpretation and paper-validation requirements.
