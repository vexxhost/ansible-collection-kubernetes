#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
import tempfile

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: kustomize
short_description: Run kubectl kustomize and save output to a file
description:
  - Generates Kubernetes manifests using kubectl kustomize from a kustomization directory
  - Saves the output to a destination file
  - Supports check mode (dry-run)
  - Properly detects changes based on content checksum
version_added: "2.5.0"
options:
  src:
    description:
      - Path to the kustomization directory
    required: true
    type: path
  dest:
    description:
      - Path where the generated manifests should be saved
    required: true
    type: path
  kubectl_path:
    description:
      - Path to the kubectl binary
    type: path
    default: kubectl
author:
  - Mohammed Naser <mnaser@vexxhost.com>
"""

EXAMPLES = r"""
- name: Generate manifests using kubectl kustomize
  vexxhost.kubernetes.kustomize:
    src: /path/to/kustomization
    dest: /path/to/manifests.yaml

- name: Generate manifests with custom kubectl path
  vexxhost.kubernetes.kustomize:
    src: /path/to/kustomization
    dest: /path/to/manifests.yaml
    kubectl_path: /usr/local/bin/kubectl
"""

RETURN = r"""
changed:
  description: Whether the destination file was changed
  returned: always
  type: bool
  sample: true
dest:
  description: Path to the destination file
  returned: always
  type: str
  sample: /path/to/manifests.yaml
checksum:
  description: SHA256 checksum of the generated content
  returned: always
  type: str
  sample: 2aae6c35c94fcfb415dbe95f408b9ce91ee846ed
"""


def main():
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(type="path", required=True),
            dest=dict(type="path", required=True),
            kubectl_path=dict(type="path", default="kubectl"),
        ),
        supports_check_mode=True,
    )

    _, stdout, _ = module.run_command(
        [module.params["kubectl_path"], "kustomize", module.params["src"]],
        check_rc=True,
    )

    dest = module.params["dest"]
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=os.path.dirname(dest) or None,
    ) as temp_file:
        temp_file.write(stdout)
        temp_file.flush()

        new_checksum = module.sha256(temp_file.name)
        old_checksum = module.sha256(dest) if os.path.exists(dest) else None

        changed = old_checksum != new_checksum

        result = {
            "changed": changed,
            "dest": dest,
            "checksum": new_checksum,
        }

        if changed and not module.check_mode:
            module.atomic_move(temp_file.name, dest)

        module.exit_json(**result)


if __name__ == "__main__":
    main()
