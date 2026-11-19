# Developer-curated Week 2 execution: Data chat handoff

Use [amendment v1](amendments/developer-curated-v1.md), not a claim of independent
human review. The original protocol, study lock, analysis plan and signed execution
mode remain intact. The comparison is unchanged. This command path records
**developer-curated, AI-assisted; no independent human review**. Hash integrity is
not independently authenticated authorship or approval.

The Data Codex chat keeps private inputs, separate keys, provenance, cross-checks,
inclusion decisions and access history in restricted storage. Shubhank Chandak
makes final inclusion decisions and must explicitly approve the exact files and
freeze after preparation is complete. This handoff does not grant that approval.
Do not send cases, keys, prompts or bundles to the implementation chat.

## 1. Pin source and install editable research dependencies

Use a fresh full clone at the amendment source commit below (a descendant changing
only tests or documentation is also acceptable).
Run each block in the same PowerShell session and stop on failure.

```powershell
$ErrorActionPreference = 'Stop'
$pin = 'adbdc5802cacdc073167d77c63a904b8b66648e6'
git clone https://github.com/Shubhank2604/ContextInvariant.git C:\Steward\ContextInvariant
if ($LASTEXITCODE) { throw 'Clone failed' }
Set-Location C:\Steward\ContextInvariant
git checkout --detach $pin
if ($LASTEXITCODE -or (git rev-parse HEAD) -ne $pin) { throw 'Wrong checkout' }
py -3.13 -m venv .venv-week2
if ($LASTEXITCODE) { throw 'Environment creation failed' }
$studyPython = Join-Path $PWD '.venv-week2\Scripts\python.exe'
& $studyPython -m pip install -c research/week1/environment-requirements.txt -e '.[research]'
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
function Study {
    & $studyPython -m context_invariant.benchmarks.week2 @args
    if ($LASTEXITCODE) { throw 'Study command failed; stop here' }
}
```

## 2. Validate privately, freeze, and prepare the pending record

Use existing restricted locations outside the checkout. Cases must use
`data_kind="developer_curated"`, `origin="authored"` or `"real_trace"`, and separate
keys with `development_only=false`. There must be 30 unique cases, ten per family
and at least 15 eligible real traces. Make any envelope changes before approving
the final bytes. Do not relabel synthetic cases as real. The private data check
below runs no selector; human approval must also address meaning and permissions.

```powershell
$cases = 'E:\PRIVATE\inputs\cases.json'
$keys = 'E:\PRIVATE\keys\keys.json'
$freeze = 'E:\PRIVATE\records\execution-freeze-v1.json'
$curation = 'E:\PRIVATE\records\curation-v1.json'
$results = 'E:\PRIVATE\results'
@'
import sys
from pathlib import Path
from context_invariant.benchmarks.week2.preflight import load_data
cases, _ = load_data(Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes(),
                     mode="developer_curated")
assert sum(c.origin == "real_trace" for c in cases) >= 15, "At least 15 real traces required"
print("Private data check passed; no selector ran")
'@ | & $studyPython - $cases $keys
if ($LASTEXITCODE) { throw 'Resolve data checks before approval' }
Study freeze --output $freeze

@'
import json, sys
from collections import Counter
from pathlib import Path
from context_invariant.benchmarks.week2.curation import AMENDMENT_PATH
from context_invariant.benchmarks.week2.preflight import canonical, json_bytes, sha
inputs, keys, freeze, output = map(Path, sys.argv[1:])
a, b, f = inputs.read_bytes(), keys.read_bytes(), freeze.read_bytes()
cases, labels, frozen = json.loads(a), json.loads(b), json.loads(f)
record = json.loads(Path("research/week2/authoring/developer-curated-template.json").read_bytes())
record.update(input_file_sha256=sha(a), key_file_sha256=sha(b),
    canonical_input_json_sha256=canonical(cases), canonical_key_json_sha256=canonical(labels),
    execution_freeze_sha256=sha(f), study_lock_sha256=frozen["study_lock_sha256"],
    analysis_plan_sha256=frozen["analysis_plan_sha256"],
    configuration_sha256=frozen["configuration_sha256"],
    amendment_sha256=frozen["files"][AMENDMENT_PATH],
    method_freeze_timestamp_utc=frozen["created_at_utc"],
    case_counts_by_family=dict(Counter(c["family"] for c in cases)),
    realistic_trace_case_ids=[c["id"] for c in cases if c["origin"] == "real_trace"])
with output.open("xb") as target:
    target.write(json_bytes(record))
print("Pending record created; NOT APPROVED; no selector ran")
'@ | & $studyPython - $cases $keys $freeze $curation
if ($LASTEXITCODE) { throw 'Pending record preparation failed' }
```

