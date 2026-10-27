#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: kubelet_container_hash_migration
short_description: Keep containers running across the Kubernetes 1.31 kubelet upgrade
description:
  - Kubernetes 1.31 changed how the kubelet hashes containers, so a kubelet
    upgraded from 1.30 restarts every running container on its node.
  - With O(pods), reads the running containers through C(crictl) and returns
    the hash changes needed for the 1.31 kubelet. Nothing is changed.
  - With O(migrations), rewrites the hashes in containerd's metadata
    database. containerd must be stopped. The database is backed up next to
    itself first, and nothing is written if anything is unexpected.
version_added: "3.5.0"
options:
  pods:
    description:
      - Pods running on the node, as returned by the Kubernetes API (for
        example from M(kubernetes.core.k8s_info)).
      - The new hashes use the images exactly as written in these pod specs.
    type: list
    elements: dict
  migrations:
    description:
      - Hash changes to apply, as returned in RV(migrations) with O(pods).
    type: list
    elements: dict
  database:
    description:
      - Path to containerd's metadata database.
    type: path
    default: /var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db
notes:
  - Supports check mode.
author:
  - Mohammed Naser (@mnaser)
"""

EXAMPLES = r"""
- name: Plan the container hash migration
  vexxhost.kubernetes.kubelet_container_hash_migration:
    pods: "{{ pods.resources }}"
  register: plan

- name: Migrate container hashes (with containerd stopped)
  vexxhost.kubernetes.kubelet_container_hash_migration:
    migrations: "{{ plan.migrations }}"
"""

RETURN = r"""
containers:
  description: Number of running containers inspected.
  returned: with I(pods)
  type: int
  sample: 42
migrations:
  description: Hash changes needed for the 1.31 kubelet.
  returned: with I(pods)
  type: list
  elements: dict
  sample:
    - container_id: 7f3c...
      name: openvswitch
      image: ghcr.io/vexxhost/openvswitch:3.3@sha256:...
      old_hash: 1234abc
      new_hash: 27b3f881
skipped:
  description: Running containers whose pod was not in O(pods); their hashes are left alone.
  returned: with I(pods)
  type: list
  elements: dict
backup:
  description: Path of the database backup.
  returned: when changed
  type: str
replacements:
  description: Number of rewritten annotations per old hash.
  returned: when changed
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (  # noqa: E402
    kubelet_hash_migration,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            pods=dict(type="list", elements="dict"),
            migrations=dict(type="list", elements="dict"),
            database=dict(
                type="path",
                default=kubelet_hash_migration.CONTAINERD_METADATA_DB,
            ),
        ),
        mutually_exclusive=[("pods", "migrations")],
        required_one_of=[("pods", "migrations")],
        supports_check_mode=True,
    )

    try:
        if module.params["pods"] is not None:
            images = kubelet_hash_migration.pod_images(module.params["pods"])
            module.exit_json(changed=False, **kubelet_hash_migration.collect(images))

        migrations = module.params["migrations"]
        if module.check_mode:
            module.exit_json(changed=bool(migrations))
        module.exit_json(
            **kubelet_hash_migration.apply(migrations, module.params["database"])
        )
    except kubelet_hash_migration.MigrationError as exc:
        module.fail_json(msg="Container hash migration failed: %s" % exc)
    except (OSError, ValueError) as exc:
        module.fail_json(msg="Container hash migration failed: %s" % exc)


if __name__ == "__main__":
    main()
