# Cluster API Add-on Provider for Helm v0.6.4

- Upstream tag commit: `825662962a26dc339f3871184c91ed4bd2f83a4f`
- Kustomize version: `v5.7.0`
- Source command: `kustomize build config/default`
- Controller manifest-list digest:
  `sha256:97d2a86f8e35d23bb4656b26f4564b35f109e47a0dc4860b71089e52eb6e6a24`

The generated manifest differs from the upstream release generator only by
using the accepted production controller manifest digest directly instead of
the mutable release tag.
