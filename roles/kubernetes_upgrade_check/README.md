# `kubernetes_upgrade_check`

Checks that run before the `kubernetes` role changes anything:

- The target version is not older than the cluster, and at most one minor
  version ahead of it.
- Workers are not upgraded past a control plane that is not part of the play.
- The target version is not in `kubernetes_upgrade_check_cgroups_per_qos_denylist`
  while any node in the Kubernetes inventory group runs pods without QoS cgroups
  (`--cgroups-per-qos=false`, which nodes deployed by older releases of this
  collection keep).
- A cluster-wide admission guard is requested when an affected 1.35+ kubelet
  can be crashed by an explicit `pods/resize` request and any node runs without
  QoS cgroups.

## Kubelets that crash without QoS cgroups

Kubernetes 1.35.9 and 1.36.4 backported
[kubernetes/kubernetes#140387](https://github.com/kubernetes/kubernetes/pull/140387),
which resizes a pod when one of its containers starts without a record of the
resources applied to it.  The kubelet only creates those records for new pods
when it manages pod cgroups, so on a node without QoS cgroups, once the init
containers of a pod with requests or limits finish, the kubelet resizes the
pod, dereferences the nil pod cgroup configuration in `doPodResizeAction`, and
crashes ([kubernetes/kubernetes#137993](https://github.com/kubernetes/kubernetes/issues/137993)).
This does not depend on the upgrade: any such pod crashes the kubelet.
[kubernetes/kubernetes#137999](https://github.com/kubernetes/kubernetes/pull/137999)
fixes it, but has not merged yet.

The default denylist has one entry per minor version: 1.35.9 and later 1.35
releases, 1.36.4 and later 1.36 releases, and everything from 1.37.0.  The fix
will ship in a different patch release on each branch, so when a branch gets
it, set `max` on that branch's entry to the first fixed release.  For example,
if 1.35.12, 1.36.8 and 1.37.4 include the fix:

```yaml
kubernetes_upgrade_check_cgroups_per_qos_denylist:
  - min: "1.35.9"
    max: "1.35.12"
  - min: "1.36.4"
    max: "1.36.8"
  - min: "1.37.0"
    max: "1.37.4"
```

Overriding the variable replaces the whole list.  Setting it to `[]` turns
the check off.

All releases from 1.35.0 are also vulnerable when an API client explicitly
updates the `pods/resize` subresource.  For versions selected by
`kubernetes_upgrade_check_cgroups_per_qos_resize_guard_versions`, the
`kubernetes` role creates a `ValidatingAdmissionPolicy` and binding that deny
only that subresource when at least one node lacks QoS cgroups.  Ordinary pod
updates continue to work.  On a new cluster, the policy is installed as soon
as the first API server is available and before additional control-plane or
worker nodes join. On an existing cluster, it is installed before new nodes
join or any kubelet is switched to 1.35+. It is removed when every node uses
QoS cgroups, or when both the target version and every installed kubelet on a
legacy node are outside the affected range. An unknown installed kubelet
version or QoS-cgroup state conservatively keeps the guard. A VPA using
`InPlaceOrRecreate` can fall back to eviction and recreation while the guard
rejects in-place resize. Like the hard denylist, the guard has one range per
Kubernetes minor so fixed branches can be opened independently.

When upgrading from an affected release to the first fixed release, the
preflight sees the old kubelets and deliberately retains the guard during the
upgrade. Run the Kubernetes role again for the full inventory after every
kubelet is fixed so the role can remove the now-unneeded policy.

The admission policy cannot protect against kubelet-initiated resize.  That is
why the automatic-trigger releases remain hard-denied by
`kubernetes_upgrade_check_cgroups_per_qos_denylist` until the upstream panic is
fixed.

For joined nodes, the role reads the running version from
`status.nodeInfo.kubeletVersion` and the effective QoS-cgroup setting from the
kubelet `configz` endpoint through the Kubernetes API. This includes
command-line flag overrides without opening an Ansible connection to each
node. The API query tries `kubernetes_bootstrap_node` first when it is
explicitly set, then each host in `kubernetes_control_plane_group` until one
returns usable API data. A delegate that cannot load its kubeconfig or list
Nodes is skipped even though the module reports that evidence gap without
failing. If no controller can perform the query, play hosts use local fallback
evidence and hosts outside the play remain unknown.

Every Node object returned by the API is inspected, including Nodes whose host
is absent from `kubernetes_upgrade_check_group`. These untracked Nodes are
reported and their state participates in denylist and admission-guard
decisions. Shut down a removed host and delete its Node API object before
removing it from inventory; an inaccessible untracked Node conservatively keeps
the guard installed. For a play host that has no Node object yet, the role falls
back to its local
`/var/lib/kubelet/kubeadm-flags.env`, `/etc/default/kubelet` and
`/var/lib/kubelet/config.yaml`, plus that host's
`kubernetes_kubeadm_extra_args` and `kubernetes_kubeadm_patches` inventory
values. A failed local read is unknown; only a successful `stat` proving that a
file is absent permits inventory/default evidence. Nodes can be moved to QoS
cgroups with a drain and rejoin, which restarts their pods. Follow the supported
[legacy-node migration procedure](../../docs/ops/qos-cgroups.md) to preserve
workload and control-plane quorum and to let the collection remove the resize
admission guard safely.

The role inspects every host in `kubernetes_upgrade_check_group` (which defaults
to `kubernetes_group`, or `all`) even when Ansible runs with `--limit`. A
missing or unavailable kubelet is recorded as unknown: the admission guard is
retained and denylisted targets are refused, but the unavailable inventory host
does not fail recovery or replacement runs.
