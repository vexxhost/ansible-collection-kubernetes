# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubeadm patches the kubernetes role manages."""

from pathlib import Path

import pytest
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar


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
            "spec": {
                "template": {"spec": {"nodeSelector": selector}},
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
                },
                "minReadySeconds": 15,
            }
        }
    }


@pytest.mark.parametrize("ready_seconds", [None, 30])
def test_coredns_repair_uses_the_same_existing_patch_override(role_vars, ready_seconds):
    patch = (
        {}
        if ready_seconds is None
        else {"corednsdeployment": {"spec": {"minReadySeconds": ready_seconds}}}
    )
    variables = role_vars(
        kubernetes_version="1.31.14", kubernetes_kubeadm_patches=patch
    )
    role = Path(__file__).resolve().parents[5] / "roles/kubernetes"
    repair = yaml.safe_load((role / "tasks/coredns-upgrade.yml").read_text())[0]
    definition = Templar(loader=DataLoader(), variables=variables).template(
        repair["kubernetes.core.k8s"]["definition"]
    )
    spec = definition["spec"]
    assert (
        spec
        == variables["kubernetes_kubeadm_managed_patches"]["corednsdeployment"]["spec"]
    )
    assert spec["minReadySeconds"] == (15 if ready_seconds is None else ready_seconds)
    assert spec["strategy"]["rollingUpdate"] == {"maxUnavailable": 0, "maxSurge": 1}


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
