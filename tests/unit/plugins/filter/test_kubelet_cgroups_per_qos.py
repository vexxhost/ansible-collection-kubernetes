# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubelet_cgroups_per_qos import (
    kubelet_cgroups_per_qos,
)

KUBEADM_FLAGS = (
    'KUBELET_KUBEADM_ARGS="--cgroups-per-qos=false '
    "--container-runtime-endpoint=unix:///run/containerd/containerd.sock "
    '--enforce-node-allocatable= --node-ip=192.0.2.10"\n'
)


def test_defaults_to_qos_cgroups():
    assert kubelet_cgroups_per_qos(["", ""]) is True


def test_kubeadm_flags_disable_qos_cgroups():
    assert kubelet_cgroups_per_qos([KUBEADM_FLAGS, ""]) is False


def test_unquoted_value():
    assert (
        kubelet_cgroups_per_qos(["KUBELET_KUBEADM_ARGS=--cgroups-per-qos=false\n"])
        is False
    )


@pytest.mark.parametrize("value", ["0", "f", "F", "FALSE", "false", "False"])
def test_go_false_values(value):
    assert kubelet_cgroups_per_qos(['ARGS="--cgroups-per-qos=%s"' % value]) is False


def test_flag_without_value_is_true():
    assert kubelet_cgroups_per_qos(['ARGS="--cgroups-per-qos"']) is True


def test_last_flag_wins():
    extra = 'KUBELET_EXTRA_ARGS="--cgroups-per-qos=true"\n'
    assert kubelet_cgroups_per_qos([KUBEADM_FLAGS, extra]) is True


def test_comments_are_ignored():
    extra = '# KUBELET_EXTRA_ARGS="--cgroups-per-qos=true"\n'
    assert kubelet_cgroups_per_qos([KUBEADM_FLAGS, extra]) is False


def test_similar_flags_are_ignored():
    assert kubelet_cgroups_per_qos(['ARGS="--cgroups-per-qos-foo=false"']) is True


def test_configuration_file():
    assert kubelet_cgroups_per_qos([""], {"cgroupsPerQOS": False}) is False
    assert kubelet_cgroups_per_qos([""], {"cgroupsPerQOS": True}) is True
    assert kubelet_cgroups_per_qos([""], {"cgroupDriver": "cgroupfs"}) is True


def test_flags_override_configuration_file():
    assert kubelet_cgroups_per_qos([KUBEADM_FLAGS], {"cgroupsPerQOS": True}) is False
    assert (
        kubelet_cgroups_per_qos(
            ['ARGS="--cgroups-per-qos=true"'], {"cgroupsPerQOS": False}
        )
        is True
    )


def test_rejects_invalid_values():
    with pytest.raises(AnsibleFilterError):
        kubelet_cgroups_per_qos(['ARGS="--cgroups-per-qos=no"'])
    with pytest.raises(AnsibleFilterError):
        kubelet_cgroups_per_qos(42)
