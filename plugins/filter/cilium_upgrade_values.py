# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Merge the compatibility profile without dropping user operator variables."""

from copy import deepcopy

from ansible.errors import AnsibleFilterError
from ansible.plugins.filter.core import combine


def cilium_upgrade_values(profile, overrides):
    result = combine(deepcopy(profile), deepcopy(overrides), recursive=True)
    defaults = profile.get("operator", {}).get("extraEnv", [])
    supplied = overrides.get("operator", {}).get("extraEnv")
    if supplied is not None and defaults:
        values = {}
        for entries in (defaults, supplied):
            names = set()
            for entry in entries:
                name = entry.get("name")
                if not name or name in names:
                    raise AnsibleFilterError(
                        "Cilium operator extraEnv needs unique names"
                    )
                names.add(name)
                values[name] = deepcopy(entry)
        result.setdefault("operator", {})["extraEnv"] = list(values.values())
    return result


class FilterModule:
    def filters(self):
        return {"cilium_upgrade_values": cilium_upgrade_values}
