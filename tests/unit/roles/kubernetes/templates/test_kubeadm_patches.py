# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubeadm patches the kubernetes role manages."""

import pytest


@pytest.mark.parametrize(
    "version,targets",
    [
        (
            "1.24.17",
            ["etcd", "kube-apiserver", "kube-controller-manager", "kube-scheduler"],
        ),
        (
            "1.30.14",
            [
                "etcd",
                "kube-apiserver",
                "kube-controller-manager",
                "kube-scheduler",
                "kubeletconfiguration",
            ],
        ),
        (
            "1.31.14",
            [
                "etcd",
                "kube-apiserver",
                "kube-controller-manager",
                "kube-scheduler",
                "kubeletconfiguration",
                "corednsdeployment",
            ],
        ),
    ],
)
def test_patch_targets(role_vars, version, targets):
    assert (
        role_vars(kubernetes_version=version)["kubernetes_kubeadm_patch_targets"]
        == targets
    )


def test_coredns_patch_keeps_node_selector(role_vars):
    selector = {"kubernetes.io/os": "linux", "openstack-control-plane": "enabled"}

    patches = role_vars(
        kubernetes_version="1.31.14", kubernetes_coredns_node_selector=selector
    )["kubernetes_kubeadm_managed_patches"]

    assert patches == {
        "corednsdeployment": {
            "spec": {"template": {"spec": {"nodeSelector": selector}}}
        }
    }


@pytest.mark.parametrize(
    "version,selector",
    [("1.30.14", {"openstack-control-plane": "enabled"}), ("1.31.14", {})],
)
def test_no_coredns_patch_without_target_or_selector(role_vars, version, selector):
    patches = role_vars(
        kubernetes_version=version, kubernetes_coredns_node_selector=selector
    )["kubernetes_kubeadm_managed_patches"]

    assert patches == {}


@pytest.mark.parametrize(
    "version,expected",
    [("1.21.14", ""), ("1.30.14", "--patches /etc/kubernetes/kubeadm-patches")],
)
def test_upgrade_args(role_vars, version, expected):
    assert (
        role_vars(kubernetes_version=version)["kubernetes_kubeadm_upgrade_args"]
        == expected
    )
