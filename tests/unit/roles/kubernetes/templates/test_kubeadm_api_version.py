# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubeadm configuration API version in kubeadm.yaml.j2."""

import pytest


@pytest.mark.parametrize(
    "version,api_version",
    [
        ("1.21.14", "kubeadm.k8s.io/v1beta2"),
        ("1.30.14", "kubeadm.k8s.io/v1beta3"),
        ("1.31.14", "kubeadm.k8s.io/v1beta4"),
        ("1.36.2", "kubeadm.k8s.io/v1beta4"),
    ],
)
def test_api_version(render_kubeadm, version, api_version):
    documents = render_kubeadm(kubernetes_version=version)

    for kind in ("InitConfiguration", "JoinConfiguration", "ClusterConfiguration"):
        assert documents[kind]["apiVersion"] == api_version


def test_v1beta3_uses_argument_maps(render_kubeadm):
    documents = render_kubeadm(kubernetes_version="1.30.14")

    assert documents["InitConfiguration"]["nodeRegistration"]["kubeletExtraArgs"] == {
        "cgroups-per-qos": "false",
        "enforce-node-allocatable": "",
        "node-ip": "192.0.2.10",
        "container-runtime-endpoint": "unix:///run/containerd/containerd.sock",
    }
    assert documents["ClusterConfiguration"]["scheduler"]["extraArgs"] == {
        "bind-address": "0.0.0.0",
        "tls-min-version": "VersionTLS13",
    }


def test_v1beta4_uses_argument_lists(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.31.14",
        kubernetes_oidc_issuer_url="https://keycloak.example.com/realms/atmosphere",
        kubernetes_oidc_client_id="kubernetes",
        kubernetes_oidc_username_claim="email",
    )

    registration = documents["InitConfiguration"]["nodeRegistration"]
    assert registration["criSocket"] == "unix:///run/containerd/containerd.sock"
    assert registration["kubeletExtraArgs"] == [
        {"name": "cgroups-per-qos", "value": "false"},
        {"name": "enforce-node-allocatable", "value": ""},
        {"name": "node-ip", "value": "192.0.2.10"},
        {
            "name": "container-runtime-endpoint",
            "value": "unix:///run/containerd/containerd.sock",
        },
    ]
    cluster = documents["ClusterConfiguration"]
    assert cluster["apiServer"]["extraArgs"] == [
        {"name": "tls-min-version", "value": "VersionTLS13"},
        {"name": "oidc-username-claim", "value": "email"},
        {
            "name": "oidc-issuer-url",
            "value": "https://keycloak.example.com/realms/atmosphere",
        },
        {"name": "oidc-client-id", "value": "kubernetes"},
    ]
    assert "proxy" not in cluster


def test_v1beta4_disables_kube_proxy_when_removed(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.31.14", kubernetes_remove_kube_proxy=True
    )

    assert documents["ClusterConfiguration"]["proxy"] == {"disabled": True}
