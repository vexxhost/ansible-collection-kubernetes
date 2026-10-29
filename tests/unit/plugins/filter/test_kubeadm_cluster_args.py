# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import copy

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_cluster_args import (
    kubeadm_cluster_args,
)


def stored(api_version, **components):
    """A stored ClusterConfiguration with the given component arguments."""
    configuration = {
        "apiVersion": "kubeadm.k8s.io/" + api_version,
        "kind": "ClusterConfiguration",
        "kubernetesVersion": "v1.29.15",
        "networking": {"podSubnet": "10.0.0.0/16"},
    }
    for component, args in components.items():
        if component == "etcd":
            configuration["etcd"] = {"local": {"dataDir": "/var/lib/etcd"}}
            if args is not None:
                configuration["etcd"]["local"]["extraArgs"] = args
        else:
            configuration[component] = {} if args is None else {"extraArgs": args}
    return configuration


@pytest.mark.parametrize("api_version", ["v1beta2", "v1beta3"])
def test_mapping_keeps_other_arguments(api_version):
    configuration = stored(
        api_version,
        scheduler={"profiling": "false"},
        controllerManager={
            "bind-address": "127.0.0.1",
            "cluster-signing-duration": "8760h",
        },
    )

    result = kubeadm_cluster_args(
        configuration,
        {
            "scheduler": {"bind-address": "0.0.0.0"},
            "controllerManager": {"bind-address": "0.0.0.0"},
        },
    )

    assert result["scheduler"]["extraArgs"] == {
        "profiling": "false",
        "bind-address": "0.0.0.0",
    }
    assert result["controllerManager"]["extraArgs"] == {
        "bind-address": "0.0.0.0",
        "cluster-signing-duration": "8760h",
    }
    assert result["networking"] == configuration["networking"]


def test_list_keeps_other_arguments_in_order():
    configuration = stored(
        "v1beta4",
        scheduler=[
            {"name": "profiling", "value": "false"},
            {"name": "bind-address", "value": "127.0.0.1"},
            {"name": "v", "value": "2"},
        ],
    )

    result = kubeadm_cluster_args(
        configuration,
        {"scheduler": {"bind-address": "0.0.0.0", "tls-min-version": "VersionTLS13"}},
    )

    assert result["scheduler"]["extraArgs"] == [
        {"name": "profiling", "value": "false"},
        {"name": "bind-address", "value": "0.0.0.0"},
        {"name": "v", "value": "2"},
        {"name": "tls-min-version", "value": "VersionTLS13"},
    ]


def test_list_replaces_repeated_arguments():
    configuration = stored(
        "v1beta4",
        controllerManager=[
            {"name": "bind-address", "value": "127.0.0.1"},
            {"name": "controllers", "value": "*"},
            {"name": "bind-address", "value": "10.0.0.1"},
        ],
    )

    result = kubeadm_cluster_args(
        configuration, {"controllerManager": {"bind-address": "0.0.0.0"}}
    )

    assert result["controllerManager"]["extraArgs"] == [
        {"name": "bind-address", "value": "0.0.0.0"},
        {"name": "controllers", "value": "*"},
    ]


@pytest.mark.parametrize(
    "api_version,args,expected",
    [
        (
            "v1beta3",
            {"oidc-username-claim": "email", "tls-min-version": "VersionTLS13"},
            {"tls-min-version": "VersionTLS13"},
        ),
        (
            "v1beta4",
            [
                {"name": "oidc-username-claim", "value": "email"},
                {"name": "tls-min-version", "value": "VersionTLS13"},
            ],
            [{"name": "tls-min-version", "value": "VersionTLS13"}],
        ),
    ],
)
def test_null_removes_stored_arguments(api_version, args, expected):
    configuration = stored(api_version, apiServer=args)

    result = kubeadm_cluster_args(
        configuration, {"apiServer": {"oidc-username-claim": None}}
    )

    assert result["apiServer"]["extraArgs"] == expected


@pytest.mark.parametrize("api_version", ["v1beta3", "v1beta4"])
def test_adds_arguments_to_components_without_any(api_version):
    configuration = stored(api_version, scheduler=None, etcd=None)
    del configuration["scheduler"]

    result = kubeadm_cluster_args(
        configuration,
        {
            "scheduler": {"bind-address": "0.0.0.0"},
            "etcd": {"tls-min-version": "TLS1.3"},
        },
    )

    if api_version == "v1beta4":
        assert result["scheduler"]["extraArgs"] == [
            {"name": "bind-address", "value": "0.0.0.0"}
        ]
        assert result["etcd"]["local"]["extraArgs"] == [
            {"name": "tls-min-version", "value": "TLS1.3"}
        ]
    else:
        assert result["scheduler"]["extraArgs"] == {"bind-address": "0.0.0.0"}
        assert result["etcd"]["local"] == {
            "dataDir": "/var/lib/etcd",
            "extraArgs": {"tls-min-version": "TLS1.3"},
        }


def test_does_not_add_empty_sections():
    configuration = stored("v1beta4")

    result = kubeadm_cluster_args(
        configuration,
        {"apiServer": {}, "scheduler": {"bind-address": None}, "etcd": {}},
    )

    assert result == configuration


def test_skips_external_etcd():
    configuration = stored("v1beta3")
    configuration["etcd"] = {"external": {"endpoints": ["https://192.0.2.1:2379"]}}

    result = kubeadm_cluster_args(
        configuration, {"etcd": {"tls-min-version": "TLS1.3"}}
    )

    assert result == configuration


def test_values_are_strings():
    result = kubeadm_cluster_args(
        stored("v1beta3"), {"scheduler": {"profiling": False, "v": 2}}
    )

    assert result["scheduler"]["extraArgs"] == {"profiling": "False", "v": "2"}


@pytest.mark.parametrize("api_version", ["v1beta3", "v1beta4"])
def test_is_idempotent_and_leaves_input_alone(api_version):
    configuration = stored(api_version, scheduler=None)
    original = copy.deepcopy(configuration)
    args = {"scheduler": {"bind-address": "0.0.0.0", "profiling": None}}

    once = kubeadm_cluster_args(configuration, args)

    assert configuration == original
    assert kubeadm_cluster_args(once, args) == once


def test_rejects_unknown_components():
    with pytest.raises(AnsibleFilterError, match="kubelet"):
        kubeadm_cluster_args(stored("v1beta4"), {"kubelet": {"max-pods": "200"}})


def test_rejects_configuration_without_api_version():
    with pytest.raises(AnsibleFilterError, match="apiVersion"):
        kubeadm_cluster_args({"kind": "ClusterConfiguration"}, {"scheduler": {}})
