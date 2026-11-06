# Migrate legacy nodes to pod QoS cgroups

Older releases of this collection joined nodes with
`--cgroups-per-qos=false` and `--enforce-node-allocatable=`. Kubeadm stores
those arguments in `/var/lib/kubelet/kubeadm-flags.env` when a node joins and
does not rewrite the file during an upgrade. Upgrading Kubernetes or rerunning
the collection therefore does not move an existing node to QoS cgroups.

Kubernetes 1.35 makes in-place pod resize generally available and locked on.
On a node without pod QoS cgroups, an in-place resize can crash the kubelet due
to [kubernetes/kubernetes#137993](https://github.com/kubernetes/kubernetes/issues/137993).
The collection blocks API-initiated resize while any affected legacy node
remains, but migrating every node is the permanent remediation. It also allows
the cluster to use patch releases that the upgrade preflight must otherwise
refuse because kubelet-initiated resize cannot be blocked by admission.

Changing this setting changes the cgroup hierarchy used for every pod. The
supported procedure is to drain, reset and rejoin one node at a time. Do not
edit `kubeadm-flags.env` and restart a node in place.

!!! warning

    This migration evicts and restarts every ordinary pod on each node. Draining
    with `--delete-emptydir-data` deletes data stored in `emptyDir` volumes.
    Confirm that PodDisruptionBudgets, local storage and application quorum can
    tolerate each eviction before continuing.

## Requirements

- Use a collection release that includes the `pods/resize` admission guard and
  this procedure. Releases 3.5.0 and later no longer set the legacy arguments
  when a node joins, but 3.5.1 and earlier do not include the admission guard.
- Keep `kubernetes_version` at the cluster's current version for the entire
  migration. Do not combine the cgroup migration with a Kubernetes upgrade.
- Take an etcd backup before changing control-plane nodes.
- Keep the normal deployment inventory and variables available. The collection
  creates fresh join credentials and renders the node's kubeadm configuration
  when it rejoins.
- Migrate only one node at a time and wait for it to become healthy before
  starting the next node.
- For a stacked-etcd control plane, keep an etcd quorum throughout the
  operation. Migrating control-plane nodes this way requires at least three
  healthy control-plane nodes.

!!! danger

    Do not reset the only control-plane node. A single-control-plane cluster has
    no remaining API server or etcd member from which the node can rejoin. Use a
    maintenance rebuild and restore from backup instead. A two-member
    stacked-etcd cluster also loses quorum when either member is stopped; add a
    third member or use a maintenance recovery procedure first.

## Remove legacy overrides

Remove these keys anywhere they are set in inventory:

```yaml
kubernetes_kubeadm_extra_args:
  kubelet:
    cgroups-per-qos: "false"
    enforce-node-allocatable: ""
```

Also remove `cgroupsPerQOS: false` from any
`kubernetes_kubeadm_patches.kubeletconfiguration` override and remove an
equivalent `KUBELET_EXTRA_ARGS` override from `/etc/default/kubelet` or the
system that manages that file. It is not necessary to set
`cgroups-per-qos=true`; omitting the argument uses the kubelet default.

Do not change `kubernetes_kubelet_cgroup_driver` as part of this procedure. The
cgroup driver and pod QoS cgroups are separate settings, and the driver must
continue to match the container runtime.

Check the effective legacy arguments on every node before starting:

```bash
ansible -i inventory/hosts.ini kubernetes --become \
  -m ansible.builtin.command \
  -a 'cat /var/lib/kubelet/kubeadm-flags.env'
```

Use the inventory group that contains all Kubernetes nodes in place of
`kubernetes` when it has a different name. Record the Kubernetes node name for
each inventory host; it may differ when `kubelet_hostname` is customized.

Run the normal deployment playbook in check mode after removing the inventory
overrides. The current version should pass the upgrade preflight without
proposing a Kubernetes version change:

```bash
ansible-playbook -i inventory/hosts.ini deployment.yml \
  --check --diff --tags kubernetes
```

Apply the playbook at the current Kubernetes version before resetting any
node. This renders the collection's current `KubeletConfiguration`, including
`kubernetes_kubelet_cgroup_driver`, on the control-plane hosts:

```bash
ansible-playbook -i inventory/hosts.ini deployment.yml \
  --tags kubernetes
```

Kubeadm join downloads the shared `kubelet-config` ConfigMap. That ConfigMap
can predate the rendered files on disk, because the collection normally
refreshes it during an upgrade and this procedure deliberately does not
upgrade Kubernetes. Refresh it from the first control-plane host before the
first reset/rejoin:

```bash
ansible -i inventory/hosts.ini 'controllers[0]' --become \
  -m ansible.builtin.command \
  -a 'kubeadm init phase upload-config kubelet --config /etc/kubernetes/kubeadm.yaml'

kubectl -n kube-system get configmap kubelet-config \
  -o jsonpath='{.data.kubelet}'
```

Use the actual `kubernetes_control_plane_group` instead of `controllers` when
it differs. In the ConfigMap output, `cgroupDriver` must equal
`kubernetes_kubelet_cgroup_driver` and must match the container runtime before
any node is reset. A stale `cgroupDriver: systemd` with runc using cgroupfs can
make static control-plane pods fail after a rejoin, costing an etcd member
during the migration.

The commands in this guide assume the deployment playbook tags the
`vexxhost.kubernetes.kubernetes` role with `kubernetes`, as the collection
playbook does. Omit `--tags kubernetes` when the deployment playbook does not
use that tag.

Do not override `kubernetes_upgrade_check_cgroups_per_qos_denylist` to force a
version that the preflight refuses. Complete this migration on the current safe
patch release first, then upgrade Kubernetes after every node uses QoS cgroups.

## Migrate a node

Migrate workers first. Migrate control-plane nodes afterwards, leaving the
first host in `kubernetes_control_plane_group` until last because the collection
uses that host as its default API delegate.

Set the inventory host and Kubernetes node name for one node:

```bash
export INVENTORY_HOST=k8s-w1.example.com
export NODE_NAME=k8s-w1.example.com
```

Drain the node. Resolve any PodDisruptionBudget failure instead of bypassing
eviction protection without reviewing the workload impact:

```bash
kubectl drain "$NODE_NAME" \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=15m
```

Reset kubeadm on that host while the rest of the cluster is healthy:

```bash
ansible -i inventory/hosts.ini "$INVENTORY_HOST" --become \
  -m ansible.builtin.command \
  -a 'kubeadm reset --force'
```

For a stacked-etcd control-plane node, `kubeadm reset` also removes its local
etcd member. Confirm the remaining etcd members and API servers are healthy
before proceeding. Stop the migration if quorum or `/readyz` is unhealthy.

Delete the stale Node API object:

```bash
kubectl delete node "$NODE_NAME" --wait=true
kubectl get --raw=/readyz
```

Run the same deployment playbook and variables used for the cluster, limited to
the reset inventory host. The `kubernetes` role sees the missing
`/etc/kubernetes/kubelet.conf`, creates new join credentials and rejoins the
node with the current kubelet defaults:

```bash
ansible-playbook -i inventory/hosts.ini deployment.yml \
  --tags kubernetes \
  --limit "$INVENTORY_HOST"
```

Wait for the node and uncordon it. A newly created Node object is normally
already schedulable, so `uncordon` may report that it was not cordoned:

```bash
kubectl wait --for=condition=Ready "node/$NODE_NAME" --timeout=10m
kubectl uncordon "$NODE_NAME"
kubectl get node "$NODE_NAME" -o wide
```

Verify that the rejoin did not restore either legacy argument:

```bash
ansible -i inventory/hosts.ini "$INVENTORY_HOST" --become \
  -m ansible.builtin.command \
  -a 'cat /var/lib/kubelet/kubeadm-flags.env'
```

The output must not contain `--cgroups-per-qos=false` or
`--enforce-node-allocatable=`. If `/var/lib/kubelet/config.yaml` explicitly
contains `cgroupsPerQOS`, it must be `true`. Confirm that replacement workload
pods become Ready and that the kubelet has not entered a restart loop before
moving to the next node.

Check the effective kubelet configuration through the API after every rejoin:

```bash
kubectl get --raw="/api/v1/nodes/$NODE_NAME/proxy/configz" \
  | jq '.kubeletconfig | {cgroupsPerQOS, cgroupDriver}'
```

`cgroupsPerQOS` must be `true`. Then inspect the containerd runtime selected
for pods on the rejoined host:

```bash
ansible -i inventory/hosts.ini "$INVENTORY_HOST" --become \
  -m ansible.builtin.command \
  -a 'crictl info -o json'
```

In that JSON, find
`config.containerd.runtimes[config.containerd.defaultRuntimeName].options.SystemdCgroup`.
It must be `true` when the kubelet reports `cgroupDriver: systemd`, and `false`
when the kubelet reports `cgroupDriver: cgroupfs`. Stop before uncordoning the
node if they disagree. Do not rely on a newer container runtime overriding a
stale kubelet ConfigMap; the migration must also be safe on containerd 1.7.

For each control-plane node, additionally check the API and local etcd pod after
the rejoin:

```bash
kubectl get --raw=/readyz
kubectl -n kube-system get pods -l component=etcd -o wide
```

## Finish the migration

After every node has rejoined, run the Kubernetes play for the full inventory
in check mode and then apply it:

```bash
ansible-playbook -i inventory/hosts.ini deployment.yml \
  --check --diff --tags kubernetes

ansible-playbook -i inventory/hosts.ini deployment.yml \
  --tags kubernetes
```

The full run verifies every inventory node. On an affected Kubernetes release,
it removes the resize admission policy only after all nodes are confirmed to
use QoS cgroups. Verify cluster health and that no guard remains:

```bash
kubectl get nodes
kubectl get pods --all-namespaces
kubectl get --raw=/readyz
kubectl get validatingadmissionpolicy,validatingadmissionpolicybinding \
  vexxhost-kubelet-resize-guard --ignore-not-found
```

The final command must return no guard resources. Kubernetes upgrades that were
previously refused by the QoS-cgroup preflight can now be performed normally.
A VPA configured with `InPlaceOrRecreate` can fall back to evicting and
recreating pods while the guard is installed; after the guard is removed,
eligible pods can use in-place resize again.

## Recover a failed node

Do not continue to another node when reset, join or health verification fails.
Leave the failed node drained and diagnose it while the rest of the cluster is
healthy. The rejoin is repeatable after another `kubeadm reset --force` and
Node deletion.

To return a node to its previous configuration, restore both legacy kubelet
arguments in that host's inventory, reset it again and rerun the limited rejoin.
Do not uncordon it until it is Ready and its previous kubelet behavior has been
verified. For a failed control-plane rejoin, verify etcd membership and restore
from the pre-migration backup when the member cannot be added safely.
