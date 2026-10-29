# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

from ansible.errors import AnsibleFilterError

DOCUMENTATION = """
  name: kubeadm_cluster_args
  short_description: Merge component arguments into a kubeadm ClusterConfiguration
  version_added: 3.5.0
  description:
    - Merge command-line arguments for the control plane components into a
      kubeadm C(ClusterConfiguration), such as the one stored in the
      C(kube-system/kubeadm-config) ConfigMap.
    - The given arguments replace the stored ones with the same name. Stored
      arguments that are not given are kept, in order.
    - Arguments set to C(null) are removed.
    - Arguments are written in the format of the configuration's own API
      version, a list of C(name)/C(value) pairs for C(v1beta4) and a mapping
      before it. Values are always strings.
    - C(etcd) arguments are skipped when the cluster uses external etcd.
  options:
    _input:
      type: dict
      required: true
      description:
        - kubeadm C(ClusterConfiguration).
    args:
      type: dict
      required: true
      description:
        - Arguments for each component, keyed by C(etcd), C(apiServer),
          C(controllerManager) or C(scheduler).
  author:
    - Mohammed Naser <mnaser@vexxhost.com>
"""

EXAMPLES = """
- name: Keep the scheduler listening on all addresses
  ansible.builtin.debug:
    msg: >-
      {{
        cluster_configuration
        | vexxhost.kubernetes.kubeadm_cluster_args({'scheduler': {'bind-address': '0.0.0.0'}})
      }}
"""

RETURN = """
  _value:
    description: A copy of the ClusterConfiguration with the merged arguments.
    type: dict
"""

COMPONENTS = {
    "etcd": ("etcd", "local"),
    "apiServer": ("apiServer",),
    "controllerManager": ("controllerManager",),
    "scheduler": ("scheduler",),
}


def _merge_mapping(stored, args):
    merged = dict(stored or {})
    for name, value in args.items():
        if value is None:
            merged.pop(name, None)
        else:
            merged[name] = str(value)
    return merged


def _merge_list(stored, args):
    merged = []
    seen = set()
    for arg in stored or []:
        name = arg.get("name")
        if name not in args:
            merged.append(arg)
            continue
        # NOTE: v1beta4 allows repeating an argument, so an argument the role
        #       manages replaces every stored copy of it.
        if name not in seen and args[name] is not None:
            merged.append({"name": name, "value": str(args[name])})
        seen.add(name)
    merged.extend(
        {"name": name, "value": str(value)}
        for name, value in args.items()
        if value is not None and name not in seen
    )
    return merged


def kubeadm_cluster_args(cluster_configuration, args):
    if not isinstance(cluster_configuration, dict):
        raise AnsibleFilterError(
            "kubeadm_cluster_args needs a ClusterConfiguration mapping, got %s"
            % type(cluster_configuration)
        )
    if not isinstance(args, dict):
        raise AnsibleFilterError(
            "kubeadm_cluster_args needs a mapping of component arguments, got %s"
            % type(args)
        )
    unknown = sorted(set(args) - set(COMPONENTS))
    if unknown:
        raise AnsibleFilterError(
            "Unknown kubeadm components: %s (supported: %s)"
            % (", ".join(unknown), ", ".join(COMPONENTS))
        )

    api_version = str(cluster_configuration.get("apiVersion", "")).rpartition("/")[2]
    if not api_version:
        raise AnsibleFilterError("The ClusterConfiguration has no apiVersion")
    merge = _merge_list if api_version == "v1beta4" else _merge_mapping

    result = copy.deepcopy(cluster_configuration)
    for component, component_args in args.items():
        if not isinstance(component_args, dict):
            raise AnsibleFilterError(
                "Arguments for %s must be a mapping, got %s"
                % (component, type(component_args))
            )
        if component == "etcd" and "external" in (result.get("etcd") or {}):
            continue

        stored = result
        for key in COMPONENTS[component]:
            stored = stored.get(key) if isinstance(stored, dict) else None
        stored_args = stored.get("extraArgs") if isinstance(stored, dict) else None

        merged = merge(stored_args, component_args)
        if not merged and stored_args is None:
            continue

        parent = result
        for key in COMPONENTS[component]:
            if not isinstance(parent.get(key), dict):
                parent[key] = {}
            parent = parent[key]
        parent["extraArgs"] = merged

    return result


class FilterModule(object):
    def filters(self):
        return {"kubeadm_cluster_args": kubeadm_cluster_args}
