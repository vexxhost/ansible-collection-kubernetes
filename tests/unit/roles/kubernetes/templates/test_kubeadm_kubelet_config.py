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


@pytest.mark.parametrize(
    "version,expected",
    [
        ("1.32.13", None),
        ("1.33.13", {"InPlacePodVerticalScaling": False}),
        ("1.34.9", {"InPlacePodVerticalScaling": False}),
        ("1.35.6", None),
        ("1.36.2", None),
    ],
)
def test_in_place_resize_disabled_while_overridable(render_kubeadm, version, expected):
    documents = render_kubeadm(kubernetes_version=version)

    assert documents["KubeletConfiguration"].get("featureGates") == expected


@pytest.mark.parametrize("version", ["1.28.15", "1.30.14", "1.31.14", "1.36.2"])
def test_kubelet_uses_the_runc_cgroup_driver(render_kubeadm, version):
    documents = render_kubeadm(kubernetes_version=version)

    assert documents["KubeletConfiguration"]["cgroupDriver"] == "cgroupfs"


def test_kubelet_cgroup_driver_can_be_overridden(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.30.14", kubernetes_kubelet_cgroup_driver="systemd"
    )

    assert documents["KubeletConfiguration"]["cgroupDriver"] == "systemd"


@pytest.mark.parametrize("version", ["1.28.15", "1.34.9", "1.35.6"])
def test_user_feature_gates_are_rendered(render_kubeadm, version):
    documents = render_kubeadm(
        kubernetes_version=version,
        kubernetes_kubelet_feature_gates={"ExampleGate": "true"},
    )

    assert documents["KubeletConfiguration"]["featureGates"]["ExampleGate"] is True


def test_user_feature_gates_override_managed_gates(render_kubeadm):
    documents = render_kubeadm(
        kubernetes_version="1.34.9",
        kubernetes_kubelet_feature_gates={"InPlacePodVerticalScaling": True},
    )

    assert documents["KubeletConfiguration"]["featureGates"] == {
        "InPlacePodVerticalScaling": True
    }
