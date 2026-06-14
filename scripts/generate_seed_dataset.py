#!/usr/bin/env python3
"""Generate broad-domain OpenShift AIOps SFT datasets with noisy real-world cases."""

from __future__ import annotations

import json
from pathlib import Path


SYSTEM = (
    "너는 OpenShift AIOps 운영 분석가다. OpenShift, Kubernetes, RHOAI, KServe, "
    "MinIO, GPU, OLM, 네트워크, 인증, 스토리지, 리소스 수명주기 신호를 종합해 "
    "가장 가능성이 높은 원인과 안전한 확인 절차를 제시한다. 검증 없는 삭제, 패치, "
    "재시작, 스케일 변경 같은 위험 조치를 바로 지시하지 않는다."
)

CATEGORY_COUNTS = {
    "train": {
        "application_connectivity": 2000,
        "configuration_identity": 2000,
        "storage_data_artifacts": 2000,
        "accelerator_serving_runtime": 2000,
        "platform_lifecycle_capacity": 2000,
    },
    "eval": {
        "application_connectivity": 222,
        "configuration_identity": 222,
        "storage_data_artifacts": 222,
        "accelerator_serving_runtime": 222,
        "platform_lifecycle_capacity": 223,
    },
    "gold": {
        "application_connectivity": 30,
        "configuration_identity": 30,
        "storage_data_artifacts": 30,
        "accelerator_serving_runtime": 30,
        "platform_lifecycle_capacity": 30,
    },
}

DIFFICULTIES = ["basic", "basic", "intermediate", "intermediate", "advanced"]

