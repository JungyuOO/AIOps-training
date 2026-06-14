# configuration_identity

Broad configuration and identity cases.

Include Secret key mismatch, ConfigMap key mismatch, `envFrom` prefix drift, imagePullSecret linkage, ServiceAccount token audience, RBAC forbidden errors, S3 credential key names, OAuth/Authorino/OLS secret references, and KServe storage secret schema.

The assistant must never ask to print Secret values. It should compare key names, reference paths, ServiceAccount linkage, and RBAC rules.
