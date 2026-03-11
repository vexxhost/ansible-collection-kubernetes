# Envoy Gateway Migration Design Spec

## Problem Statement

ingress-nginx is being archived in March 2026 with no further security patches.
The Atmosphere project relies heavily on ingress-nginx deployed as a DaemonSet with
`hostNetwork: true` on ports 80/443. We need a replacement that is:

1. **Truly open source** — no risk of a single company pulling the rug
2. **Available now** — no waiting for unreleased versions
3. **Gateway API native** — enables future migration from Ingress to Gateway API
4. **Feature-complete** — covers all nginx annotations used in Atmosphere

## Decision

**Envoy Gateway** is the chosen replacement.

### Why Envoy Gateway

| Criterion | Envoy Gateway |
|---|---|
| **Proxy engine** | Envoy (CNCF Graduated, battle-tested at Google/Lyft) |
| **Project status** | CNCF project, multi-org governance |
| **Governance** | Steering committee: Envoy Core, Tetrate, SAP, Ambassador Labs, Tencent |
| **Gateway API** | Purpose-built, full conformance |
| **DaemonSet + hostNetwork** | Fully supported via EnvoyProxy CRD |
| **Available now** | Yes — v1.7.0 (Feb 2026) |
| **Legacy Ingress support** | No — Gateway API only |

### Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| **Cilium Ingress** | Dual-port hostNetwork fix (PR #44447) not yet released (needs 1.19.2). Zero nginx annotation compat. Couples CNI + ingress blast radius. |
| **Contour** | CNCF Incubating but Broadcom-dominated governance after VMware acquisition. |
| **Traefik** | Single-company governance risk (Traefik Labs). Partial nginx annotation compat (~80%). |
| **Keep ingress-nginx** | Being archived, no security patches after March 2026. |

## Architecture

### Deployment Model

Envoy Gateway runs two components:

1. **Control plane** (`envoy-gateway`) — Deployment in `envoy-gateway-system` namespace.
   Watches Gateway API resources and configures Envoy proxies.
2. **Data plane** (`envoy-proxy`) — DaemonSet with `hostNetwork: true` on ports 80/443.
   Runs on nodes labeled `openstack-control-plane: enabled`.

```
┌─────────────────────────────────────────────┐
│  envoy-gateway-system namespace             │
│                                             │
│  ┌─────────────────┐   ┌─────────────────┐  │
│  │  envoy-gateway   │   │  envoy-proxy    │  │
│  │  (Deployment)    │──▶│  (DaemonSet)    │  │
│  │  Control plane   │   │  hostNetwork    │  │
│  └─────────────────┘   │  :80 :443       │  │
│                         └─────────────────┘  │
└─────────────────────────────────────────────┘
```

### Gateway API Resource Model

Replace Ingress resources with standardized Gateway API resources:

```
GatewayClass (atmosphere)
  └── Gateway (atmosphere)
        ├── Listener :80  (HTTP → HTTPS redirect)
        ├── Listener :443 (HTTPS, TLS termination)
        ├── Listener :5354 (TCP, DNS forwarding)
        └── HTTPRoute (per-service)
              ├── Rules (path matching, rewriting)
              └── Filters (headers, URL rewrite)

BackendTLSPolicy (per-service needing backend HTTPS)
BackendTrafficPolicy (timeouts, body size limits)
SecurityPolicy (CORS, auth, IP allowlisting)
```

## Nginx Annotation Migration Map

Every nginx annotation currently used in Atmosphere has a Gateway API equivalent:

### Body Size & Buffering

```yaml
# BEFORE (nginx annotation)
nginx.ingress.kubernetes.io/proxy-body-size: "0"
nginx.ingress.kubernetes.io/proxy-request-buffering: "off"

# AFTER (Envoy Gateway BackendTrafficPolicy)
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: glance-upload
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: glance
  requestBuffer:
    limit: "0"  # unlimited
```

> **Note:** `proxy-request-buffering: "off"` has no direct Gateway API equivalent.
> Envoy streams request bodies by default (no buffering), so the nginx behavior of
> disabling buffering is the default in Envoy. No additional configuration needed.

### Timeouts

```yaml
# BEFORE
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"

# AFTER (Gateway API native + BackendTrafficPolicy)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: nova-novncproxy
spec:
  rules:
    - timeouts:
        backendRequest: "3600s"
---
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: nova-timeouts
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: nova-novncproxy
  timeout:
    http:
      connectionIdleTimeout: "3600s"
      requestTimeout: "3600s"
```

### CORS

```yaml
# BEFORE
nginx.ingress.kubernetes.io/enable-cors: "true"
nginx.ingress.kubernetes.io/cors-allow-origin: "https://horizon.example.com"

# AFTER (Envoy Gateway SecurityPolicy)
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: horizon-cors
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: horizon
  cors:
    allowOrigins:
      - type: Exact
        value: "https://horizon.example.com"
    allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowHeaders: ["*"]
```

### Backend TLS (HTTPS backends)

