# Type-aware transformations

Phase 5E replaces the executor's broad prose-versus-tool split with `TypeAwareCompressor`. The existing `CompressionExecutor` still owns reservation reuse, budget accounting, error isolation, and result validation; the router only selects a transformation family.

| Context type | Initial transformation policy |
|---|---|
| System instruction | Lossless/no-op only |
| Tool definition | Lossless/no-op only |
| Code | Conservative exact-line extraction |
| Tool output and error | Structured JSON pruning or line-aware log extraction |
| Task state | Structured JSON pruning only |
| Retrieved document | Verbatim sentence extraction with source-item provenance |
| User/assistant message and memory | Verbatim sentence extraction |
| Decision and plan | Verbatim sentence extraction |

Mandatory and explicitly non-compressible items remain lossless regardless of type.

## Structured data

`StructuredDataCompressor` accepts JSON objects and retains complete values for selected top-level keys. It ranks:

1. contract-required keys;
2. keys named by the task;
3. operational keys such as `status`, `state`, `id`, `error`, `code`, `result`, `message`, and `timestamp`;
4. remaining keys deterministically.

Missing required keys and required fields that cannot fit are explicit failures. Arrays, scalar JSON roots, malformed JSON, and natural-language task state are not rewritten into guessed structure. Nested values are retained whole; nested-path pruning is not implemented.

## Code

`CodeCompressor` removes full-line comments first, then prioritizes exact source lines containing imports, declarations, return/raise/throw statements, and task-referenced symbols. It does not use prose summarization, rewrite identifiers, or claim that the resulting snippet is independently executable. It is intentionally a small conservative transformation rather than a multi-language AST platform.

## Evidence and conversation

Retrieved evidence and conversational text remain extractive: selected sentences are copied verbatim and restored to source order. Evidence results use the `evidence_extractive` strategy label and preserve source-item provenance.

The existing optional LLM summarizer remains available as an explicitly injected component, but Phase 5E does not make it a default transformation.

## Contract boundary

Before Phase 5F, items requiring numeric, date, identifier, citation, or negation preservation are routed losslessly. Structured-key-only contracts may use structured pruning because required keys and their complete values are checked directly. Phase 5F adds reusable feature validators, fallback sequencing, and detailed validation traces.
