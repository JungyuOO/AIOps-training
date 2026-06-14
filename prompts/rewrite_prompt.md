# Rewrite Prompt

Rewrite only samples that failed validation, failed diversity checks, or scored below Gold.

Preserve the broad `category`, `difficulty`, and concrete `expected_cause` unless they are clearly wrong. Keep realistic OpenShift evidence in the user turn.

Rewrite the assistant turn so that it:

- Uses all six required sections.
- Names the most likely cause first.
- Points to exact resource fields and event/log lines.
- Separates direct cause evidence from noisy but realistic background logs.
- Includes namespace-scoped `oc` verification commands.
- Describes safe remediation direction without directly instructing destructive commands.
- Includes a concise follow-up question when evidence is insufficient.

If the original sample only changed namespace, id, timestamp, or numbers, rewrite the scenario with meaningful variation in resource type, evidence fields, logs, and cause chain.

Return JSONL only.
