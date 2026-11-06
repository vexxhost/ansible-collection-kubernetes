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
updates continue to work.  The policy is installed after the control plane is
upgraded and before any existing kubelet is switched to 1.35+, and is removed
when every node uses QoS cgroups or the target version is outside the affected
range.  Like the hard denylist, the guard has one range per Kubernetes minor so
fixed branches can be opened independently.

The admission policy cannot protect against kubelet-initiated resize.  That is
why the automatic-trigger releases remain hard-denied by
`kubernetes_upgrade_check_cgroups_per_qos_denylist` until the upstream panic is
fixed.

Whether a node runs pods in QoS cgroups is read from
`/var/lib/kubelet/kubeadm-flags.env`, `/etc/default/kubelet` and
`/var/lib/kubelet/config.yaml`, together with `kubernetes_kubeadm_extra_args`
(for nodes that have not joined yet) and the `kubeletconfiguration` patch in
`kubernetes_kubeadm_patches`.  Nodes can be moved to QoS cgroups with a drain
and rejoin, which restarts their pods. Follow the supported
[legacy-node migration procedure](../../docs/ops/qos-cgroups.md) to preserve
workload and control-plane quorum and to let the collection remove the resize
admission guard safely.

The role inspects every host in `kubernetes_upgrade_check_group` (which defaults
to `kubernetes_group`, or `all`) even when Ansible runs with `--limit`.  It will
not remove the cluster-wide policy if any of those hosts is unreachable or its
state cannot be determined.
