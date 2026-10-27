# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_args import (
    kubeadm_args,
)

ARGS = {"bind-address": "0.0.0.0", "profiling": False, "v": 2}


@pytest.mark.parametrize("api_version", ["v1beta2", "v1beta3"])
def test_mapping_before_v1beta4(api_version):
    assert kubeadm_args(ARGS, api_version) == {
        "bind-address": "0.0.0.0",
        "profiling": "False",
        "v": "2",
    }


def test_name_value_list_for_v1beta4():
    assert kubeadm_args(ARGS, "v1beta4") == [
        {"name": "bind-address", "value": "0.0.0.0"},
        {"name": "profiling", "value": "False"},
        {"name": "v", "value": "2"},
    ]


def test_rejects_non_mapping():
    with pytest.raises(AnsibleFilterError):
        kubeadm_args(["bind-address=0.0.0.0"], "v1beta4")
