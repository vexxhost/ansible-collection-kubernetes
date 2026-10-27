# Cluster API

This role deploys the [Cluster API](https://cluster-api.sigs.k8s.io/) on a
Kubernetes cluster.

The role compares the providers you configure with the `Provider` objects that
`clusterctl` records in the management cluster. It upgrades providers whose
version changed with `clusterctl upgrade apply`, then installs missing ones
with `clusterctl init`. You can change versions or add providers on an existing
management cluster by running the role again.

## Add-on providers

`clusterctl` can also manage [add-on providers][addon-providers], which are
controllers that run next to Cluster API in the management cluster. List them
in `cluster_api_addon_providers`:

```yaml
cluster_api_addon_providers:
  - name: csr-approver
    version: 0.1.0
```

Add-on manifests are read from `files/providers/addon-<name>/v<version>` in
this role, so installs work without internet access. To use an add-on that
isn't bundled here, set `url` to its `addon-components.yaml`. The
`metadata.yaml` file must be next to it.

Add-ons are upgraded and get `cluster_api_node_selector` like the other
providers. Use `clusterctl_config` to set add-on variables or to override
images, for example to pull from a local registry:

```yaml
clusterctl_config:
  CSR_APPROVER_MAX_EXPIRATION: 720h
  images:
    addon-csr-approver/cluster-api-csr-approver:
      repository: registry.example.com/vexxhost
      tag: v0.1.0
```

`clusterctl` applies variables only when it installs or upgrades a provider.

### Bundled add-ons

| Name | Versions | Requires | Description |
|---|---|---|---|
| [`csr-approver`][csr-approver] | `0.1.0` | Cluster API 1.11 or later | Approves kubelet serving certificate requests in workload clusters after checking them against the Machine addresses. |

[addon-providers]: https://cluster-api.sigs.k8s.io/developer/providers/contracts/clusterctl
[csr-approver]: https://github.com/vexxhost/cluster-api-csr-approver
