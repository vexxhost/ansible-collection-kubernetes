#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: kubelet_configz
short_description: Read effective kubelet configuration from the Kubernetes API
description:
  - Lists Kubernetes Node objects once and reads each requested kubelet's
    effective C(configz) through the API server's node proxy.
  - A missing Node object or an unavailable kubelet is returned as unknown for
    that node instead of failing the module.
version_added: "3.5.1"
options:
  node_names:
    description:
      - Kubernetes Node names to inspect.
    type: list
    elements: str
    required: true
  kubeconfig:
    description:
      - Path to a kubeconfig with permission to list and proxy nodes.
    type: path
    default: /etc/kubernetes/admin.conf
  request_timeout:
    description:
      - Positive timeout in seconds for each kubelet C(configz) request.
    type: int
    default: 10
notes:
  - Supports check mode.
  - Requires the Kubernetes Python client on the delegated host.
author:
  - Mohammed Naser (@mnaser)
"""

EXAMPLES = r"""
- name: Read effective kubelet settings
  vexxhost.kubernetes.kubelet_configz:
    node_names: "{{ groups['kubernetes'] }}"
  register: kubelet_configz
"""

RETURN = r"""
nodes:
  description: Inspection result keyed by Kubernetes Node name.
  returned: always
  type: dict
  contains:
    exists:
      description: Whether the Node API object exists, or C(null) if listing failed.
      type: bool
    kubelet_version:
      description: Version reported in C(status.nodeInfo.kubeletVersion).
      type: str
    cgroups_per_qos:
      description: Effective C(cgroupsPerQOS), or C(null) when unavailable.
      type: bool
    error:
      description: Why the node's state could not be determined.
      type: str
api_error:
  description: Why Node objects could not be listed.
  returned: when the Kubernetes API cannot be queried
  type: str
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (  # noqa: E402
    kubelet_configz,
)

KUBERNETES_IMP_ERR = None
try:
    from kubernetes import client, config
except ImportError as exc:
    KUBERNETES_IMP_ERR = exc


def _unknown_nodes(node_names, error):
    return {
        name: {
            "exists": None,
            "kubelet_version": "",
            "cgroups_per_qos": None,
            "error": error,
        }
        for name in node_names
    }


def main():
    module = AnsibleModule(
        argument_spec=dict(
            node_names=dict(type="list", elements="str", required=True),
            kubeconfig=dict(type="path", default="/etc/kubernetes/admin.conf"),
            request_timeout=dict(type="int", default=10),
        ),
        supports_check_mode=True,
    )

    if module.params["request_timeout"] < 1:
        module.fail_json(msg="request_timeout must be a positive integer")

    if KUBERNETES_IMP_ERR:
        error = "The Kubernetes Python client is unavailable: %s" % KUBERNETES_IMP_ERR
        module.exit_json(
            changed=False,
            nodes=_unknown_nodes(module.params["node_names"], error),
            api_error=error,
        )

    node_names = list(dict.fromkeys(module.params["node_names"]))
    configuration = client.Configuration()
    try:
        config.load_kube_config(
            config_file=module.params["kubeconfig"],
            client_configuration=configuration,
        )
        api_client = client.ApiClient(
            configuration=configuration,
            pool_threads=max(1, min(len(node_names), 32)),
        )
        api = client.CoreV1Api(api_client)
        try:
            nodes = kubelet_configz.inspect(
                api,
                node_names,
                request_timeout=module.params["request_timeout"],
            )
        finally:
            api_client.close()
    except Exception as exc:  # API failure is incomplete evidence, not a play failure
        error = "Could not list Kubernetes nodes: %s" % exc
        module.exit_json(
            changed=False,
            nodes=_unknown_nodes(node_names, error),
            api_error=error,
        )

    module.exit_json(changed=False, nodes=nodes)


if __name__ == "__main__":
    main()
