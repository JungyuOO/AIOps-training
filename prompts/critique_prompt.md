# Critique Prompt

Review each OpenShift AIOps SFT sample against these checks:

- JSON is valid and has all required metadata.
- `category` is a broad domain and `expected_cause` is the concrete failure mode.
- `messages` are ordered as `system`, `user`, `assistant`.
- The assistant uses `[진단]`, `[근거]`, `[확인 명령어]`, `[조치 방향]`, `[주의사항]`, and `[추가 확인질문]`.
- The diagnosis identifies one most likely cause before listing alternatives.
- Evidence cites specific fields such as `spec.selector`, `metadata.labels`, `status.conditions`, `secretKeyRef.key`, `targetPort`, event messages, object size, GPU allocatable, or OLM conditions.
- Every namespaced `oc` command includes `-n <namespace>` or `--namespace <namespace>`.
- Cluster-scoped or all-namespace checks such as `oc get nodes` and `oc get pod -A` are acceptable.
- Samples must not differ only by namespace, ids, timestamps, or numeric substitutions.
- Realistic non-causal noise is allowed, but the assistant must distinguish direct evidence from noise.
- Dangerous actions such as `oc delete`, `oc patch`, `oc scale`, and `oc rollout restart` are not suggested as immediate fixes.
- Secret values are never requested or printed.

Return a compact critique with blocking errors first, then warnings, then suggested rewrite direction.
