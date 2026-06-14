# application_connectivity

Broad OpenShift application connectivity cases.

Include Route, Service, EndpointSlice, readiness, TLS termination, backend protocol, DNS, NetworkPolicy, traffic split, and ingress symptoms. The model must identify the concrete `expected_cause`, not just say "network problem".

Required evidence should point to fields such as `route.spec.to.name`, `service.spec.selector`, `service.spec.ports[].targetPort`, `pod.metadata.labels`, `pod.status.conditions`, `endpointslice.conditions.ready`, NetworkPolicy ingress rules, DNS query output, or Route backend weights.
