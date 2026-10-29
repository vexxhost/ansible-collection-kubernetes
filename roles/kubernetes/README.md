# `kubernetes`

## Control plane arguments

`kubeadm join` and `kubeadm upgrade` render the control plane components from
the `ClusterConfiguration` stored in the `kube-system/kubeadm-config`
ConfigMap, and kubeadm only uploads that from `/etc/kubernetes/kubeadm.yaml`
when it creates the cluster. On every run, the role merges the arguments it
sets for etcd, kube-apiserver, kube-controller-manager and kube-scheduler
(including `kubernetes_kubeadm_extra_args`) into the stored copy:

- Arguments the role sets replace stored ones with the same name.
- Other stored arguments are kept.
- Arguments set to `null` in `kubernetes_kubeadm_extra_args` are removed.

This keeps clusters created by older versions of the role in line with new
ones. For example, kube-scheduler and kube-controller-manager keep
`bind-address: 0.0.0.0` (so their metrics and health endpoints stay reachable
on the node IPs) instead of going back to `127.0.0.1` on upgrade.

kubeadm applies the stored arguments the next time it writes the components,
during an upgrade or when a control plane node joins. Running the role does not
restart the control plane by itself.
