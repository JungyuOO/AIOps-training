# Dataset Summary

Version: `v2.0`

This repository contains broad-domain OpenShift AIOps SFT datasets for training, validation, and holdout evaluation.

The `category` field is intentionally broad. Specific failure modes are tracked in `expected_cause`, so one category does not collapse into thousands of near-identical endpoint, Secret, PVC, GPU, or OLM cases.

## Counts

| Split | File | Samples | Format |
|---|---|---:|---|
| Train | `data/curated/train.full.jsonl` | 10,000 | metadata + messages |
| Eval | `data/curated/eval.full.jsonl` | 1,111 | metadata + messages |
| Gold | `data/curated/gold.full.jsonl` | 150 | metadata + messages |
| Train export | `data/curated/aiops_train.jsonl` | 10,000 | messages only |
| Eval export | `data/curated/aiops_eval.jsonl` | 1,111 | messages only |
| Gold export | `data/curated/aiops_gold.jsonl` | 150 | messages only |

Compatibility aliases are also kept as `train.jsonl`, `eval.jsonl`, and `gold.jsonl`.

## Broad Categories

| Category | Train | Eval | Gold | Scope |
|---|---:|---:|---:|---|
| `application_connectivity` | 2,000 | 222 | 30 | Route, Service, EndpointSlice, readiness, TLS, DNS, NetworkPolicy, traffic split |
| `configuration_identity` | 2,000 | 222 | 30 | Secret, ConfigMap, ServiceAccount, RBAC, imagePullSecret, S3 credentials, OAuth refs |
| `storage_data_artifacts` | 2,000 | 222 | 30 | PVC/PV, StorageClass, MinIO/S3, model artifacts, object size, CA bundle, upload integrity |
| `accelerator_serving_runtime` | 2,000 | 222 | 30 | GPU scheduling, Workbench contention, device plugin, CUDA, vLLM, KServe runtime |
| `platform_lifecycle_capacity` | 2,000 | 223 | 30 | OLM, DSC/DSCI, Knative, Authorino, quota, LimitRange, cleanup candidates |

## Quality Gates

- JSONL parse and required metadata validation are enforced by `scripts/validate_jsonl.py`.
- Assistant output must include `[진단]`, `[근거]`, `[확인 명령어]`, `[조치 방향]`, `[주의사항]`, and `[추가 확인질문]`.
- Namespaced `oc` verification commands must include namespace flags. Cluster-scoped or all-namespace checks are allowed.
- Normalized duplicate detection strips split ids, namespace sequence ids, case ids, and digits before comparing question-answer pairs.
- A dataset fails validation when a normalized question-answer pair appears more than 3 times or when the unique normalized pair ratio is below 0.95.
- Training exports remove metadata and keep only `messages`.

## Current Verification

- Raw validation: 11,261 valid, 0 warnings, 0 errors, unique normalized pair ratio 1.0000.
- Curated validation: 11,261 valid, 0 warnings, 0 errors, unique normalized pair ratio 1.0000.
- Diversity audit: train has 10,000 unique questions, 10,000 unique answers, and 10,000 unique question-answer pairs.
- Scoring: 11,261 Gold-or-better samples by the rule-based scorer, 0 Fail samples.

## Workbench Files

Copy these files into the Workbench data directory:

```text
data/curated/aiops_train.jsonl -> ~/aiops-gemma3/data/aiops_train.jsonl
data/curated/aiops_eval.jsonl  -> ~/aiops-gemma3/data/aiops_eval.jsonl
data/curated/aiops_gold.jsonl  -> ~/aiops-gemma3/data/aiops_gold.jsonl
```