```yaml
# BEFORE
nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"

# AFTER (Gateway API BackendTLSPolicy)
apiVersion: gateway.networking.k8s.io/v1
kind: BackendTLSPolicy
metadata:
  name: placement-tls
spec:
  targetRefs:
    - group: ""
      kind: Service
      name: placement-api
  validation:
    caCertificateRefs:
      - name: placement-ca
        group: ""
        kind: ConfigMap
    hostname: placement-api.openstack.svc
```

### URL Rewriting

```yaml
# BEFORE
nginx.ingress.kubernetes.io/rewrite-target: /

# AFTER (HTTPRoute filter)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
spec:
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /identity
      filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
      backendRefs:
        - name: keystone-api
          port: 5000
```

### IP Allowlisting

```yaml
# BEFORE
nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8"

# AFTER (Envoy Gateway SecurityPolicy)
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: allow-internal
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: admin-api
  authorization:
    defaultAction: Deny
    rules:
      - action: Allow
        principal:
          clientCIDRs:
            - "10.0.0.0/8"
```

### Basic Auth

```yaml
# BEFORE
nginx.ingress.kubernetes.io/auth-type: basic
nginx.ingress.kubernetes.io/auth-secret: my-secret

# AFTER (Envoy Gateway SecurityPolicy)
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: basic-auth
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: protected-route
  basicAuth:
    users:
      group: ""
      kind: Secret
      name: my-secret
```

### Configuration/Server Snippets

```yaml
# BEFORE
nginx.ingress.kubernetes.io/configuration-snippet: |
  proxy_set_header X-Custom "value";

# AFTER — no snippets; decompose into specific Gateway API features:
# - Header modification → HTTPRoute RequestHeaderModifier filter
# - Custom Envoy config → EnvoyPatchPolicy (escape hatch)
```

> **Note on snippets:** The actual `configuration-snippet` and `server-snippet` content
> used in Atmosphere must be audited during Phase 2. Each snippet must be decomposed
> into its constituent features (header manipulation, proxy settings, etc.) and mapped
> to the appropriate Gateway API resource or EnvoyPatchPolicy. This is an unquantified
> risk that will be resolved during the parallel deployment phase.

### WebSocket Support (Nova noVNC)

Nova noVNC requires WebSocket upgrade support with long-lived connections.
Nginx handles this implicitly with `proxy_http_version 1.1` and `Upgrade` headers.
Envoy requires explicit route-level configuration:

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: nova-websocket
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: nova-novncproxy
  timeout:
    http:
      connectionIdleTimeout: "3600s"
      requestTimeout: "3600s"
---
# WebSocket upgrades are enabled by default in Envoy Gateway.
# Envoy Gateway automatically configures upgrade_configs for websocket
# on all HTTP routes. No additional configuration is needed unless
# custom upgrade types are required.
```

### TCP/UDP Port Forwarding (DNS 5354)

```yaml
# BEFORE (nginx tcp-services ConfigMap)
data:
  "5354": "openstack/minidns:5354"

# AFTER (Gateway TCPRoute)
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: TCPRoute
metadata:
  name: minidns
spec:
  parentRefs:
    - name: atmosphere
      sectionName: dns-tcp
  rules:
    - backendRefs:
        - name: minidns
          namespace: openstack
          port: 5354
```

## Scope of Change

### Separation of Concerns

This collection (`vexxhost.kubernetes`) provides **generic, reusable Ansible roles**
for deploying Kubernetes infrastructure components. It is consumed by downstream
projects like Atmosphere. The collection must NOT contain downstream-specific
configuration (e.g., OpenStack service routes, specific policies).

- **This collection** → deploys Envoy Gateway + Gateway API CRDs. Provides the
  infrastructure. Analogous to how `roles/cilium/` deploys Cilium without knowing
  what workloads will use it.
- **Downstream (Atmosphere)** → creates Gateway, HTTPRoute, SecurityPolicy, etc.
  resources specific to its OpenStack services. This is NOT in scope for this
  collection.

### This Collection (ansible-collection-kubernetes)

Add a new `envoy_gateway` role following the existing pattern:

```
roles/envoy_gateway/
├── defaults/main.yml          # Version, images, Helm config (user-overridable)
├── vars/main.yml              # Internal Helm values (prefixed with _)
├── files/chart/               # Vendored Helm chart
├── meta/main.yml              # Role metadata + upload_helm_chart dependency
├── tasks/main.yml             # Helm deployment
└── templates/values.yml.j2    # Default Helm values template
```

The role follows the existing pattern where:
- `vars/main.yml` defines `_envoy_gateway_helm_values` (internal defaults)
- `defaults/main.yml` defines `envoy_gateway_helm_values: {}` (user overrides)
- Task merges: `_envoy_gateway_helm_values | combine(envoy_gateway_helm_values, recursive=True)`
- `meta/main.yml` declares dependency on `vexxhost.kubernetes.upload_helm_chart`

The role will:
1. Install Gateway API CRDs (via `gateway-crds-helm` chart or bundled)
2. Deploy Envoy Gateway control plane (via `gateway-helm` chart)
3. Optionally create a `GatewayClass` resource (configurable name, defaults)

> The role does NOT create Gateway, HTTPRoute, or policy resources.
> Those are downstream concerns (e.g., Atmosphere creates its own Gateway with
> listeners for :80, :443, :5354 and HTTPRoutes for each OpenStack service).

### Atmosphere (downstream, NOT in scope for this collection)

> The following is documented for context only. These changes belong in
> `vexxhost/atmosphere`, not in this collection.

1. Replace `roles/ingress_nginx/` with a role that uses the `envoy_gateway` role
   from this collection
2. Create `Gateway` resource with listeners for :80, :443, :5354
3. Migrate all OpenStack service Ingress resources to `HTTPRoute` + policies
4. Update `helm-toolkit` `_ingress.tpl` to generate `HTTPRoute` instead of `Ingress`
5. Remove ingress-nginx Helm chart dependency

## Helm Values Structure

The Helm chart deploys the **control plane** only. The data plane (Envoy proxy
DaemonSet) is configured separately via the `EnvoyProxy` CRD, which the
`GatewayClass` references. This separation is by design in Envoy Gateway.

```yaml
# roles/envoy_gateway/defaults/main.yml
envoy_gateway_helm_release_name: envoy-gateway
envoy_gateway_helm_chart_path: "chart/"
envoy_gateway_helm_chart_ref: /usr/local/src/envoy-gateway
envoy_gateway_helm_release_namespace: envoy-gateway-system
envoy_gateway_helm_values: {}

