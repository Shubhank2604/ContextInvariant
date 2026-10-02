# LongBench Subset Report

- Provider/model: `openai/gpt-5.4-mini-2026-03-17`
- Profile: `standard`
- Cases: 100
- Predictions: 300

| Dataset | Strategy | Metric | Successful | Mean score | Quality retention |
|---|---|---|---:|---:|---:|
| 2wikimqa | full_context | qa_f1 | 25/25 | 0.5844444444444444 | 1.0 |
| 2wikimqa | phase5_full | qa_f1 | 25/25 | 0.6604444444444444 | 1.0176470588235293 |
| 2wikimqa | phase5_v040 | qa_f1 | 25/25 | 0.6284444444444445 | 0.9235294117647059 |
| hotpotqa | full_context | qa_f1 | 25/25 | 0.7469523809523809 | 1.0 |
| hotpotqa | phase5_full | qa_f1 | 25/25 | 0.5716190476190476 | 0.7619047619047619 |
| hotpotqa | phase5_v040 | qa_f1 | 25/25 | 0.6430476190476191 | 0.8469387755102041 |
| passage_retrieval_en | full_context | retrieval | 25/25 | 1.0 | 1.0 |
| passage_retrieval_en | phase5_full | retrieval | 25/25 | 0.88 | 0.88 |
| passage_retrieval_en | phase5_v040 | retrieval | 25/25 | 0.84 | 0.84 |
| repobench-p | full_context | code_similarity | 23/25 | 0.05782608695652174 | 1.0 |
| repobench-p | phase5_full | code_similarity | 25/25 | 0.0592 | 0.23669467787114848 |
| repobench-p | phase5_v040 | code_similarity | 25/25 | 0.046 | 0.35112044817927174 |

## Runtime performance

Observed process peak resident memory: 195465216 bytes. It is process-wide and must not be attributed to an individual strategy.

| Dataset | Strategy | Mean input | Optimizer total ms | p50 ms | p95 ms | Embedding ms | Compression ms | Provider total ms | Output tokens | Cached tokens | Estimated cost USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2wikimqa | full_context | 7144.8 | 171.82420002063736 | 6.962799991015345 | 11.370019993046297 | 0.0 | 0.0 | 49995.83769997116 | 203 | 13824 | 0.1243488 |
| 2wikimqa | phase5_full | 6210.56 | 2494.1329000575934 | 85.68150000064634 | 239.3034800072198 | 72.21059199888259 | 1.0532600025180727 | 48058.319100004155 | 218 | 143360 | 0.0197535 |
| 2wikimqa | phase5_v040 | 6210.76 | 1984.1068000532687 | 67.99999999930151 | 164.62685999576928 | 64.04160000383854 | 0.7747120026033372 | 46070.87850003154 | 209 | 13824 | 0.10715805 |
| hotpotqa | full_context | 12323.52 | 271.9198999402579 | 9.726499993121251 | 19.85640000202693 | 0.0 | 0.0 | 45060.73489997652 | 193 | 31232 | 0.2085084 |
| hotpotqa | phase5_full | 7656.84 | 4652.562900038902 | 210.06159999524243 | 325.0535999948624 | 145.0865959969815 | 1.2609239993616939 | 47039.19780001161 | 181 | 178432 | 0.0232569 |
| hotpotqa | phase5_v040 | 7656.12 | 4230.73009995278 | 180.52550000720657 | 260.0642799923662 | 141.9054120022338 | 1.5335959999356419 | 43952.95609999448 | 192 | 14848 | 0.1337151 |
| passage_retrieval_en | full_context | 12645.12 | 145.3046000970062 | 4.508700018050149 | 8.679280010983346 | 0.0 | 0.0 | 105717.03369999886 | 175 | 12544 | 0.23119155 |
| passage_retrieval_en | phase5_full | 7930.4 | 3925.2406999876257 | 152.0524000225123 | 268.546839983901 | 119.97430400573649 | 2.1706680033821613 | 61438.999800011516 | 175 | 133120 | 0.06280575 |
| passage_retrieval_en | phase5_v040 | 7929.64 | 2596.1703000066336 | 78.09270001598634 | 222.93533998890774 | 85.5732800019905 | 1.7822160001378506 | 91605.03950004932 | 175 | 61440 | 0.11119425 |
| repobench-p | full_context | 8791.391304347826 | 90.53699995274656 | 3.240999998524785 | 8.75850000884384 | 0.0 | 0.0 | 122887.63569996809 | 1469 | 24064 | 0.16063305 |
| repobench-p | phase5_full | 6345.08 | 1531.842800002778 | 41.820499987807125 | 187.94609999749787 | 43.06122799986042 | 0.3010960016399622 | 56969.73730021273 | 1600 | 171264 | 0.0311973 |
| repobench-p | phase5_v040 | 6316.68 | 1429.9729999911506 | 41.947800025809556 | 178.42863998375813 | 44.30376800009981 | 0.6558440008666366 | 48347.256999928504 | 1600 | 17920 | 0.1341555 |

## Paired score deltas

Candidate minus reference; confidence intervals require 20 paired cases.

| Dataset | Reference | Candidate | Cases | Mean delta | 95% CI |
|---|---|---|---:|---:|---|
| 2wikimqa | full_context | phase5_full | 25 | 0.0760 | [-0.0360, 0.2000] |
| 2wikimqa | full_context | phase5_v040 | 25 | 0.0440 | [-0.0600, 0.1721] |
| 2wikimqa | phase5_v040 | phase5_full | 25 | 0.0320 | [0.0000, 0.0960] |
| hotpotqa | full_context | phase5_full | 25 | -0.1753 | [-0.3400, -0.0386] |
| hotpotqa | full_context | phase5_v040 | 25 | -0.1039 | [-0.2371, 0.0067] |
| hotpotqa | phase5_v040 | phase5_full | 25 | -0.0714 | [-0.2000, 0.0171] |
| passage_retrieval_en | full_context | phase5_full | 25 | -0.1200 | [-0.2410, 0.0000] |
| passage_retrieval_en | full_context | phase5_v040 | 25 | -0.1600 | [-0.3200, -0.0400] |
| passage_retrieval_en | phase5_v040 | phase5_full | 25 | 0.0400 | [-0.0800, 0.1600] |
| repobench-p | full_context | phase5_full | 23 | 0.0026 | [-0.0509, 0.0574] |
| repobench-p | full_context | phase5_v040 | 23 | -0.0135 | [-0.0600, 0.0296] |
| repobench-p | phase5_v040 | phase5_full | 25 | 0.0132 | [-0.0072, 0.0360] |

Raw `cases.jsonl` and `predictions.jsonl` are authoritative; this report is derived.
