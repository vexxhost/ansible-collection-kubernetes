# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Read effective kubelet configuration through the Kubernetes API."""

import json


def _node_version(node):
    status = getattr(node, "status", None)
    node_info = getattr(status, "node_info", None)
    version = getattr(node_info, "kubelet_version", None) or ""
    return version[1:] if version.startswith("v") else version


def _cgroups_per_qos(response):
    if hasattr(response, "data"):
        response = response.data
    if isinstance(response, (str, bytes)):
        response = json.loads(response)
    config = response.get("kubeletconfig", {})
    value = config.get("cgroupsPerQOS", True)
    if not isinstance(value, bool):
        raise ValueError("configz returned a non-boolean cgroupsPerQOS value")
    return value


def inspect(api, node_names, request_timeout=10, include_all_nodes=False):
    """Return Node versions and effective cgroupsPerQOS values.

    Node objects are listed once. The caller supplies an API client configured
    with enough worker threads for the asynchronous configz requests.
    """
    nodes = {
        node.metadata.name: node
        for node in api.list_node(_request_timeout=request_timeout).items
    }
    result = {}
    requests = {}

    names_to_inspect = list(dict.fromkeys(node_names))
    if include_all_nodes:
        names_to_inspect.extend(name for name in nodes if name not in names_to_inspect)

    for name in names_to_inspect:
        node = nodes.get(name)
        if node is None:
            result[name] = {
                "exists": False,
                "kubelet_version": "",
                "cgroups_per_qos": None,
                "error": "Node API object does not exist",
            }
            continue

        result[name] = {
            "exists": True,
            "kubelet_version": _node_version(node),
            "cgroups_per_qos": None,
        }
        try:
            requests[name] = api.connect_get_node_proxy_with_path(
                name,
                "configz",
                async_req=True,
                _preload_content=False,
                _request_timeout=request_timeout,
            )
        except Exception as exc:  # pragma: no cover - generated client boundary
            result[name]["error"] = "Could not start configz request: %s" % exc

    for name, request in requests.items():
        try:
            result[name]["cgroups_per_qos"] = _cgroups_per_qos(request.get())
        except Exception as exc:  # API and JSON errors are node-local evidence gaps
            result[name]["error"] = "Could not retrieve configz: %s" % exc

    return result