envoy_gateway_version: "v1.7.0"
envoy_gateway_image: "docker.io/envoyproxy/gateway:{{ envoy_gateway_version }}"
envoy_gateway_envoy_image: "docker.io/envoyproxy/envoy:distroless-v1.33.1"

envoy_gateway_node_selector: {}
```

```yaml
# roles/envoy_gateway/templates/values.yml.j2
# Control plane configuration only
config:
  envoyGateway:
    gateway:
      controllerName: gateway.envoyproxy.io/gatewayclass-controller
```

## EnvoyProxy CRD for DaemonSet + hostNetwork

The **data plane** configuration is done via an `EnvoyProxy` custom resource
referenced by the `GatewayClass`. This is separate from the Helm chart, which
only deploys the control plane.

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: EnvoyProxy
metadata:
  name: atmosphere-proxy
  namespace: envoy-gateway-system
spec:
  provider:
    type: Kubernetes
    kubernetes:
      envoyDaemonSet:
        pod:
          spec:
            hostNetwork: true
            dnsPolicy: ClusterFirstWithHostNet
            nodeSelector:
              openstack-control-plane: enabled
---
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: atmosphere
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
  parametersRef:
    group: gateway.envoyproxy.io
    kind: EnvoyProxy
    name: atmosphere-proxy
    namespace: envoy-gateway-system
---
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: atmosphere
  namespace: openstack
spec:
  gatewayClassName: atmosphere
  listeners:
    - name: http
      protocol: HTTP
      port: 80
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-tls
    - name: dns-tcp
      protocol: TCP
      port: 5354
```

## Migration Strategy

### Phase 1: Add Envoy Gateway Role (this collection)

- Create `roles/envoy_gateway/` with Helm chart deployment
- Vendor the Envoy Gateway Helm chart
- Add Gateway API CRD installation
- No removal of any existing functionality

### Phase 2: Deploy Alongside ingress-nginx (Atmosphere)

- Deploy Envoy Gateway in parallel with ingress-nginx
- Create GatewayClass + Gateway resources
- Migrate one service (e.g., Keystone) to HTTPRoute as proof of concept
- Validate feature parity

### Phase 3: Full Migration (Atmosphere)

- Migrate all OpenStack services from Ingress to HTTPRoute
- Update helm-toolkit templates
- Add BackendTrafficPolicy/SecurityPolicy resources as needed
- Switch DNS to point to Envoy Gateway
- Remove ingress-nginx

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Envoy Gateway v1alpha1 policy APIs may change | Pin version, test upgrades in CI |
| BackendTLSPolicy is relatively new in GA | Core Gateway API feature with broad controller support |
| `configuration-snippet` has no direct equivalent | Audit all snippets; use EnvoyPatchPolicy as escape hatch |
| Envoy Gateway is newer than ingress-nginx | Envoy proxy itself is battle-tested; Gateway is the control plane |
| Parallel deployment complexity | Phase 2 allows side-by-side validation before cutover |

## Success Criteria

1. Envoy Gateway role deploys and creates a functioning GatewayClass
2. DaemonSet runs on hostNetwork with ports 80 and 443
3. HTTPRoute can serve HTTPS traffic with cert-manager certificates
4. All 14 nginx annotations have working Gateway API equivalents
5. TCP forwarding works for port 5354 (DNS)
6. No ingress-nginx dependency remains after Phase 3
