#!/usr/bin/python
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Preserve a custom, authenticated HA kubelet endpoint without restarting it."""

import copy
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: kubelet_ha_endpoint
short_description: Preserve a controller kubelet HA endpoint across kubeadm upgrades
description:
  - Updates only the selected cluster server and an exact hosts entry.
  - Authenticates the certificate hostname before changing files.
options:
  hostname:
    description: Certificate-valid custom hostname resolving to the existing API VIP.
    type: str
    required: true
  address:
    description: Existing API VIP address used for the exact hosts-file mapping.
    type: str
    required: true
  node_name:
    description: Name of the node the current kubelet credentials may read.
    type: str
    required: true
  control_plane_endpoint:
    description: Kubeadm controlPlaneEndpoint URL whose managed endpoint may be changed.
    type: str
    required: true
  node_address:
    description: Local API address whose native kubeadm endpoint may also be changed.
    type: str
  kubeconfig:
    description: Existing kubelet kubeconfig; other fields and credentials are preserved.
    type: path
    default: /etc/kubernetes/kubelet.conf
  hosts_file:
    description: Hosts file used to resolve the custom HA hostname.
    type: path
    default: /etc/hosts
author: Rico Lin (@ricolin)
"""
EXAMPLES = r"""
- name: Preserve the existing API VIP route
  vexxhost.kubernetes.kubelet_ha_endpoint:
    hostname: kubernetes.default.svc.cluster.local
    address: "{{ kube_vip_address }}"
    node_name: "{{ kubelet_hostname }}"
    control_plane_endpoint: "https://{{ kubernetes_hostname }}:6443"
"""
RETURN = r"""
server:
  description: The resulting HA API endpoint.
  returned: success
  type: str
"""


def endpoint_plan(text, hostname, control_plane_endpoint=None, node_address=None):
    config = yaml.safe_load(text)
    contexts = [c for c in config["contexts"] if c["name"] == config["current-context"]]
    if len(contexts) != 1:
        raise ValueError("ambiguous kubelet context")
    cluster_name = contexts[0]["context"]["cluster"]
    clusters = [c for c in config["clusters"] if c["name"] == cluster_name]
    if len(clusters) != 1:
        raise ValueError("ambiguous kubelet cluster")
    server = "https://" + hostname + ":6443"
    current = clusters[0]["cluster"]["server"]
    managed = {control_plane_endpoint, server, "https://127.0.0.1:6443"}
    if node_address:
        literal = "[" + node_address + "]" if ":" in node_address else node_address
        managed.add("https://" + literal + ":6443")
    if control_plane_endpoint is not None and current not in managed:
        return text, current
    expected = copy.deepcopy(config)
    next(c for c in expected["clusters"] if c["name"] == cluster_name)["cluster"][
        "server"
    ] = server
    tree = yaml.compose(text)
    cluster_nodes = next(value for key, value in tree.value if key.value == "clusters")
    matches = []
    for node in cluster_nodes.value:
        fields = {key.value: value for key, value in node.value}
        if fields["name"].value == cluster_name:
            matches += [
                value for key, value in fields["cluster"].value if key.value == "server"
            ]
    if len(matches) != 1:
        raise ValueError("ambiguous kubelet server field")
    value = matches[0]
    rewritten = (
        text[: value.start_mark.index]
        + json.dumps(server)
        + text[value.end_mark.index :]
    )
    if yaml.safe_load(rewritten) != expected:
        raise ValueError("unexpected kubeconfig change")
    return rewritten, server


def hosts_plan(text, hostname, address):
    found = False
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if hostname in words[1:]:
            if ipaddress.ip_address(words[0]) != ipaddress.ip_address(address):
                raise ValueError("conflicting hosts entry for the HA endpoint")
            found = True
    return text if found else text.rstrip("\n") + "\n" + address + " " + hostname + "\n"


def replace_file(path, content):
    stat = path.stat()
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copystat(path, temporary)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            hostname=dict(type="str", required=True),
            address=dict(type="str", required=True),
            node_name=dict(type="str", required=True),
            control_plane_endpoint=dict(type="str", required=True),
            node_address=dict(type="str"),
            kubeconfig=dict(type="path", default="/etc/kubernetes/kubelet.conf"),
            hosts_file=dict(type="path", default="/etc/hosts"),
        ),
        supports_check_mode=True,
    )
    try:
        p = module.params
        address = str(ipaddress.ip_address(p["address"]))
        hostname = p["hostname"]
        if not hostname or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
            for c in hostname
        ):
            raise ValueError("invalid API certificate hostname")
        paths = [Path(p["hosts_file"]), Path(p["kubeconfig"])]
        if not paths[1].exists():
            module.exit_json(
                changed=False, skipped=True, reason="node has not joined the cluster"
            )
        if any(not path.is_file() or path.is_symlink() for path in paths):
            raise ValueError("expected regular hosts and kubelet kubeconfig files")
        original = {path: path.read_bytes() for path in paths}
        config, server = endpoint_plan(
            original[paths[1]].decode(),
            hostname,
            p["control_plane_endpoint"],
            p["node_address"],
        )
        if server != "https://" + hostname + ":6443":
            module.exit_json(
                changed=False, server=server, custom_endpoint_preserved=True
            )
        expected = {
            paths[0]: hosts_plan(
                original[paths[0]].decode(), hostname, address
            ).encode(),
            paths[1]: config.encode(),
        }
        sources = next(
            line.split(":", 1)[1].split()
            for line in Path("/etc/nsswitch.conf").read_text().splitlines()
            if line.startswith("hosts:")
        )
        if not sources or sources[0] != "files":
            raise ValueError(
                "hosts-file resolution must take precedence for the HA endpoint"
            )
        changed = any(original[path] != expected[path] for path in paths)
        if module.check_mode or not changed:
            module.exit_json(changed=changed, server=server)
        # The old hosts mapping is not needed for this certificate/auth check.
        literal = "[" + address + "]" if ":" in address else address
        result = subprocess.run(
            [
                module.get_bin_path("kubectl", required=True),
                "--request-timeout=10s",
                "--kubeconfig=" + p["kubeconfig"],
                "--server=https://" + literal + ":6443",
                "--tls-server-name=" + hostname,
                "get",
                "node",
                p["node_name"],
                "-o",
                "name",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode:
            raise ValueError("HA endpoint certificate or node authentication failed")
        applied = []
        try:
            for path in paths:
                if expected[path] == original[path]:
                    continue
                if path.read_bytes() != original[path]:
                    raise ValueError("file changed during endpoint preparation")
                fd, backup = tempfile.mkstemp(
                    prefix=path.name + ".before-ha-", dir=path.parent
                )
                os.close(fd)
                shutil.copy2(path, backup)
                os.chmod(backup, 0o600)
                replace_file(path, expected[path])
                applied.append(path)
                if path == paths[0]:
                    resolved = subprocess.run(
                        [
                            module.get_bin_path("getent", required=True),
                            "ahosts",
                            hostname,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    addresses = {
                        str(ipaddress.ip_address(line.split()[0]))
                        for line in resolved.stdout.splitlines()
                    }
                    if resolved.returncode or addresses != {address}:
                        raise ValueError(
                            "the HA hostname does not resolve exclusively to the API VIP"
                        )
        except Exception:
            for path in reversed(applied):
                if path.read_bytes() == expected[path]:
                    replace_file(path, original[path])
            raise
        module.exit_json(changed=True, server=server)
    except Exception as exc:
        module.fail_json(msg=str(exc))


if __name__ == "__main__":
    main()