Existing files are not overwritten. Preserve earlier versions if changes are needed.
The pending template is intentionally rejected by preflight until completed.

## 3. Record the actual preparation, access history and developer approval

Complete the private curation JSON with actual `authors`, `ai_assistance` (Data
Codex preparation/cross-checks and any other assistance), `provenance_and_permissions`
and `cross_checks_and_inclusion_decisions`. Do not invent independent reviewers:
`independent_human_review=false` and `independent_human_reviewers=[]` are required.
Keep `review_arrangement` exactly as supplied in the template.

Fill `access_history` with nonempty objects containing `actor`, `action` and a
timezone-aware `at_utc`, including actual developer/Data-chat access before freezing.
Retain the full access log and any sanitization/exclusion/replacement records privately.

After Shubhank approves these exact dataset/key hashes, source/configuration freeze
and inclusion decisions, record `approval_status="approved"`,
`approved_by="Shubhank Chandak"`, the actual timezone-aware `approved_at_utc`, and
an `approval_reference` pointing to the retained human approval. Approval must
follow the freeze and recorded preapproval access events. Keep a subsequent
execution access log separately; do not rewrite the approved record after running.

No signature, reviewer credential or public-key fingerprint is required in this
mode. The runner validates the record and bindings; it cannot authenticate a human
approval or independently verify provenance. Do not change installed dependencies
or executing source after freezing. Changes to bound inputs, keys or source require
new versions, a new freeze as applicable, and renewed approval before execution.

## 4. Run preflight, execution and the read-only audit

Only after actual approval, use these commands without `--synthetic`, `--seal`,
`--signature`, `--public-key` or `--trusted-key-sha256`:

```powershell
$common = @(
    '--developer-curated', '--inputs', $cases, '--keys', $keys,
    '--freeze', $freeze, '--curation-record', $curation
)
Study preflight @common
$bundle = Study run @common --output-directory $results
$audit = (Study audit @common --bundle $bundle) | ConvertFrom-Json
if ($audit.status -ne 'passed' -or $audit.checked_evaluations -ne 180 -or
    $audit.mode -ne 'developer_curated' -or $audit.seal_verified -or
    $audit.independent_human_review -or -not $audit.developer_approval_recorded -or
    $audit.selectors_rerun) { throw 'Audit acceptance checks failed' }
$audit | ConvertTo-Json -Depth 5
```

Audit proves 180 unique case/method/budget rows, including failures; it rechecks
identity, token accounting, prompt reconstruction, failure classes and all metrics
without executing either selector. `seal_verified=false` is expected for this
unsigned arrangement. Reuse the same `audit` command and bundle to check saved
results without rerunning methods.

Keep all raw files restricted: bundles contain scoring keys, prompts and case text.
Share only nonrevealing provenance/approval summaries, hashes, audit summary and
aggregate method/budget/family results with matched-valid token/recall denominators.
Report the developer-curated arrangement and limitations in every study report.
Preserve failures and original artifacts; never retune or drop cases after outcomes.

## Synthetic verification only

Implementation-side tests use `synthetic --developer-curated` and
`preflight/run/audit --developer-curated --synthetic` with a clearly labelled
`synthetic_test_only` record. These are development copies of public pilot cases,
not independent observations, real-trace claims or Shubhank's dataset approval.
The final mode rejects their envelope and approval status. No private cases or
keys were accessed to implement or verify this amendment; no live models were called.
