# Kubernetes upgrades

Set `kubernetes_version` to an exact patch release in the next minor, then run
one playbook for the complete inventory:

```console
ansible-playbook vexxhost.kubernetes.site -i inventory/hosts.ini
```

Repeat for each intervening minor until the chosen target, selecting a
supported exact patch release at each step. Each invocation handles one minor;
do not skip intermediate Kubernetes minors. Complete the version-specific
prerequisites below before each step.

## Upgrade lifecycle

Controllers are reconciled serially. The stored cluster version decides whether
`upgrade apply` is needed; each controller's three component manifests decide
whether its `upgrade node` remains necessary. A rerun therefore finishes peers
even if an interrupted run already recorded the target cluster version.

The kubelet loop remains serial and keeps running containers. Controller
kubelets refresh only kubeadm's `kubelet-config` phase, rather than repeating
the control-plane/add-on upgrade. Rescue starts a failed kubelet before
propagating the failure. All site plays stop on fatal errors.

## Compatibility by target version

| Target | Managed compatibility |
| --- | --- |
| 1.34 | Prepare the etcd 3.5-to-3.6 transition before kubeadm changes members; the bridge and data checks are operator prerequisites. |
| 1.35 and later affected releases | Retain the stopped-kubelet resource-checkpoint transition on entry, preserve the native checkpoint on later hops and keep the resize admission guard. Remove obsolete gate overrides and validate target runtime/CRI behavior. |

### Etcd, runtime and resize prerequisites

Before moving local etcd from 3.5 to 3.6, update every member to 3.5.32 or
later and verify that legacy v2 data does not block the transition. Follow the
[etcd upgrade procedure](https://etcd.io/docs/v3.6/upgrades/upgrade_3_6/),
including snapshot and WAL checks with a compatible `etcdutl`. Check protected
offline data copies, never run the checker against the live data directory,
and stop for custom data or an unexpected result. Keep verified backups.

Before starting the target kubelet, qualify its container runtime and CRI
behavior with both existing workloads and a new pod with init containers.
Persist the accepted runtime version and checksum so role dependencies cannot
select an older default. Preserve runtime configuration and runc behavior;
perform any required runtime intermediate upgrades as a separate controlled
operation. This workflow does not automatically implement that runtime path.

On nodes using legacy QoS cgroup settings, retain the collection's checkpoint
transition before the first 1.35 kubelet startup and verify the resulting
resource records. Preserve the kubelet-owned checkpoint on subsequent hops.
Retain the resize admission guard on affected releases: successful startup
does not make explicit in-place resize safe. Honor patch-specific denylist checks
and follow the [pod QoS cgroup procedure](qos-cgroups.md); do not bypass a
denied patch or combine a cgroup migration with a minor upgrade.

Keep the collection's managed `InPlacePodVerticalScaling: false` behavior for
1.33/1.34 nodes with legacy QoS cgroup settings. Do not combine a cgroup
migration with the version bump. For later affected releases, follow the
[pod QoS cgroup procedure](qos-cgroups.md) and the resize upgrade guard.

The playbook does not perform a complete runtime/etcd migration or establish
integrated HA application continuity. Complete the prerequisite operations
and qualify the exact collection, addon and runtime combination before rollout;
monitor service traffic throughout each minor upgrade.
