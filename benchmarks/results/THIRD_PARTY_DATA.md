# Third-party benchmark data

The retained model-backed LongBench evidence bundle contains a normalized 100-case subset in
`20261002T021250.312800Z-comparison-standard/cases.jsonl`. Those case records are research inputs
derived from LongBench and its upstream datasets; they are not relicensed under the ContextOS
MIT license. The bundle is retained unchanged so that the published aggregate results remain
auditable.

The subset contains 25 records from each of these LongBench tasks:

| Task | Upstream material | Applicable notice |
|---|---|---|
| `hotpotqa` | HotpotQA development data | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); attribution to the HotpotQA authors and project |
| `2wikimqa` | 2WikiMultihopQA development data | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0); attribution to the 2WikiMultihopQA authors and project |
| `passage_retrieval_en` | English Wikipedia passages assembled and summarized by LongBench | Wikipedia text is [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); LongBench's assembly is covered by its repository license |
| `repobench-p` | RepoBench-P code-completion data adapted by LongBench | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); attribution to the RepoBench authors and project |

ContextOS sampled, normalized, and serialized these records for its evaluation; the records may
therefore differ in format from the upstream distributions. No claim of endorsement by any
upstream author or project is made.

Sources and citations:

- [LongBench repository and MIT license](https://github.com/THUDM/LongBench)
- [LongBench dataset card and task construction](https://huggingface.co/datasets/zai-org/LongBench)
- [HotpotQA project and dataset license](https://github.com/hotpotqa/hotpot)
- [2WikiMultihopQA project and license](https://github.com/Alab-NII/2wikimultihop)
- [RepoBench project and license](https://github.com/Leolty/repobench)

When redistributing or adapting the retained case records, follow the applicable upstream
license and attribution requirements. The metrics, reports, configuration, telemetry, and
ContextOS-authored benchmark code remain covered by the repository's own licensing terms.
