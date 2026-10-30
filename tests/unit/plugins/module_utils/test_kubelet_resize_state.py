# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubelet actuated pod state checkpoint."""

import json

from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (
    kubelet_resize_state as resize_state,
)

# NOTE: Written by a 1.35.6 kubelet to /var/lib/kubelet/actuated_pods_state.
KUBELET_CHECKPOINT = {
    "data": (
        '{"entries":{'
        '"2b0b8095b7ced4d3761c67803c003293":{"ContainerResources":'
        '{"kube-scheduler":{"requests":{"cpu":"100m"}}},"PodLevelResources":null},'
        '"2c5bea55f7881948d9a5a0828be8dad7":{"ContainerResources":'
        '{"kube-apiserver":{"requests":{"cpu":"250m"}}},"PodLevelResources":null},'
        '"7190a102fb01c7a3b2001815b05616b7":{"ContainerResources":'
        '{"kube-controller-manager":{"requests":{"cpu":"200m"}}},"PodLevelResources":null},'
        '"9ba27a9cf7baa882ca6e28dc2f6b2fed":{"ContainerResources":'
        '{"etcd":{"requests":{"cpu":"100m","memory":"100Mi"}}},"PodLevelResources":null},'
        '"eb0a4bfe02d54d93b0e1de2d9db8de7b":{"ContainerResources":'
        '{"kube-vip":{}},"PodLevelResources":null}}}'
    ),
    "checksum": 2398840411,
}


def static_pod(config_hash, name, resources):
    return {
        "metadata": {
            "uid": "mirror-" + config_hash,
            "annotations": {resize_state.MIRROR_POD_ANNOTATION: config_hash},
        },
        "spec": {"containers": [{"name": name, "resources": resources}]},
        "status": {"phase": "Running"},
    }


def test_checksum_matches_kubelet():
    assert resize_state.checksum(KUBELET_CHECKPOINT["data"]) == (
        KUBELET_CHECKPOINT["checksum"]
    )


def test_checkpoint_matches_kubelet():
    pods = [
        static_pod(
            "2b0b8095b7ced4d3761c67803c003293",
            "kube-scheduler",
            {"requests": {"cpu": "100m"}},
        ),
        static_pod(
            "eb0a4bfe02d54d93b0e1de2d9db8de7b",
            "kube-vip",
            {},
        ),
        static_pod(
            "9ba27a9cf7baa882ca6e28dc2f6b2fed",
            "etcd",
            {"requests": {"memory": "100Mi", "cpu": "100m"}},
        ),
        static_pod(
            "7190a102fb01c7a3b2001815b05616b7",
            "kube-controller-manager",
            {"requests": {"cpu": "200m"}},
        ),
        static_pod(
            "2c5bea55f7881948d9a5a0828be8dad7",
            "kube-apiserver",
            {"requests": {"cpu": "250m"}},
        ),
    ]

    assert json.loads(resize_state.checkpoint(pods)) == KUBELET_CHECKPOINT


def test_entries_follow_kubelet_allocation():
    pods = [
        {
            "metadata": {"uid": "pod-1"},
            "spec": {
                "initContainers": [
                    {"name": "init", "resources": {"requests": {"cpu": "1"}}},
                    {
                        "name": "sidecar",
                        "restartPolicy": "Always",
                        "resources": {"limits": {"memory": "64Mi"}},
                    },
                ],
                "containers": [
                    {
                        "name": "main",
                        "resources": {
                            "requests": {"memory": "16Mi", "cpu": "10m"},
                            "limits": {"cpu": "1"},
                        },
                    },
                    {"name": "plain"},
                ],
            },
            "status": {"phase": "Running"},
        },
        {
            "metadata": {"uid": "pod-2"},
            "spec": {"containers": [{"name": "job"}]},
            "status": {"phase": "Succeeded"},
        },
    ]

    assert resize_state.entries(pods) == {
        "pod-1": {
            "ContainerResources": {
                "main": {
                    "limits": {"cpu": "1"},
                    "requests": {"cpu": "10m", "memory": "16Mi"},
                },
                "plain": {},
                "sidecar": {"limits": {"memory": "64Mi"}},
            },
            "PodLevelResources": None,
        }
    }

    data = json.loads(resize_state.checkpoint(pods))["data"]
    assert data.startswith(
        '{"entries":{"pod-1":{"ContainerResources":{"main":'
        '{"limits":{"cpu":"1"},"requests":{"cpu":"10m","memory":"16Mi"}}'
    )
