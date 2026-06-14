# OpenShift AIOps SFT Dataset

This repository manages a Korean OpenShift AIOps SFT dataset and the validation/training notebook pipeline for a Gemma3 12B LoRA adapter.

The repository is for dataset generation, validation, scoring, export, and notebook preparation. Actual model training runs in the OpenShift AI Jupyter Workbench.

## Current Dataset

Version: `v2.0`

| Split | File | Samples | Use |
|---|---|---:|---|
| Train | `data/curated/aiops_train.jsonl` | 10,000 | SFT training |
| Eval | `data/curated/aiops_eval.jsonl` | 1,111 | Eval loss during training |
| Gold | `data/curated/aiops_gold.jsonl` | 150 | Holdout final evaluation only |

Metadata-preserving files are also kept:

| Split | File |
|---|---|
| Train full | `data/curated/train.full.jsonl` |
| Eval full | `data/curated/eval.full.jsonl` |
| Gold full | `data/curated/gold.full.jsonl` |

Compatibility aliases exist as `train.jsonl`, `eval.jsonl`, and `gold.jsonl`, but the Workbench-facing canonical names are `aiops_train.jsonl`, `aiops_eval.jsonl`, and `aiops_gold.jsonl`.

## Workbench Copy Paths

Copy these files into the Workbench:

```text
data/curated/aiops_train.jsonl -> ~/aiops-gemma3/data/aiops_train.jsonl
data/curated/aiops_eval.jsonl  -> ~/aiops-gemma3/data/aiops_eval.jsonl
data/curated/aiops_gold.jsonl  -> ~/aiops-gemma3/data/aiops_gold.jsonl
notebooks/aiops_training.ipynb -> Workbench notebook
```

`gold` must not be used for training. Use it only after training for holdout comparison and sample output review.

## Broad Categories

The dataset now uses broad operational domains in `category`. Concrete failure modes are stored in `expected_cause`.

| Category | Scope |
|---|---|
| `application_connectivity` | Route, Service, EndpointSlice, readiness, TLS, DNS, NetworkPolicy, traffic split |
| `configuration_identity` | Secret, ConfigMap, ServiceAccount, RBAC, imagePullSecret, S3 credentials, OAuth refs |
| `storage_data_artifacts` | PVC/PV, StorageClass, MinIO/S3, model artifacts, object size, CA bundle, upload integrity |
| `accelerator_serving_runtime` | GPU scheduling, Workbench contention, device plugin, CUDA, vLLM, KServe runtime |
| `platform_lifecycle_capacity` | OLM, DSC/DSCI, Knative, Authorino, quota, LimitRange, cleanup candidates |

This avoids creating thousands of nearly identical endpoint-only or Secret-only samples.

## Sample Format

Full records include metadata:

```json
{
  "id": "train-application_connectivity-00001",
  "category": "application_connectivity",
  "difficulty": "basic",
  "expected_cause": "service_selector_pod_label_mismatch",
  "symptoms": ["..."],
  "must_mention": ["service.spec.selector", "pod.metadata.labels", "endpoints <none>"],
  "forbidden_actions": ["검증 없는 oc delete", "검증 없는 oc patch"],
  "source": "synthetic",
  "generator": "scripts/generate_seed_dataset.py",
  "version": "v2.0",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

Training exports keep only:

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

## Required Assistant Sections

Every assistant answer must include:

```text
[진단]
[근거]
[확인 명령어]
[조치 방향]
[주의사항]
[추가 확인질문]
```

The answer must:

- name the most likely cause first
- cite exact YAML/status/log fields
- include namespace-scoped `oc` commands
- separate direct evidence from noisy background logs
- avoid immediate destructive commands
- never ask to print Secret values

## Quality Gates

Run validation before training:

```bash
python -m scripts.validate_jsonl data/curated/train.full.jsonl data/curated/eval.full.jsonl data/curated/gold.full.jsonl --write-invalid data/rejected/invalid_samples.jsonl
```

Current result:

```text
VALID: 11261
WARN: 0
ERROR: 0
UNIQUE_PAIR_RATIO: 1.0000
```

Diversity audit:

```bash
python -m scripts.audit_dataset_diversity data/curated/aiops_train.jsonl
```

Current train result:

```text
UNIQUE_QUESTIONS: 10000
UNIQUE_ANSWERS: 10000
UNIQUE_PAIRS: 10000
REPEATED_PAIR_ROWS: 0
```

Scoring:

```bash
python -m scripts.score_dataset data/curated/train.full.jsonl data/curated/eval.full.jsonl data/curated/gold.full.jsonl --json-report data/reports/quality_report.json --markdown-report data/reports/score_report.md
```

## Regenerate Dataset

Generate raw split files:

```bash
python -m scripts.generate_seed_dataset
```

Validate:

```bash
python -m scripts.validate_jsonl data/raw/train.raw.jsonl data/raw/eval.raw.jsonl data/raw/gold.raw.jsonl --write-invalid data/rejected/invalid_samples.jsonl
```

Promote raw to curated full files, then export messages-only files:

```bash
python -m scripts.export_training_jsonl data/curated/train.full.jsonl data/curated/aiops_train.jsonl
python -m scripts.export_training_jsonl data/curated/eval.full.jsonl data/curated/aiops_eval.jsonl
python -m scripts.export_training_jsonl data/curated/gold.full.jsonl data/curated/aiops_gold.jsonl
```

## Training Notebook

Use:

```text
notebooks/aiops_training.ipynb
```

The notebook uses:

- SFTTrainer for supervised fine-tuning
- PEFT LoRA adapter training
- 4bit QLoRA model loading
- `aiops_train.jsonl` for training
- `aiops_eval.jsonl` for eval loss
- `aiops_gold.jsonl` for final holdout generation checks

Training outputs are written under:

```text
~/aiops-gemma3/outputs/gemma3-12b-aiops-lora-v1
```

The notebook also packages the adapter as a `.tar.gz` archive and uploads the adapter files to MinIO:

```text
s3://rhoai-models/aiops-adapters/gemma3-12b-aiops-lora-v1/
```

## Reports

- `data/reports/dataset_summary.md`
- `data/reports/quality_report.json`
- `data/reports/score_report.md`
