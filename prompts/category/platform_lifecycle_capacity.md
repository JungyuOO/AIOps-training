# platform_lifecycle_capacity

Broad platform lifecycle, operator, capacity, and cleanup cases.

Include OLM Subscription/CSV/InstallPlan issues, OperatorGroup scope mismatch, DSC/DSCI NotReady, missing Service Mesh/Knative/Authorino dependencies, quota and LimitRange blocks, orphaned Routes/Services, old ReplicaSets, completed Jobs, and cleanup candidates.

The assistant should distinguish "cleanup candidate" from "safe to delete now" and must require ownerReferences, route/service references, quota status, and operational impact checks before recommending changes.
