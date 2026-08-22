# Cluster API

This role deploys the [Cluster API](https://cluster-api.sigs.k8s.io/) on a
Kubernetes cluster.

## Optional Helm add-on provider

Set `cluster_api_addon_provider_enabled: true` to install the pinned Cluster
API Add-on Provider for Helm and include it in `clusterctl init` and upgrade
operations. It is disabled by default and therefore does not alter existing
Ubuntu 22.04, Ubuntu 24.04, or other Kubernetes image/tag combinations.

The role installs two controller replicas, a disruption budget, topology
spread, bounded resources, and a digest-pinned controller image. Add-on chart
selection and workload compatibility remain deployment inputs; this generic
role does not assume NVIDIA hardware, a guest operating system, or a specific
Kubernetes minor release.

```yaml
cluster_api_addon_provider_enabled: true
cluster_api_addon_provider: helm
cluster_api_addon_provider_version: 0.6.4
cluster_api_addon_provider_node_selector:
  openstack-control-plane: enabled
```
