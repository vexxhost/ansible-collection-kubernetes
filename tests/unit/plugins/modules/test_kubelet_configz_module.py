# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
from ansible_collections.vexxhost.kubernetes.plugins.modules import kubelet_configz


class ModuleFailure(Exception):
    pass


def test_request_timeout_must_be_positive(monkeypatch):
    class FakeModule:
        params = {
            "node_names": ["node-1"],
            "kubeconfig": "/etc/kubernetes/admin.conf",
            "request_timeout": 0,
        }

        def fail_json(self, **kwargs):
            raise ModuleFailure(kwargs["msg"])

    monkeypatch.setattr(kubelet_configz, "AnsibleModule", lambda **kwargs: FakeModule())

    with pytest.raises(ModuleFailure, match="must be a positive integer"):
        kubelet_configz.main()
