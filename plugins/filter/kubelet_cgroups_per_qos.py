# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

from ansible.errors import AnsibleFilterError
from ansible.module_utils.common.collections import is_string

DOCUMENTATION = """
  name: kubelet_cgroups_per_qos
  short_description: Tell whether a kubelet runs pods in QoS cgroups
  version_added: 3.5.1
  description:
    - Return the value the kubelet uses for C(cgroupsPerQOS), from the
      environment files its systemd unit reads and its configuration file.
    - Command-line flags override the configuration file, and the last
      C(--cgroups-per-qos) flag wins, as with the kubelet itself.  Without
      either, the kubelet default (C(true)) is returned.
  options:
    _input:
      type: list
      elements: string
      required: true
      description:
        - Contents of the environment files holding the kubelet flags, in the
          order the kubelet receives them (for example
          C(/var/lib/kubelet/kubeadm-flags.env), then C(/etc/default/kubelet)).
          Use an empty string for a file that does not exist.
    config:
      type: dict
      required: false
      description:
        - The KubeletConfiguration, if any.
  author:
    - Mohammed Naser <mnaser@vexxhost.com>
"""

EXAMPLES = """
- name: Check whether the kubelet runs pods in QoS cgroups
  ansible.builtin.debug:
    msg: "{{ ['KUBELET_KUBEADM_ARGS=\\"--cgroups-per-qos=false\\"'] | vexxhost.kubernetes.kubelet_cgroups_per_qos }}"
"""

RETURN = """
  _value:
    description: Whether the kubelet runs pods in QoS cgroups.
    type: bool
"""

# NOTE: Values accepted by Go's strconv.ParseBool, which the kubelet uses for
#       boolean flags.
TRUE_VALUES = ("1", "t", "T", "TRUE", "true", "True")
FALSE_VALUES = ("0", "f", "F", "FALSE", "false", "False")

FLAG = re.compile(r"""(?:^|[\s"'=])--cgroups-per-qos(?:=([^\s"']*))?(?=[\s"']|$)""")


def _flag(files):
    value = None
    for content in files:
        if not content:
            continue
        if not is_string(content):
            raise AnsibleFilterError(
                "Invalid file content type (%s) for kubelet_cgroups_per_qos"
                % type(content)
            )
        for line in content.splitlines():
            if line.lstrip().startswith("#"):
                continue
            for match in FLAG.finditer(line):
                value = "true" if match.group(1) is None else match.group(1)
    if value is None:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise AnsibleFilterError("Invalid value for --cgroups-per-qos: %r" % value)


def kubelet_cgroups_per_qos(files, config=None):
    if is_string(files):
        files = [files]
    if not isinstance(files, (list, tuple)):
        raise AnsibleFilterError(
            "Invalid value type (%s) for kubelet_cgroups_per_qos (%r)"
            % (type(files), files)
        )

    flag = _flag(files)
    if flag is not None:
        return flag
    value = (config or {}).get("cgroupsPerQOS")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if str(value) in TRUE_VALUES:
        return True
    if str(value) in FALSE_VALUES:
        return False
    raise AnsibleFilterError("Invalid value for cgroupsPerQOS: %r" % value)


class FilterModule(object):
    def filters(self):
        return {"kubelet_cgroups_per_qos": kubelet_cgroups_per_qos}