CASES = {
    "application_connectivity": [
        ("service_selector_pod_label_mismatch", "Service selector와 Pod label이 달라 Endpoint가 비어 있음", "service.spec.selector", "pod.metadata.labels", "endpoints <none>"),
        ("service_targetport_containerport_mismatch", "Service targetPort가 컨테이너 포트와 달라 connection refused 발생", "service.spec.ports[].targetPort", "containerPort", "event connection refused"),
        ("readiness_probe_excludes_endpoint", "Readiness probe 실패로 EndpointSlice ready=false", "pod.status.conditions", "endpointslice.conditions.ready", "readiness probe"),
        ("route_points_to_wrong_service", "Route spec.to.name이 장애 서비스가 아닌 오래된 Service를 가리킴", "route.spec.to.name", "service.metadata.name", "route admitted"),
        ("route_tls_backend_protocol_mismatch", "Route TLS termination과 backend protocol 조합이 맞지 않음", "route.spec.tls.termination", "service port name", "backend handshake error"),
        ("networkpolicy_blocks_service_traffic", "NetworkPolicy가 ingress from namespace/pod selector를 막음", "networkpolicy.spec.ingress", "pod labels", "timeout"),
        ("cluster_dns_service_resolution_failure", "CoreDNS 또는 Service DNS 해석 실패가 특정 namespace에서 반복됨", "dns query", "service fqdn", "coredns log"),
        ("ingress_canary_route_weight_misconfigured", "canary/blue-green Route weight가 의도와 달라 트래픽이 잘못 분배됨", "route.spec.alternateBackends", "weight", "backend service"),
    ],
    "configuration_identity": [
        ("secret_key_mismatch", "Secret은 있지만 Deployment가 참조하는 key가 없음", "env.valueFrom.secretKeyRef.key", "secret.data keys", "CrashLoopBackOff"),
        ("configmap_key_mismatch", "ConfigMap key 이름이 애플리케이션 기대값과 다름", "configMapKeyRef.key", "configMap.data keys", "CreateContainerConfigError"),
        ("imagepullsecret_missing_on_serviceaccount", "private registry 이미지를 pull할 Secret이 ServiceAccount에 연결되지 않음", "imagePullSecrets", "serviceAccount.imagePullSecrets", "ImagePullBackOff"),
        ("serviceaccount_token_audience_mismatch", "ServiceAccount token audience가 외부 API 기대 audience와 다름", "serviceAccountName", "token audience", "401 unauthorized"),
        ("rbac_forbidden_on_config_watch", "Controller가 ConfigMap/Secret watch 권한이 없어 동기화 실패", "role rules", "serviceAccount", "Forbidden"),
        ("s3_credential_key_name_mismatch", "S3 credential Secret key 이름이 SDK가 기대하는 이름과 다름", "secret.data keys", "AWS_ACCESS_KEY_ID", "S3 auth error"),
        ("oauth_client_secret_reference_missing", "OAuth/Authorino/OLS 설정의 credentialsSecretRef가 존재하지 않음", "credentialsSecretRef", "secret name", "NotReady"),
        ("envfrom_prefix_breaks_expected_variable", "envFrom prefix 때문에 애플리케이션이 기대하는 환경변수명이 생성되지 않음", "envFrom.prefix", "container env", "missing env var"),
    ],
    "storage_data_artifacts": [
        ("pvc_pending_missing_storageclass", "PVC storageClassName이 비어 Pending 상태", "pvc.status.phase", "pvc.spec.storageClassName", "FailedBinding"),
        ("rwo_pvc_multi_attach_conflict", "ReadWriteOnce PVC를 두 Pod가 동시에 attach하려 함", "accessModes", "persistentVolumeClaim.claimName", "Multi-Attach"),
        ("minio_model_object_zero_bytes", "MinIO 모델 파일이 0B라 storage-initializer가 EOF 발생", "object size", "model path", "storage-initializer"),
        ("s3_endpoint_scheme_missing", "S3 endpoint에 http/https scheme이 없어 client 초기화 실패", "S3 endpoint", "storageUri", "invalid endpoint"),
        ("bucket_prefix_typo_model_not_found", "bucket/prefix 오타로 모델 경로를 찾지 못함", "bucket", "prefix", "NoSuchKey"),
        ("node_filesystem_no_space_left", "노드 또는 PVC 파일시스템 공간 부족으로 쓰기 실패", "No space left on device", "pvc usage", "node filesystem"),
        ("storage_initializer_ca_bundle_missing", "사설 MinIO TLS 인증서 CA bundle이 없어 TLS 검증 실패", "caBundle", "x509", "storage-initializer"),
        ("multipart_upload_incomplete_artifact", "multipart upload 중단으로 safetensors shard 일부가 누락됨", "object list", "shard count", "unexpected EOF"),
    ],
    "accelerator_serving_runtime": [
        ("insufficient_gpu_allocatable", "Pod가 요청한 nvidia.com/gpu보다 allocatable GPU가 부족함", "node.status.allocatable.nvidia.com/gpu", "resources.limits.nvidia.com/gpu", "FailedScheduling"),
        ("workbench_occupies_available_gpu", "Workbench Pod가 단일 GPU를 점유해 KServe predictor가 Pending", "Workbench Pod", "pod resources", "Insufficient nvidia.com/gpu"),
        ("nvidia_visible_devices_void", "컨테이너 환경에서 NVIDIA_VISIBLE_DEVICES=void라 torch CUDA가 비활성", "NVIDIA_VISIBLE_DEVICES", "torch.cuda.is_available", "pod env"),
        ("gpu_device_plugin_not_ready", "NVIDIA device plugin DaemonSet이 NotReady라 GPU 리소스가 노출되지 않음", "DaemonSet status", "node allocatable", "device plugin"),
        ("vllm_max_model_len_oom", "vLLM max_model_len이 과도해 KV cache OOM 발생", "vLLM args", "CUDA out of memory", "max_model_len"),
        ("kserve_runtime_storage_init_blocks_predictor", "storage initializer 실패 때문에 predictor 컨테이너가 시작되지 않음", "init container", "InferenceService predictor", "storageUri"),
        ("cuda_driver_runtime_version_mismatch", "CUDA runtime과 노드 driver 버전 불일치로 로딩 실패", "CUDA error", "driver version", "runtime image"),
        ("model_server_liveness_timeout_during_warmup", "대형 모델 warmup 시간이 길어 liveness probe가 먼저 실패", "livenessProbe", "startup time", "model loading"),
    ],
    "platform_lifecycle_capacity": [
        ("installplan_manual_approval_pending", "Manual InstallPlan이 승인 대기라 CSV가 Pending", "installplan.spec.approved", "subscription.status", "csv.status.phase"),
        ("operatorgroup_targetnamespace_mismatch", "OperatorGroup targetNamespaces가 설치 namespace와 맞지 않음", "operatorgroup.spec.targetNamespaces", "csv reason", "UnsupportedOperatorGroup"),
        ("dsci_service_mesh_missing_operator", "DSCI CapabilityServiceMesh 조건이 MissingOperator", "dsci.status.conditions", "CapabilityServiceMesh", "MissingOperator"),
        ("knative_serving_not_ready_blocks_kserve", "KnativeServing NotReady로 KServe 경로가 준비되지 않음", "KnativeServing condition", "KServe condition", "NotReady"),
        ("quota_blocks_new_pods", "ResourceQuota가 CPU/MEM/GPU 요청을 막아 신규 Pod 생성 실패", "resourcequota.status", "pod requests", "exceeded quota"),
        ("limitrange_default_request_too_high", "LimitRange 기본 request가 과도해 스케줄링 실패", "limitrange.spec", "pod requests", "insufficient cpu"),
        ("orphaned_route_service_cleanup_candidate", "ownerReferences가 없는 Route/Service가 남아 정리 후보지만 영향 확인 필요", "ownerReferences", "route.spec.to.name", "service.spec.selector"),
        ("old_replicaset_or_completed_jobs_accumulated", "오래된 ReplicaSet/Completed Job 누적으로 정리 필요", "metadata.creationTimestamp", "ownerReferences", "job status"),
    ],
}

