# Container hash migration check

Checks `plugins/module_utils/kubelet_hash_migration.py` (used by the
`vexxhost.kubernetes.kubelet_container_hash_migration` module) against a real
containerd 2.2 metadata database:

```sh
cd hack/kubelet-hash-migration
go run . create /tmp/meta.db /tmp/plan.json
python3 apply.py /tmp/meta.db /tmp/plan.json
go run . verify /tmp/meta.db /tmp/plan.json
```

`verify` fails if bbolt's consistency check fails, if containerd cannot read a
container back, or if a container does not carry its new hash.
