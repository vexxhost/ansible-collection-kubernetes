# Envoy Gateway Role Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable `envoy_gateway` Ansible role that deploys Envoy Gateway and Gateway API CRDs to a Kubernetes cluster, with an optional default GatewayClass.

**Architecture:** Follow the existing Helm-based role pattern (cert_manager, cilium). Vendor the Envoy Gateway Helm chart into `roles/envoy_gateway/files/chart/`. Deploy via `kubernetes.core.helm` module with configurable values and image overrides. The Envoy Gateway Helm chart bundles Gateway API CRDs. The role optionally creates a GatewayClass resource. Downstream consumers (e.g., Atmosphere) create their own Gateway, HTTPRoute, and policy resources.

**Tech Stack:** Ansible, Helm, Kubernetes, Envoy Gateway v1.7.0, Gateway API CRDs

**Spec:** `docs/superpowers/specs/2026-03-11-envoy-gateway-migration-design.md`

---

## File Structure

```
roles/envoy_gateway/
├── defaults/main.yml          # User-overridable: version, images, chart paths, helm values
├── vars/main.yml              # Internal: _envoy_gateway_helm_values (merged with user overrides)
├── meta/main.yml              # Role metadata + upload_helm_chart dependency
├── tasks/main.yml             # Deploy Helm chart + optional GatewayClass
├── templates/
│   └── gatewayclass.yml.j2    # Optional GatewayClass resource template
├── files/
│   └── chart/                 # Vendored Envoy Gateway Helm chart (v1.7.0)
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
└── README.md                  # Role documentation
```

Modified files:
- `.charts.yml` — Add envoy-gateway chart entry
- `renovate.json` — Add `roles/envoy_gateway/files/chart/**` to `ignorePaths`

> **Design note (spec deviation):** The spec lists `templates/values.yml.j2` in the
> file structure. This plan uses `vars/main.yml` instead, following the `cert_manager`
> role pattern which is the newer convention in this repo. The `cilium` role uses
> `templates/values.yml.j2` but that's the older pattern. Both work identically.

---

## Chunk 1: Vendor Helm Chart and Create Role Structure

### Task 1: Vendor the Envoy Gateway Helm chart

**Files:**
- Create: `roles/envoy_gateway/files/chart/` (entire directory from Helm pull)

- [ ] **Step 1: Pull the Envoy Gateway Helm chart from OCI registry**

```bash
cd /home/mnaser/src/github.com/vexxhost/ansible-collection-kubernetes
mkdir -p roles/envoy_gateway/files
helm pull oci://docker.io/envoyproxy/gateway-helm \
  --version v1.7.0 \
  --untar \
  --untardir roles/envoy_gateway/files
mv roles/envoy_gateway/files/gateway-helm roles/envoy_gateway/files/chart
```

Expected: `roles/envoy_gateway/files/chart/` directory containing `Chart.yaml`, `values.yaml`, `templates/`, etc.

- [ ] **Step 2: Verify the chart structure and CRD bundling**

```bash
ls roles/envoy_gateway/files/chart/
cat roles/envoy_gateway/files/chart/Chart.yaml | head -20
```

Expected: Standard Helm chart with `name: gateway-helm`.

Verify Gateway API CRDs are bundled:

```bash
ls roles/envoy_gateway/files/chart/crds/ 2>/dev/null || \
  grep -r 'gateway.networking.k8s.io' roles/envoy_gateway/files/chart/templates/ | head -5
```

The Envoy Gateway chart bundles Gateway API CRDs. If they are NOT bundled, a separate
CRD installation step must be added (see fallback in Task 5).

- [ ] **Step 3: Record image references from the chart**

```bash
grep -E 'repository:|tag:|image:' roles/envoy_gateway/files/chart/values.yaml
```

Save this output — it determines the exact variable names for `defaults/main.yml`
and `vars/main.yml` in the next tasks. The values.yaml structure dictates the
Helm override keys.

- [ ] **Step 4: Commit the vendored chart**

```bash
git add roles/envoy_gateway/files/chart/
git commit -s -m "feat(envoy_gateway): vendor Envoy Gateway Helm chart v1.7.0

Vendor the official Envoy Gateway Helm chart from
oci://docker.io/envoyproxy/gateway-helm for use in the
envoy_gateway role. The chart bundles Gateway API CRDs.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Create role defaults

**Files:**
- Create: `roles/envoy_gateway/defaults/main.yml`

**Prerequisite:** Task 1 Step 3 output (image references from chart values.yaml).

- [ ] **Step 1: Create defaults/main.yml**

Follow the pattern from `roles/cert_manager/defaults/main.yml`. Include:
- Helm chart path/ref/release config
- Image tag and image variables (names from Task 1 Step 3)
- Envoy data plane image (for downstream override even though it's configured via CRD)
- Node selector
- GatewayClass configuration variables

```yaml
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