APPS = ["orders", "billing", "claims", "portal", "catalog", "checkout", "notebook", "embedding", "gateway", "collector", "trainer", "predictor", "router", "inventory", "fraud", "search", "recommend", "profile", "audit", "invoice", "shipment", "risk", "events", "metrics"]
ENVS = ["dev", "test", "stage", "prod", "dr", "perf", "sandbox", "pilot"]
TEAMS = ["platform", "mlops", "payments", "retail", "ops", "analytics", "serving", "infra"]
MODELS = ["gemma-3-12b-it", "llama-guard-8b", "embedding-ko-v2", "reranker-ko", "granite-code", "mistral-serve"]
NODES = ["worker-a40-01", "worker-a40-02", "worker-l40s-01", "gpu-node-03", "compute-07"]
REGISTRIES = ["registry.redhat.io", "quay.internal.local", "registry.apps.lab", "harbor.corp.local"]


def pick(values: list[str], index: int, offset: int = 0) -> str:
    return values[(index + offset) % len(values)]


def alpha_code(index: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    n = index + 1
    chars = []
    while n:
        n, rem = divmod(n - 1, 26)
        chars.append(alphabet[rem])
    return "".join(reversed(chars))


def variation(category: str, index: int, split: str) -> dict[str, str | int]:
    cause, description, field_a, field_b, field_c = CASES[category][index % len(CASES[category])]
    app = pick(APPS, index)
    env = pick(ENVS, index, 2)
    team = pick(TEAMS, index, 4)
    seq = index + 1
    release = f"{pick(['atlas', 'boreal', 'cygnus', 'delta', 'ember', 'flux', 'galaxy', 'helix'], index)}-{alpha_code(index)}"
    return {
        "category": category,
        "cause": cause,
        "description": description,
        "field_a": field_a,
        "field_b": field_b,
        "field_c": field_c,
        "split": split,
        "seq": seq,
        "app": app,
        "env": env,
        "team": team,
        "namespace": f"{team}-{env}-{split}-{seq:05d}",
        "service": f"{app}-svc-{(index % 31) + 1}",
        "route": f"{app}-route-{(index % 37) + 1}",
        "pod": f"{app}-{(index * 17 % 4096):03x}",
        "deploy": f"{app}-deploy-{(index % 43) + 1}",
        "model": pick(MODELS, index),
        "node": pick(NODES, index),
        "registry": pick(REGISTRIES, index),
        "selector": f"{app}-{env}",
        "pod_label": f"{app}-{env}-v{(index % 5) + 1}",
        "container_port": 7000 + (index * 13 % 900),
        "target_port": 7100 + (index * 19 % 900),
        "gpu": 1 + (index % 2),
        "storage_gi": 10 + (index * 3 % 190),
        "restart_count": 5 + (index * 7 % 211),
        "status_code": 500 + (index % 29),
        "change": f"CHG-{split.upper()}-{category[:3].upper()}-{release}",
        "release": release,
        "timestamp": f"2026-06-{(index % 27) + 1:02d}T{(index * 7 % 24):02d}:{(index * 11 % 60):02d}:00Z",
    }


def difficulty_for(index: int) -> str:
    return DIFFICULTIES[index % len(DIFFICULTIES)]


def symptoms_for(v: dict[str, str | int]) -> list[str]:
    return [str(v["description"]), str(v["field_a"]), str(v["field_b"]), str(v["field_c"])]


def oc_block(v: dict[str, str | int]) -> str:
    ns = v["namespace"]
    category = v["category"]
    if category == "application_connectivity":
        return f"""`oc get route {v['route']} -n {ns} -o yaml`
spec:
  to:
    name: {v['service']}
  tls:
    termination: edge

`oc get svc {v['service']} -n {ns} -o yaml`
spec:
  selector:
    app: {v['selector']}
  ports:
  - port: 80
    targetPort: {v['target_port']}

`oc get pod {v['pod']} -n {ns} --show-labels`
{v['pod']} app={v['pod_label']},team={v['team']}

Events:
Warning Unhealthy {v['field_c']} observed for {v['app']} at {v['timestamp']}"""
    if category == "configuration_identity":
        return f"""`oc describe pod {v['pod']} -n {ns}`
Warning Failed {v['field_c']} for workload {v['app']}

Deployment YAML:
serviceAccountName: {v['app']}-sa
env:
- name: {str(v['app']).upper()}_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {v['app']}-credentials
      key: password
image: {v['registry']}/{v['team']}/{v['app']}:v{int(v['seq']) % 17}

`oc get secret,configmap,serviceaccount -n {ns}`
{v['app']}-credentials   Opaque
{v['app']}-config        ConfigMap
{v['app']}-sa            ServiceAccount"""
    if category == "storage_data_artifacts":
        return f"""`oc get pvc {v['app']}-data -n {ns} -o yaml`
spec:
  storageClassName: ""
  resources:
    requests:
      storage: {v['storage_gi']}Gi
status:
  phase: Pending

`oc logs pod/{v['app']}-predictor -c storage-initializer -n {ns}`
{v['field_c']}: path=s3://rhoai-models/{v['model']}/snapshots/{str(v['change']).lower()}

Object inventory:
model={v['model']} shard={int(v['seq']) % 9} size={0 if 'zero' in str(v['cause']) else int(v['seq']) * 1024}"""
    if category == "accelerator_serving_runtime":
        return f"""`oc describe pod {v['app']}-predictor-0 -n {ns}`
Warning FailedScheduling {v['field_c']}

Predictor spec:
resources:
  limits:
    nvidia.com/gpu: "{v['gpu']}"
args:
- --model=/mnt/models/{v['model']}
- --max-model-len={16384 + (int(v['seq']) % 4) * 8192}

`oc get pod -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,GPU:.spec.containers[*].resources.limits.nvidia\\.com/gpu,NODE:.spec.nodeName`
notebooks {v['team']}-{v['app']}-workbench 1 {v['node']}"""
    return f"""`oc get csv,subscription,installplan,operatorgroup -n {ns}`
NAME STATUS REASON
{v['app']}-operator.v2 Pending {v['field_c']}

`oc get dsc,dsci -n {ns} -o yaml`
status:
  conditions:
  - type: Ready
    status: "False"
    reason: {v['cause']}

`oc get resourcequota,limitrange,job,rs,route,svc -n {ns}`
{v['app']}-quota hard.cpu={2 + int(v['seq']) % 8} used.cpu={2 + int(v['seq']) % 8}"""


def user_prompt(v: dict[str, str | int]) -> str:
    return f"""namespace: {v['namespace']}

운영 알림: {v['team']} 팀의 {v['app']} 워크로드에서 `{v['cause']}` 의심 상황입니다.
최근 변경: {v['change']}
릴리스: {v['release']}
관측 시각: {v['timestamp']}
노이즈 로그:
- sidecar envoy access log 200 /readyz latency={int(v['seq']) % 300}ms
- unrelated pod {v['app']}-canary restartCount={int(v['seq']) % 3}
- previous deploy annotation checksum/config={alpha_code(int(v['seq']) + 30)}

{oc_block(v)}

위 출력 기준으로 가장 가능성이 높은 원인, 근거 필드, 확인 명령어, 안전한 조치 방향을 정리해 주세요."""


def assistant_answer(v: dict[str, str | int]) -> str:
    ns = v["namespace"]
    commands = [
        f"oc get events -n {ns} --sort-by=.lastTimestamp",
        f"oc get pod -n {ns} -o wide",
    ]
    if v["category"] == "application_connectivity":
        commands += [
            f"oc get route {v['route']} -n {ns} -o yaml",
            f"oc get svc {v['service']} -n {ns} -o yaml",
            f"oc get endpoints,endpointslice -n {ns} -l kubernetes.io/service-name={v['service']}",
            f"oc get networkpolicy -n {ns} -o yaml",
        ]
    elif v["category"] == "configuration_identity":
        commands += [
            f"oc get deploy {v['deploy']} -n {ns} -o yaml",
            f"oc get secret,configmap,serviceaccount,role,rolebinding -n {ns}",
            f"oc describe pod {v['pod']} -n {ns}",
        ]
    elif v["category"] == "storage_data_artifacts":
        commands += [
            f"oc get pvc,pv,pod -n {ns}",
            f"oc describe pvc {v['app']}-data -n {ns}",
            f"oc logs -n {ns} --all-containers --tail=120 pod/{v['app']}-predictor",
        ]
    elif v["category"] == "accelerator_serving_runtime":
        commands += [
            f"oc describe pod -n {ns} --selector serving.kserve.io/inferenceservice",
            "oc get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu",
            "oc get pod -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,GPU:.spec.containers[*].resources.limits.nvidia\\.com/gpu,NODE:.spec.nodeName",
        ]
    else:
        commands += [
            f"oc get csv,subscription,installplan,operatorgroup -n {ns}",
            f"oc get dsc,dsci,resourcequota,limitrange,job,rs -n {ns} -o yaml",
        ]

    style = int(v["seq"]) % 4
    opener = [
        f"`{v['cause']}`를 1순위 원인으로 봅니다.",
        f"가장 먼저 확인할 가설은 `{v['cause']}`입니다.",
        f"현재 증거만 보면 `{v['cause']}` 가능성이 가장 높습니다.",
        f"우선순위가 가장 높은 원인은 `{v['cause']}`입니다.",
    ][style]
    evidence = (
        f"{v['description']} 관측과 `{v['field_a']}`, `{v['field_b']}`, `{v['field_c']}` "
        f"필드가 같은 방향을 가리킵니다. 노이즈 로그는 직접 원인보다 보조 신호로만 봐야 합니다."
    )
    action = {
        "application_connectivity": "Route/Service/Endpoint/DNS/NetworkPolicy 중 실제로 끊긴 지점을 좁힌 뒤 배포 원본에서 매핑을 정정합니다.",
        "configuration_identity": "Secret 값은 출력하지 말고 key 이름, 참조 경로, ServiceAccount/RBAC 연결만 비교합니다.",
        "storage_data_artifacts": "PVC/PV 상태와 S3 object 목록, 모델 artifact 크기, initializer 로그를 함께 확인한 뒤 경로 또는 업로드를 정정합니다.",
        "accelerator_serving_runtime": "GPU 점유 Pod, node allocatable, runtime args, CUDA 로그를 함께 보고 요청량 또는 serving 설정을 조정합니다.",
        "platform_lifecycle_capacity": "OLM/DSC 조건, quota/limitrange, ownerReferences를 먼저 확인해 플랫폼 상태와 정리 후보를 분리합니다.",
    }[str(v["category"])]
    return f"""[진단]
{opener} 단일 로그 한 줄보다 YAML 필드, 이벤트, 상태 조건이 같은 방향으로 맞물리는지가 더 중요합니다.

[근거]
{evidence} 관측 대상은 namespace `{ns}`, app `{v['app']}`, change `{v['change']}`입니다.

[확인 명령어]
```bash
{chr(10).join(commands)}
```

[조치 방향]
{action} 원인이 맞더라도 운영 리소스 직접 변경 전에는 ownerReferences, 영향 namespace, 관련 워크로드를 확인하고 GitOps 원본에서 추적 가능하게 수정합니다.

[주의사항]
검증 없이 `oc delete`, `oc patch`, `oc scale`, `oc rollout restart`를 바로 실행하지 마십시오. Secret 문제에서는 값 출력이 아니라 key 이름과 참조 경로만 확인해야 합니다.

[추가 확인질문]
`{ns}`에서 `{v['change']}` 이후 이미지, 설정, 스토리지, GPU, OLM/Operator, quota 관련 변경이 있었습니까?"""


def build_record(category: str, index: int, split: str) -> dict:
    v = variation(category, index, split)
    return {
        "id": f"{split}-{category}-{index + 1:05d}",
        "category": category,
        "difficulty": difficulty_for(index),
        "expected_cause": v["cause"],
        "symptoms": symptoms_for(v),
        "must_mention": [v["field_a"], v["field_b"], v["field_c"]],
        "forbidden_actions": ["검증 없는 oc delete", "검증 없는 oc patch", "검증 없는 oc scale", "검증 없는 rollout restart"],
        "source": "synthetic",
        "generator": "scripts/generate_seed_dataset.py",
        "version": "v2.0",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt(v) + f"\n\ncase_id: {split}-{category}-{index + 1:05d}"},
            {"role": "assistant", "content": assistant_answer(v)},
        ],
    }


def main() -> int:
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    for split, category_counts in CATEGORY_COUNTS.items():
        path = out_dir / f"{split}.raw.jsonl"
        total = 0
        with path.open("w", encoding="utf-8") as handle:
            for category, count in category_counts.items():
                for index in range(count):
                    handle.write(json.dumps(build_record(category, index, split), ensure_ascii=False) + "\n")
                    total += 1
        print(f"WROTE: {path} {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
