#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: kubelet_resize_state
short_description: Keep the kubelet running across the Kubernetes 1.35 upgrade
description:
  - From Kubernetes 1.35, the kubelet records the resources applied to each
    running container in its actuated pod state, and tries to resize any
    container without a record. On nodes running with
    C(--cgroups-per-qos=false), that resize panics and the kubelet
    crash-loops.
  - Kubelets before 1.35 only keep that state when in-place pod resize is
    enabled. This writes it from the pod specs, which match what is applied
    to running containers before 1.35.
  - Run it with the kubelet stopped, before starting a 1.35 or newer kubelet.
version_added: "3.5.0"
options:
  pods:
    description:
      - Pods on the node, as returned by the Kubernetes API (for example from
        M(kubernetes.core.k8s_info)).
    type: list
    elements: dict
    required: true
  path:
    description:
      - Path of the kubelet's actuated pod state.
    type: path
    default: /var/lib/kubelet/actuated_pods_state
  backup:
    description:
      - Keep a copy of an existing file before replacing it.
    type: bool
    default: true
notes:
  - Supports check mode.
author:
  - Mohammed Naser (@mnaser)
"""

EXAMPLES = r"""
- name: Write the kubelet actuated pod state (with the kubelet stopped)
  vexxhost.kubernetes.kubelet_resize_state:
    pods: "{{ pods.resources }}"
"""

RETURN = r"""
pods:
  description: Number of pods recorded.
  returned: always
  type: int
  sample: 42
backup_file:
  description: Path of the backup of the previous file.
  returned: when changed and a previous file existed
  type: str
"""

import os  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (  # noqa: E402
    kubelet_resize_state,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            pods=dict(type="list", elements="dict", required=True),
            path=dict(type="path", default="/var/lib/kubelet/actuated_pods_state"),
            backup=dict(type="bool", default=True),
        ),
        supports_check_mode=True,
    )

    path = module.params["path"]
    try:
        content = kubelet_resize_state.checkpoint(module.params["pods"])
        count = len(kubelet_resize_state.entries(module.params["pods"]))
    except (KeyError, TypeError, ValueError) as exc:
        module.fail_json(msg="Failed to build the kubelet resize state: %s" % exc)

    current = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    if current == content:
        module.exit_json(changed=False, pods=count)
    if module.check_mode:
        module.exit_json(changed=True, pods=count)

    result = dict(changed=True, pods=count)
    if current is not None and module.params["backup"]:
        result["backup_file"] = module.backup_local(path)

    directory = os.path.dirname(path)
    temp = os.path.join(directory, ".%s.tmp" % os.path.basename(path))
    with open(
        os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
    ) as handle:
        handle.write(content)
    module.atomic_move(temp, path)
    os.chmod(path, 0o600)
    module.exit_json(**result)


if __name__ == "__main__":
    main()