---
envoy_gateway_helm_chart_path: "chart/"
envoy_gateway_helm_chart_ref: /usr/local/src/envoy-gateway

envoy_gateway_helm_release_name: envoy-gateway
envoy_gateway_helm_release_namespace: envoy-gateway-system
envoy_gateway_helm_values: {}

envoy_gateway_node_selector: {}

envoy_gateway_version: "v1.7.0"
envoy_gateway_image: "docker.io/envoyproxy/gateway:{{ envoy_gateway_version }}"
envoy_gateway_image_certgen: "docker.io/envoyproxy/gateway:{{ envoy_gateway_version }}"

# Data plane Envoy proxy image (used by downstream in EnvoyProxy CRD, not by this chart)
envoy_gateway_envoy_image: "docker.io/envoyproxy/envoy:distroless-v1.33.1"

# Optional GatewayClass creation
envoy_gateway_gateway_class_name: ""
```

> **IMPORTANT:** After vendoring the chart (Task 1), verify image names match
> the chart's `values.yaml`. Adjust `envoy_gateway_image` and
> `envoy_gateway_image_certgen` if the chart uses different image references.
> The `envoy_gateway_envoy_image` version must match what this Envoy Gateway
> version expects — check the chart's default EnvoyProxy image.

- [ ] **Step 2: Commit**

```bash
git add roles/envoy_gateway/defaults/main.yml
git commit -s -m "feat(envoy_gateway): add role defaults

Define user-overridable defaults for Envoy Gateway version, image
references, Helm release configuration, node selector, and optional
GatewayClass name.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Create role vars (internal Helm values)

**Files:**
- Create: `roles/envoy_gateway/vars/main.yml`

**Prerequisite:** Task 1 Step 3 output (chart values.yaml structure).

- [ ] **Step 1: Read the vendored chart's values.yaml in full**

```bash
cat roles/envoy_gateway/files/chart/values.yaml
```

Identify the EXACT keys for:
- Control plane image (repository + tag)
- Certgen job image (repository + tag)
- Pod nodeSelector
- Any other image references

- [ ] **Step 2: Create vars/main.yml using EXACT chart keys**

Follow the pattern from `roles/cert_manager/vars/main.yml`. Use the
`vexxhost.kubernetes.docker_image` filter for image references. The
`_envoy_gateway_helm_values` variable uses an underscore prefix to indicate
it's internal and will be merged with user overrides.

Write the file using the EXACT key paths from Step 1. Example structure
(adjust to match actual chart values.yaml):

```yaml
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

---
_envoy_gateway_helm_values:
  deployment:
    envoyGateway:
      image:
        repository: "{{ envoy_gateway_image | vexxhost.kubernetes.docker_image('name') }}"
        tag: "{{ envoy_gateway_image | vexxhost.kubernetes.docker_image('tag') }}"
    pod:
      nodeSelector: "{{ envoy_gateway_node_selector }}"
  certgen:
    job:
      image:
        repository: "{{ envoy_gateway_image_certgen | vexxhost.kubernetes.docker_image('name') }}"
        tag: "{{ envoy_gateway_image_certgen | vexxhost.kubernetes.docker_image('tag') }}"
```

> The YAML structure above is a template based on common Envoy Gateway chart
> layouts. You MUST verify each key path matches the vendored chart's
> `values.yaml` from Step 1. If keys differ, use the chart's actual keys.

- [ ] **Step 3: Commit**

```bash
git add roles/envoy_gateway/vars/main.yml
git commit -s -m "feat(envoy_gateway): add internal Helm values

Define internal Helm values with image overrides using the
docker_image filter. These are merged with user-provided
envoy_gateway_helm_values at deploy time.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Create role metadata (meta/main.yml)

**Files:**
- Create: `roles/envoy_gateway/meta/main.yml`

- [ ] **Step 1: Create meta/main.yml**

Follow the pattern from `roles/cert_manager/meta/main.yml`. Declare the
`upload_helm_chart` dependency which syncs the vendored chart to target nodes.

```yaml
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

---
galaxy_info:
  author: VEXXHOST, Inc.
  description: Ansible role for Envoy Gateway
  license: Apache-2.0
  min_ansible_version: 5.5.0
  standalone: false
  platforms:
    - name: EL
      versions:
        - "8"
        - "9"
    - name: Ubuntu
      versions:
        - focal
        - jammy

