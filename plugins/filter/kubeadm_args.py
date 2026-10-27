# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleFilterError
from ansible.module_utils.common.collections import is_string

DOCUMENTATION = """
  name: kubeadm_args
  short_description: Format component arguments for a kubeadm configuration
  version_added: 3.5.0
  description:
    - Format a mapping of command-line arguments (for example C(extraArgs) or
      C(kubeletExtraArgs)) for the given kubeadm configuration API version.
    - kubeadm C(v1beta4) takes a list of C(name)/C(value) pairs, while older
      versions take a mapping. Values are always strings.
    - Arguments set to C(null) are left out, so an override can remove an
      argument the role sets by default.
  options:
    _input:
      type: dict
      required: true
      description:
        - Arguments to format, in order.
    api_version:
      type: string
      required: true
      description:
        - kubeadm configuration API version, for example C(v1beta3) or C(v1beta4).
  author:
    - Mohammed Naser <mnaser@vexxhost.com>
"""

EXAMPLES = """
- name: Format the scheduler arguments for kubeadm v1beta4
  ansible.builtin.debug:
    msg: "{{ {'bind-address': '0.0.0.0'} | vexxhost.kubernetes.kubeadm_args('v1beta4') }}"
"""

RETURN = """
  _value:
    description: The arguments as a mapping, or as a list of name/value pairs for v1beta4.
    type: raw
"""


def kubeadm_args(value, api_version):
    if not isinstance(value, dict):
        raise AnsibleFilterError(
            "Invalid value type (%s) for kubeadm_args (%r)" % (type(value), value)
        )
    if not is_string(api_version):
        raise AnsibleFilterError("kubeadm_args needs a kubeadm API version")

    args = dict((str(name), str(arg)) for name, arg in value.items() if arg is not None)
    if api_version == "v1beta4":
        return [{"name": name, "value": arg} for name, arg in args.items()]
    return args


class FilterModule(object):
    def filters(self):
        return {"kubeadm_args": kubeadm_args}
