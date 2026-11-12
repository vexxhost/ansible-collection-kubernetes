# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Preserve supported site settings while refreshing role-owned kubelet keys."""

import copy

from ansible.errors import AnsibleFilterError

API = "kubelet.config.k8s.io/v1beta1"
OWNED = ("cgroupDriver", "tlsMinVersion")
MANAGED_GATES = ("InPlacePodVerticalScaling",)


def kubelet_upgrade_config(stored, desired):
    for name, value in [("stored", stored), ("desired", desired)]:
        if (
            not isinstance(value, dict)
            or value.get("apiVersion") != API
            or value.get("kind") != "KubeletConfiguration"
        ):
            raise AnsibleFilterError(
                f"{name} kubelet configuration requires supported {API} schema and kind"
            )
        if not isinstance(value.get("featureGates", {}), dict):
            raise AnsibleFilterError(f"{name} featureGates must be a mapping")
    result = copy.deepcopy(stored)
    for key in OWNED:
        if key in desired:
            result[key] = copy.deepcopy(desired[key])
    gates = copy.deepcopy(stored.get("featureGates", {}))
    for key in MANAGED_GATES:
        gates.pop(key, None)
    gates.update(desired.get("featureGates", {}))
    if gates:
        result["featureGates"] = gates
    else:
        result.pop("featureGates", None)
    return result


class FilterModule:
    def filters(self):
        return {"kubelet_upgrade_config": kubelet_upgrade_config}
