# Generation Prompt

Generate high-quality Korean OpenShift AIOps SFT data.

Output JSONL only. Do not wrap the output in Markdown. Each line must be one JSON object with:

- `id`
- `category`
- `difficulty`
- `expected_cause`
- `symptoms`
- `must_mention`
- `forbidden_actions`
- `source`
- `generator`
- `version`
- `messages`

`messages` must contain exactly three turns in this order: `system`, `user`, `assistant`.

Use broad domain categories:

- `application_connectivity`
- `configuration_identity`
- `storage_data_artifacts`
- `accelerator_serving_runtime`
- `platform_lifecycle_capacity`

Use `expected_cause` for the concrete failure mode inside the broad category.

The assistant answer must use these six sections exactly:

```text
[진단]
[근거]
[확인 명령어]
[조치 방향]
[주의사항]
[추가 확인질문]
```

The user message must include realistic `oc get`, `oc describe`, YAML snippets, events, logs, and some non-causal noise. Do not create samples that differ only by namespace, case id, timestamps, or numeric values.

The assistant must name the most likely cause first, cite concrete YAML/status/log fields, separate direct evidence from noise, include namespace-scoped validation commands, avoid immediate destructive action, and ask for missing information when needed.