dependencies:
  - role: vexxhost.kubernetes.upload_helm_chart
    vars:
      upload_helm_chart_src: "{{ envoy_gateway_helm_chart_path }}"
      upload_helm_chart_dest: "{{ envoy_gateway_helm_chart_ref }}"
```

- [ ] **Step 2: Commit**

```bash
git add roles/envoy_gateway/meta/main.yml
git commit -s -m "feat(envoy_gateway): add role metadata

Declare role metadata and upload_helm_chart dependency for
syncing the vendored chart to target nodes.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Create role tasks (tasks/main.yml) and GatewayClass template

**Files:**
- Create: `roles/envoy_gateway/tasks/main.yml`
- Create: `roles/envoy_gateway/templates/gatewayclass.yml.j2`

- [ ] **Step 1: Create tasks/main.yml**

Follow the pattern from `roles/cert_manager/tasks/main.yml`. Deploy the Helm
chart with merged values. Then optionally create a GatewayClass if
`envoy_gateway_gateway_class_name` is set.

```yaml
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

---
- name: Deploy Helm chart
  run_once: true
  kubernetes.core.helm:
    name: "{{ envoy_gateway_helm_release_name }}"
    chart_ref: "{{ envoy_gateway_helm_chart_ref }}"
    release_namespace: "{{ envoy_gateway_helm_release_namespace }}"
    create_namespace: true
    kubeconfig: /etc/kubernetes/admin.conf
    values: "{{ _envoy_gateway_helm_values | combine(envoy_gateway_helm_values, recursive=True) }}"

- name: Create GatewayClass
  run_once: true
  kubernetes.core.k8s:
    state: present
    kubeconfig: /etc/kubernetes/admin.conf
    definition: "{{ lookup('ansible.builtin.template', 'gatewayclass.yml.j2') | from_yaml }}"
  when: envoy_gateway_gateway_class_name | length > 0
```

- [ ] **Step 2: Create templates/gatewayclass.yml.j2**

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: "{{ envoy_gateway_gateway_class_name }}"
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
```

- [ ] **Step 3: Commit**

```bash
git add roles/envoy_gateway/tasks/main.yml roles/envoy_gateway/templates/gatewayclass.yml.j2
git commit -s -m "feat(envoy_gateway): add deployment tasks and GatewayClass template

Deploy Envoy Gateway via Helm chart with merged internal and
user-provided values. Optionally create a GatewayClass resource
when envoy_gateway_gateway_class_name is set.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Chunk 2: Configuration, Documentation, and Verification

### Task 6: Update .charts.yml and renovate.json

**Files:**
- Modify: `.charts.yml`
- Modify: `renovate.json`

- [ ] **Step 1: Update .charts.yml**

`.charts.yml` is currently orphaned (not consumed by any automation in this repo)
but serves as documentation of vendored chart sources. Add the Envoy Gateway
entry for consistency.

```yaml
---
charts:
  - name: cert-manager
    directory: chart
    version: 1.11.5
    repository:
      url: https://charts.jetstack.io
  - name: gateway-helm
    directory: chart
    version: v1.7.0
    repository:
      url: oci://docker.io/envoyproxy/gateway-helm
```

- [ ] **Step 2: Update renovate.json**

