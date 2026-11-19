# Testable offline coding replay

This is one scripted agent workflow with real, locally captured test output. It is
not a live model trajectory. `inputs/task-test-capture.json` contains stdout and exit
status from the buggy candidate and a separately identified reference patch.

The task is to fix `should_retry(status_code, attempts_made, retry_limit=2)` while
preserving its signature: retry only 503, honor the current attempt limit, reject
negative attempts, and never retry 429. The oracle contains 12 behavior checks.
The original implementation fails; the reference passes. Neither result measures
what a model would produce from a selected context.

The three chronological checkpoints are:

1. Investigate the original request, source, and captured failing test result.
2. A new tool configuration changes retry_limit from 1 to 2. The new record supersedes
   the old one. The follow-up requires both current state and the original request.
3. Finish the patch using the earlier failure and original no-429 rule. This explicitly
   tests retention of an earlier supporting record after later state changes.

Each checkpoint is compared at 80% of its original record tokens. A fourth, clearly
marked stress probe adds a required lossless test transcript and removes unrelated
tool output. It is a budget probe of checkpoint three, not another observed agent turn.
Its certificate establishes that no legal lossless required context fits.

The replay bundle saves each method's exact model-facing prompt in its raw prediction
row, along with record tokens and full rendered-prompt tokens. These are different
quantities. No prompt is emitted for no-context outcomes. The shared evaluator and
focused tests distinguish returned context missing a requirement (`invalid_context`)
from an explicit certified overflow (`no_context`, `budget_infeasible`).

From the repository root, after the installation in `../README.md`:

```powershell
python scripts/build_week1_replay.py
python -m context_invariant.benchmarks.week1.runner --inputs research/week1/inputs/replay.json --checklists research/week1/inputs/replay-checklists.json --output-directory out/week1-replay --replay
python research/week1/workflow/task/check_task.py research/week1/workflow/task/retry.py
python research/week1/workflow/task/check_task.py research/week1/workflow/task/reference_retry.py
```

The first oracle command intentionally exits 1; the reference command exits 0.
The generator is for intentional fixture regeneration, not required for reproduction
from already saved inputs.

For a later live evaluation, create a fresh isolated copy of the buggy task for each
method/replicate, give the same fixed model snapshot the saved prompt at each checkpoint,
and allow the same edit/test tool budget. Keep the oracle and reference patch out of
the prompt. Record every tool call, patch, model usage, errors, seed/decoding settings,
and elapsed time. Apply the returned patch, run all 12 checks, and verify the function
signature and allowed edit scope. End-to-end success requires all checks to pass with
no interface regression. A missing patch, provider error, invalid context, explicit
overflow, or failing oracle is not success; retain its distinct reason and denominator.
Counterbalance method order and report matched-completion quality separately from
all-attempt success. Reserve additional independently authored tests before the live
study; these 12 development tests must not become the sole final held-out oracle.

No live smoke test was performed: this session established no selected model snapshot
or configured, authorized provider execution. The offline replay is the deliverable.
