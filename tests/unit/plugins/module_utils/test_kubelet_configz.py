# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

from ansible_collections.vexxhost.kubernetes.plugins.module_utils import kubelet_configz


class Request:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def get(self):
        if self.error:
            raise self.error
        return self.result


class API:
    def __init__(self):
        self.nodes = [
            SimpleNamespace(
                metadata=SimpleNamespace(name="enabled"),
                status=SimpleNamespace(
                    node_info=SimpleNamespace(kubelet_version="v1.36.2")
                ),
            ),
            SimpleNamespace(
                metadata=SimpleNamespace(name="down"),
                status=SimpleNamespace(
                    node_info=SimpleNamespace(kubelet_version="v1.35.6")
                ),
            ),
        ]

    def list_node(self, **kwargs):
        assert kwargs["_request_timeout"] == 10
        return SimpleNamespace(items=self.nodes)

    def connect_get_node_proxy_with_path(self, name, path, **kwargs):
        assert path == "configz"
        assert kwargs["async_req"] is True
        assert kwargs["_preload_content"] is False
        if name == "down":
            return Request(error=TimeoutError("timed out"))
        return Request({"kubeletconfig": {"cgroupsPerQOS": True}})


def test_inspect_returns_effective_state_and_node_local_errors():
    result = kubelet_configz.inspect(API(), ["enabled", "down", "new"])

    assert result["enabled"] == {
        "exists": True,
        "kubelet_version": "1.36.2",
        "cgroups_per_qos": True,
    }
    assert result["down"]["exists"] is True
    assert result["down"]["kubelet_version"] == "1.35.6"
    assert result["down"]["cgroups_per_qos"] is None
    assert "timed out" in result["down"]["error"]
    assert result["new"]["exists"] is False


def test_configz_uses_kubelet_default_when_field_is_omitted():
    assert kubelet_configz._cgroups_per_qos({"kubeletconfig": {}}) is True


def test_configz_decodes_the_kubernetes_client_string_response():
    response = '{"kubeletconfig":{"cgroupsPerQOS":false}}'
    assert kubelet_configz._cgroups_per_qos(response) is False


def test_configz_decodes_the_raw_kubernetes_client_response():
    response = SimpleNamespace(data=b'{"kubeletconfig":{"cgroupsPerQOS":false}}')
    assert kubelet_configz._cgroups_per_qos(response) is False