Add the vendored chart directory to `ignorePaths` to prevent Renovate from
interfering with the vendored chart (same pattern as cilium).

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "local>vexxhost/.github"
  ],
  "ignorePaths": [
    "roles/cilium/files/chart/**",
    "roles/envoy_gateway/files/chart/**"
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add .charts.yml renovate.json
git commit -s -m "chore(envoy_gateway): add chart tracking and renovate ignore

Add Envoy Gateway to .charts.yml for chart source documentation
and to renovate.json ignorePaths to prevent interference with
the vendored chart directory.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Create role README

**Files:**
- Create: `roles/envoy_gateway/README.md`

- [ ] **Step 1: Create README.md**

```markdown
# Envoy Gateway

This role deploys [Envoy Gateway](https://gateway.envoyproxy.io/) to a
Kubernetes cluster using the official Helm chart.

Envoy Gateway is a Gateway API implementation built on the Envoy proxy.
It provides a standardized way to manage ingress traffic using Gateway API
resources (Gateway, HTTPRoute, GRPCRoute, TCPRoute, etc.).

## Role Variables

| Variable | Default | Description |
|---|---|---|
| `envoy_gateway_helm_release_name` | `envoy-gateway` | Helm release name |
| `envoy_gateway_helm_release_namespace` | `envoy-gateway-system` | Target namespace |
| `envoy_gateway_helm_values` | `{}` | User-provided Helm value overrides |
| `envoy_gateway_node_selector` | `{}` | Node selector for control plane pods |
| `envoy_gateway_version` | `v1.7.0` | Envoy Gateway version |
| `envoy_gateway_envoy_image` | `docker.io/envoyproxy/envoy:...` | Envoy data plane image (for downstream EnvoyProxy CRD) |
| `envoy_gateway_gateway_class_name` | `""` | GatewayClass name to create (empty = skip) |

## Usage

```yaml
- hosts: kubernetes_control_plane
  roles:
    - role: vexxhost.kubernetes.envoy_gateway
      vars:
        envoy_gateway_node_selector:
          node-role.kubernetes.io/control-plane: ""
        envoy_gateway_gateway_class_name: my-gateway
```

## Gateway API CRDs

The Envoy Gateway Helm chart bundles Gateway API CRDs. No separate CRD
installation is required.

## Gateway API Resources

This role deploys the Envoy Gateway control plane and Gateway API CRDs.
If `envoy_gateway_gateway_class_name` is set, it also creates a GatewayClass.
Downstream consumers create their own Gateway API resources:

- `Gateway` — Defines listeners (ports, protocols, TLS)
- `HTTPRoute` — Routes HTTP traffic to backends
- `TCPRoute` / `UDPRoute` — Routes L4 traffic
- `BackendTLSPolicy` — Backend TLS configuration
- `SecurityPolicy` — CORS, auth, IP allowlisting (Envoy Gateway extension)
- `BackendTrafficPolicy` — Timeouts, body size limits (Envoy Gateway extension)
- `EnvoyProxy` — Data plane deployment configuration (DaemonSet, hostNetwork, etc.)
```

- [ ] **Step 2: Commit**

```bash
git add roles/envoy_gateway/README.md
git commit -s -m "docs(envoy_gateway): add role README

Document role variables, usage example, CRD bundling, and
Gateway API resource model for downstream consumers.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Final verification

- [ ] **Step 1: Verify role file structure**

```bash
find roles/envoy_gateway -type f -not -path '*/chart/*' | sort
```

Expected output:
```
roles/envoy_gateway/README.md
roles/envoy_gateway/defaults/main.yml
roles/envoy_gateway/meta/main.yml
roles/envoy_gateway/tasks/main.yml
roles/envoy_gateway/templates/gatewayclass.yml.j2
roles/envoy_gateway/vars/main.yml
```

- [ ] **Step 2: Verify chart directory exists**

```bash
test -f roles/envoy_gateway/files/chart/Chart.yaml && echo "OK" || echo "MISSING"
test -f roles/envoy_gateway/files/chart/values.yaml && echo "OK" || echo "MISSING"
```

Expected: Both OK.

- [ ] **Step 3: Verify Ansible can parse all YAML files**

```bash
cd /home/mnaser/src/github.com/vexxhost/ansible-collection-kubernetes
python -c "import yaml; yaml.safe_load(open('roles/envoy_gateway/defaults/main.yml'))"
python -c "import yaml; yaml.safe_load(open('roles/envoy_gateway/vars/main.yml'))"
python -c "import yaml; yaml.safe_load(open('roles/envoy_gateway/meta/main.yml'))"
python -c "import yaml; yaml.safe_load(open('roles/envoy_gateway/tasks/main.yml'))"
```

Expected: No errors (all valid YAML).

- [ ] **Step 4: Consistency checks**

Verify these match:
- `envoy_gateway_version` in `defaults/main.yml` matches vendored `Chart.yaml` appVersion
- `_envoy_gateway_helm_values` keys in `vars/main.yml` match the chart's `values.yaml` structure
- `upload_helm_chart` vars in `meta/main.yml` reference the correct defaults variables
- `envoy_gateway_envoy_image` tag is compatible with the vendored Envoy Gateway version

```bash
# Check version consistency
grep 'version' roles/envoy_gateway/defaults/main.yml
grep -i 'version\|appVersion' roles/envoy_gateway/files/chart/Chart.yaml

# Check helm value keys exist in chart
KEYS=$(grep -oP '^\s+\w+:' roles/envoy_gateway/vars/main.yml | tr -d ' :' | head -5)
for key in $KEYS; do
  grep -q "$key" roles/envoy_gateway/files/chart/values.yaml && \
    echo "OK: $key found in chart values" || \
    echo "WARN: $key NOT found in chart values"
done
```

- [ ] **Step 5: Verify git log**

```bash
git --no-pager log --oneline feat/envoy-gateway --not main | head -15
```

Expected: All commits from this implementation on the `feat/envoy-gateway` branch.
