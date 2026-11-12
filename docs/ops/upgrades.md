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

The role retains an authenticated etcd snapshot on the bootstrap controller
and a checksum-verified copy under `kubernetes_etcd_snapshot_directory` on the
Ansible controller before changing the stored configuration. Snapshot files
and directories are private. Manage retention outside the upgrade operation.
External etcd deployments need their own backup procedure.

The image repository is reconciled into the stored ClusterConfiguration before
upgrading. Previously a new `kubernetes_image_repository` only changed the init
file, while kubeadm continued reading an old cluster/CoreDNS registry from its
ConfigMap. The reconciliation owns only `imageRepository` and
`dns.imageRepository`; it preserves DNS image tags, disabled state, networking,
certificate settings and explicit etcd overrides. Returning to the normal
registry replaces a stale mirror with the target kubeadm version's defaults.
Confirm target images and registry credentials are available before upgrading.

### Proxy-free state is more than resource deletion

When `kubernetes_remove_kube_proxy: true`, kubeadm's stored configuration must
retain `proxy.disabled: true` on supported schemas before addons reconcile.
The role migrates older configuration with kubeadm and reads the value back.
It also checks every targeted node's IPv4/IPv6 host rules before application
preparation, after controller commands, and at final reconciliation. A
worker-only recovery runs the same host check.

Deleting a kube-proxy DaemonSet or ConfigMap does not remove its kernel rules.
A remaining `KUBE-FORWARD` INVALID drop can precede a replacement CNI's accept
rules and stall a connection after SYN/SYN-ACK. An apparently healthy node or
matching Cilium Helm release does not prove that packet path is clean.
Unexpected proxy resources, writers or owned host rules stop the run before
further disruption. This guard never silently flushes the firewall.

For a reviewed legacy node, first stop unintended proxy writers and establish
that Cilium replacement is healthy. An explicit recovery is available:

```console
ansible reviewed-node -i inventory/hosts.ini --become \
  -m vexxhost.kubernetes.kube_proxy_state -a 'state=absent'
```

Recovery requires a single healthy Cilium agent in replacement mode, saves
root-only originals in a new `/var/tmp/kube-proxy-recovery-*` directory, tests
no-flush transactions and verifies unrelated rules are unchanged. Errors
restore only the owned rules; originals remain for investigation. Other CNIs
require their own reviewed recovery. Kubelet, Cilium, Tailscale and other
firewall owners are preserved. Validate new external service connections
after each recovered node before rerunning the upgrade. The recovery helper
does not claim continuous availability or replace external ingress checks.

These checks inspect the selected iptables backend. IPVS, native nftables
proxy mode and rules in an alternate inactive backend require a separate
audit. Qualify recovery with the deployed firewall and Cilium versions before
use.

Controllers are reconciled serially. The stored cluster version decides whether
`upgrade apply` is needed; each controller's three component manifests decide
whether its `upgrade node` remains necessary. A rerun therefore finishes peers
even if an interrupted run already recorded the target cluster version.

For kube-vip ARP HA, the target controller temporarily leaves the VIP election.
The role waits for another owner, removes only a stale host VIP after the local
kube-vip exits, reconnects only kubelet/Cilium TCP tuples bound to that retired
VIP, and waits for sustained API/lease recovery before gracefully stopping the
old API. The original manifest is restored in `always`; a host watchdog also
restores it after `kubernetes_upgrade_operation_timeout` if Ansible is lost.
Set `kubernetes_upgrade_vip_handoff: false` for a separately managed endpoint.
BGP and single-controller deployments keep the ordinary kubeadm path.

The kubelet loop remains serial and keeps running containers. Controller
kubelets refresh only kubeadm's `kubelet-config` phase, rather than repeating
the control-plane/add-on upgrade. Rescue starts a failed kubelet before
propagating the failure. All site plays stop on fatal errors.

## Compatibility by target version

| Target | Managed compatibility |
| --- | --- |
| 1.29 and 1.30 | Restore CoreDNS placement immediately after either kubeadm control-plane command, then finish its rollout before kubelets. |
| 1.31 | Migrate container hashes while kubelet/containerd are stopped. Follow the newest committed BoltDB tree; inactive pages and old transactions are not live annotations. |
| 1.31 and later | Migrate the stored kubeadm schema when necessary and persist `proxy.disabled` before upgrade when Cilium replaces kube-proxy. |
| 1.31 and later | Keep CoreDNS placement and overlapping rolling updates through the supported `corednsdeployment` patch. |
| 1.33 and later | Preserve a custom, certificate-valid controller kubelet HA endpoint before kubeadm's local-endpoint behavior can restart it. Preserve any existing custom endpoint. |
| 1.34 | Prepare the etcd 3.5-to-3.6 transition before kubeadm changes members; the bridge and data checks are operator prerequisites. |
| 1.35 and later affected releases | Retain the stopped-kubelet resource-checkpoint transition on entry, preserve the native checkpoint on later hops and keep the resize admission guard. Remove obsolete gate overrides and validate target runtime/CRI behavior. |

### Etcd, runtime and resize prerequisites

Before moving local etcd from 3.5 to 3.6, update every member to 3.5.32 or
later and verify that legacy v2 data does not block the transition. Follow the
[etcd upgrade procedure](https://etcd.io/docs/v3.6/upgrades/upgrade_3_6/),
including snapshot and WAL checks with a compatible `etcdutl`. Check protected
offline data copies, never run the checker against the live data directory,
and stop for custom data or an unexpected result. Keep verified backups.
The playbook's normal snapshot does not replace this bridge or data review.

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

The HA hostname defaults to `kubernetes.default.svc.cluster.local`, a standard
API certificate SAN, with an exact hosts-file mapping to the existing VIP.
For another cluster DNS domain, set `kubernetes_kubelet_ha_hostname` accordingly.
The module authenticates the hostname using the current kubelet credentials
before changing files, preserves all other kubeconfig fields, and does not
restart the kubelet during preparation.

CoreDNS uses `maxUnavailable: 0`, `maxSurge: 1` and 15 seconds of readiness
stabilization. The role shares this policy between kubeadm patches and legacy
placement repair; site overrides use the existing
`kubernetes_kubeadm_patches.corednsdeployment.spec` input. The HA address likewise
comes from the existing API VIP settings, without a second address override.
Kubeadm 1.29/1.30 can still overwrite the initial Deployment
before the collection repairs placement: this compatibility path can involve
two rollouts. Overlapping replicas do not establish zero DNS packet loss.
Worker-only recovery skips unrelated CoreDNS reconciliation.

## Application lifecycle integration

`kubernetes_upgrade_lifecycle_role` is empty by default. A consuming deployment
can supply its own role. That role's `prerequisites.yml` runs once
after the existing upgrade preflight and before controller disruption;
worker-only recovery skips it. The `prepare.yml` and `restore.yml` tasks
wrap each controller operation. Their context is `kubernetes_upgrade_host` and
`kubernetes_version`; restoration runs even after a failed preparation or
upgrade. This integration protects applications around controller operations;
it is not a replacement for their normal deployment roles.

Keep the collection's managed `InPlacePodVerticalScaling: false` behavior for
1.33/1.34 nodes with legacy QoS cgroup settings. Do not combine a cgroup
migration with the version bump. For later affected releases, follow the
[pod QoS cgroup procedure](qos-cgroups.md) and the resize upgrade guard.

The playbook does not perform a complete runtime/etcd migration or establish
integrated HA application continuity. Complete the prerequisite operations
and qualify the exact collection, addon and runtime combination before rollout;
monitor service traffic throughout each minor upgrade.
