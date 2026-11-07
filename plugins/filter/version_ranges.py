# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleFilterError
from ansible.plugins.test.core import version_compare

DOCUMENTATION = """
  name: version_matching_ranges
  short_description: Return ranges containing a version
  version_added: 3.6.0
  description:
    - Returns entries whose C(min) is inclusive and whose optional C(max) is
      exclusive.
  options:
    _input:
      type: string
      required: true
      description: Version to match.
    ranges:
      type: list
      elements: dict
      required: true
      description: Version ranges with C(min) and optional C(max) keys.
  author:
    - Mohammed Naser <mnaser@vexxhost.com>
"""

EXAMPLES = """
- name: Find matching ranges
  ansible.builtin.set_fact:
    matches: "{{ kubernetes_version | vexxhost.kubernetes.version_matching_ranges(ranges) }}"
"""

RETURN = """
  _value:
    description: Matching range entries.
    type: list
"""


def _validate(ranges):
    if not isinstance(ranges, (list, tuple)):
        raise AnsibleFilterError("Version ranges must be a list")
    for item in ranges:
        if not isinstance(item, dict) or not item.get("min"):
            raise AnsibleFilterError("Each version range must contain min")


def version_matching_ranges(version, ranges):
    _validate(ranges)
    return [
        item
        for item in ranges
        if version_compare(version, item["min"], "ge")
        and ("max" not in item or version_compare(version, item["max"], "lt"))
    ]


class FilterModule(object):
    def filters(self):
        return {"version_matching_ranges": version_matching_ranges}
