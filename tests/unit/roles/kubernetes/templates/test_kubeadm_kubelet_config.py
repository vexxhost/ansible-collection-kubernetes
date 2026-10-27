# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubeadm argument overrides in kubeadm.yaml.j2."""

import pytest


def as_mapping(args):
    if isinstance(args, list):
        return {arg["name"]: arg["value"] for arg in args}
    return args


def kubelet_args(documents):
    return as_mapping(
        documents["InitConfiguration"]["nodeRegistration"]["kubeletExtraArgs"]
    )


@pytest.mark.parametrize("version", ["1.28.15", "1.31.14", "1.36.2"])
def test_kubelet_keeps_qos_cgroup_defaults(render_kubeadm, version):
    args = kubelet_args(render_kubeadm(kubernetes_version=version))

    assert "cgroups-per-qos" not in args
    assert "enforce-node-allocatable" not in args


def test_extra_args_can_restore_legacy_qos_flags(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.31.14",
        kubernetes_kubeadm_extra_args={
            "kubelet": {"cgroups-per-qos": "false", "enforce-node-allocatable": ""}
        },
    )

    args = kubelet_args(documents)
    assert args["cgroups-per-qos"] == "false"
    assert args["enforce-node-allocatable"] == ""


@pytest.mark.parametrize("version", ["1.30.14", "1.31.14"])
def test_extra_args_add_change_and_remove(render_kubeadm, version):
    documents = render_kubeadm(
        kubernetes_version=version,
        kubernetes_kubeadm_extra_args={
            "kubelet": {"max-pods": 200},
            "apiServer": {"tls-min-version": None, "audit-log-maxage": 30},
            "scheduler": {"bind-address": "127.0.0.1"},
        },
    )

    assert kubelet_args(documents)["max-pods"] == "200"
    cluster = documents["ClusterConfiguration"]
    assert as_mapping(cluster["apiServer"]["extraArgs"]) == {"audit-log-maxage": "30"}
    assert as_mapping(cluster["scheduler"]["extraArgs"]) == {
        "bind-address": "127.0.0.1",
        "tls-min-version": "VersionTLS13",
    }
    assert as_mapping(cluster["controllerManager"]["extraArgs"])["bind-address"] == (
        "0.0.0.0"
    )


def test_extra_args_for_some_components_only(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.31.14",
        kubernetes_kubeadm_extra_args={"etcd": {"quota-backend-bytes": "8589934592"}},
    )

    assert as_mapping(
        documents["ClusterConfiguration"]["etcd"]["local"]["extraArgs"]
    ) == {
        "tls-min-version": "TLS1.3",
        "quota-backend-bytes": "8589934592",
    }
