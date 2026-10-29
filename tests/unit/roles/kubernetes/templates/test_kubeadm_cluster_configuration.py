# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Check the role's arguments against stored kubeadm cluster configurations."""

import pytest
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_cluster_args import (
    kubeadm_cluster_args,
)


def role_args(variables):
    """The arguments cluster-configuration.yml merges into the stored copy."""
    return {
        "etcd": variables["kubernetes_kubeadm_etcd_args"],
        "apiServer": variables["kubernetes_kubeadm_api_server_args"],
        "controllerManager": variables["kubernetes_kubeadm_controller_manager_args"],
        "scheduler": variables["kubernetes_kubeadm_scheduler_args"],
    }


@pytest.mark.parametrize("version", ["1.28.13", "1.30.14", "1.31.14", "1.34.0"])
def test_new_clusters_are_left_alone(render_kubeadm, role_vars, version):
    """A cluster created by the role already stores the role's arguments."""
    configuration = render_kubeadm(kubernetes_version=version)["ClusterConfiguration"]

    result = kubeadm_cluster_args(
        configuration, role_args(role_vars(kubernetes_version=version))
    )

    assert result == configuration


@pytest.mark.parametrize(
    "api_version,version", [("v1beta3", "1.29.15"), ("v1beta4", "1.34.0")]
)
def test_restores_bind_address_on_old_clusters(role_vars, api_version, version):
    """Clusters created before the role set bind-address get it back."""
    configuration = {
        "apiVersion": "kubeadm.k8s.io/" + api_version,
        "kind": "ClusterConfiguration",
        "controllerManager": {},
        "scheduler": {},
    }

    result = kubeadm_cluster_args(
        configuration, role_args(role_vars(kubernetes_version=version))
    )

    for component in ("controllerManager", "scheduler"):
        args = result[component]["extraArgs"]
        if api_version == "v1beta4":
            args = {arg["name"]: arg["value"] for arg in args}
        assert args["bind-address"] == "0.0.0.0"


def test_overrides_reach_existing_clusters(render_kubeadm, role_vars):
    """kubernetes_kubeadm_extra_args changes the stored arguments too."""
    configuration = render_kubeadm(kubernetes_version="1.34.0")["ClusterConfiguration"]
    extra_args = {
        "kubelet": {},
        "etcd": {},
        "apiServer": {"audit-log-maxage": "30", "tls-min-version": None},
        "controllerManager": {},
        "scheduler": {"bind-address": "192.0.2.10"},
    }

    result = kubeadm_cluster_args(
        configuration,
        role_args(
            role_vars(
                kubernetes_version="1.34.0", kubernetes_kubeadm_extra_args=extra_args
            )
        ),
    )

    assert result["apiServer"]["extraArgs"] == [
        {"name": "audit-log-maxage", "value": "30"}
    ]
    assert {"name": "bind-address", "value": "192.0.2.10"} in result["scheduler"][
        "extraArgs"
    ]
