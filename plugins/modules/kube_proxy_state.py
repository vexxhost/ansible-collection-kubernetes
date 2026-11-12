#!/usr/bin/python
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

DOCUMENTATION = r"""
module: kube_proxy_state
short_description: Inspect orphaned kube-proxy rules or explicitly recover them
version_added: "3.6.0"
description:
  - Checks IPv4 and IPv6 iptables state without treating kubelet chains as proxy rules.
  - Recovery requires healthy Cilium replacement and no running kube-proxy container.
  - Recovery saves private originals, uses no-flush transactions and restores owned rules on failure.
options:
  state:
    type: str
    choices: [checked, absent]
    default: checked
    description: Inspect only, or explicitly remove verified proxy-owned state.
author:
  - Rico Lin (@ricolin)
"""
EXAMPLES = r"""
- name: Refuse orphaned proxy state before upgrading
  vexxhost.kubernetes.kube_proxy_state:
- name: Explicitly recover one reviewed node
  vexxhost.kubernetes.kube_proxy_state:
    state: absent
"""
RETURN = r"""
proxy_chains:
  description: Proxy-owned chain count by address family.
  returned: always
  type: dict
backup:
  description: Protected originals retained by explicit recovery.
  returned: when recovery runs
  type: str
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (
    kube_proxy_rules as rules,
)


def command(argv, body=None, check=True):
    process = subprocess.run(
        argv, input=body, text=True, capture_output=True, timeout=30, check=False
    )
    if check and process.returncode:
        raise RuntimeError(f"{argv[0]} failed: {process.stderr[-1000:]}")
    return process


def containers_without_proxy():
    containers = json.loads(command(["crictl", "ps", "-o", "json"]).stdout)[
        "containers"
    ]
    if any(c["metadata"]["name"] == "kube-proxy" for c in containers):
        raise RuntimeError("Stop the kube-proxy writer before host recovery")
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            try:
                if (path / "comm").read_text().strip() == "kube-proxy":
                    raise RuntimeError(
                        "Stop the host kube-proxy writer before recovery"
                    )
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
    return containers


def replacement_ready():
    containers = containers_without_proxy()
    agents = [c for c in containers if c["metadata"]["name"] == "cilium-agent"]
    if len(agents) != 1:
        raise RuntimeError("Automatic recovery requires a verified Cilium replacement")
    status = json.loads(
        command(
            ["crictl", "exec", agents[0]["id"], "cilium", "status", "-o", "json"]
        ).stdout
    )
    if (
        status["cilium"]["state"] != "Ok"
        or status["kube-proxy-replacement"]["mode"] != "True"
    ):
        raise RuntimeError("Cilium kube-proxy replacement is not healthy and enabled")
    return agents[0]["id"]


def main():
    module = AnsibleModule(
        argument_spec={
            "state": {"choices": ["checked", "absent"], "default": "checked"}
        },
        supports_check_mode=True,
    )
    originals, plans, counts = {}, {}, {}
    backup = None
    attempted = []
    try:
        containers_without_proxy()
        for family, save in (("v4", "iptables-save"), ("v6", "ip6tables-save")):
            raw = command([save, "-c"]).stdout
            originals[family] = {"raw": raw, "tables": rules.parse(raw)}
            plans[family], counts[family] = rules.cleanup_plan(
                originals[family]["tables"]
            )
        if not any(counts.values()):
            module.exit_json(changed=False, proxy_chains=counts)
        if module.params["state"] == "checked":
            module.fail_json(
                changed=False,
                proxy_chains=counts,
                msg="Orphaned kube-proxy host rules remain. Stop proxy writers, verify the service replacement, then explicitly recover one reviewed node with kube_proxy_state state=absent and validate service traffic before continuing.",
            )
        if module.check_mode:
            module.exit_json(changed=True, proxy_chains=counts)
        agent = replacement_ready()
        os.umask(0o077)
        backup = tempfile.mkdtemp(prefix="kube-proxy-recovery-", dir="/var/tmp")
        for family, data in originals.items():
            Path(backup, "before." + family).write_text(data["raw"])
            if counts[family]:
                restore = "iptables-restore" if family == "v4" else "ip6tables-restore"
                command([restore, "-w", "10", "--noflush", "--test"], plans[family])
        for family, data in originals.items():
            if not counts[family]:
                continue
            save, restore = (
                ("iptables-save", "iptables-restore")
                if family == "v4"
                else ("ip6tables-save", "ip6tables-restore")
            )
            if rules.parse(command([save]).stdout) != data["tables"]:
                raise RuntimeError("Firewall rules changed during recovery planning")
            attempted.append(family)
            command([restore, "-w", "10", "--noflush"], plans[family])
            after = rules.parse(command([save]).stdout)
            if rules.cleanup_plan(after)[1] or rules.projection(
                after
            ) != rules.projection(data["tables"]):
                raise RuntimeError(
                    "Recovery changed non-proxy rules or left proxy state"
                )
        if replacement_ready() != agent:
            raise RuntimeError("Cilium identity changed during host recovery")
        module.exit_json(changed=True, proxy_chains=counts, backup=backup)
    except Exception as exc:  # noqa: BLE001 -- all failures must restore owned state
        failures = []
        for family in reversed(attempted):
            try:
                save, restore = (
                    ("iptables-save", "iptables-restore")
                    if family == "v4"
                    else ("ip6tables-save", "ip6tables-restore")
                )
                body = rules.restore_plan(
                    originals[family]["tables"], rules.parse(command([save]).stdout)
                )
                command([restore, "-w", "10", "--noflush"], body)
            except Exception as rollback:  # noqa: BLE001 -- retain rollback errors
                failures.append(str(rollback))
        module.fail_json(
            msg=str(exc),
            changed=bool(attempted),
            backup=backup,
            rollback_errors=failures,
        )


if __name__ == "__main__":
    main()
