# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Exercise real nft iptables transactions inside disposable namespaces.

Run with ``uv run --script tests/integration/kube_proxy_firewall.py`` on Linux
with unprivileged user namespaces and the nft iptables tools available.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "rules", ROOT / "plugins/module_utils/kube_proxy_rules.py"
)
rules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rules)

FIXTURE = """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:KUBE-FORWARD - [0:0]
:KUBE-FIREWALL - [0:0]
:CILIUM_FORWARD - [0:0]
-A FORWARD -m comment --comment "kubernetes forwarding rules" -j KUBE-FORWARD
-A FORWARD -j CILIUM_FORWARD
-A INPUT -j KUBE-FIREWALL
-A KUBE-FORWARD -m conntrack --ctstate INVALID -j DROP
-A KUBE-FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A KUBE-FIREWALL -j RETURN
-A CILIUM_FORWARD -j RETURN
COMMIT
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:KUBE-SERVICES - [0:0]
:KUBE-SVC-TEST - [0:0]
:KUBE-SEP-TEST - [0:0]
-A PREROUTING -m comment --comment "kubernetes service portals" -j KUBE-SERVICES
-A OUTPUT -m comment --comment "kubernetes service portals" -j KUBE-SERVICES
-A KUBE-SERVICES -j KUBE-SVC-TEST
-A KUBE-SVC-TEST -j KUBE-SEP-TEST
-A KUBE-SEP-TEST -j RETURN
COMMIT
"""


def command(argv, body=None):
    result = subprocess.run(
        argv, input=body, text=True, capture_output=True, check=False, timeout=30
    )
    if result.returncode:
        raise RuntimeError(f"{argv}: {result.stderr}")
    return result.stdout


def semantic(tables):
    # Chain creation order can change; rule order within each chain must not.
    return {
        table: {
            "chains": values["chains"],
            "rules": {
                name: [rule for rule in values["rules"] if rule[1] == name]
                for name in values["chains"]
            },
        }
        for table, values in tables.items()
    }


def exercise():
    for prefix in ["iptables-nft", "ip6tables-nft"]:
        save, restore = prefix + "-save", prefix + "-restore"
        command([restore], FIXTURE)
        before = rules.parse(command([save, "-c"]))
        plan, count = rules.cleanup_plan(before)
        assert count == 4
        command([restore, "-w", "10", "--noflush", "--test"], plan)
        assert rules.parse(command([save])) == before
        command([restore, "-w", "10", "--noflush"], plan)
        after = rules.parse(command([save]))
        assert rules.cleanup_plan(after)[1] == 0
        assert rules.projection(before) == rules.projection(after)
        command([restore, "-w", "10", "--noflush"], rules.restore_plan(before, after))
        restored = rules.parse(command([save]))
        assert semantic(restored) == semantic(before)
        # Repeating rollback must not duplicate rules or built-in hooks.
        command(
            [restore, "-w", "10", "--noflush"], rules.restore_plan(before, restored)
        )
        assert semantic(rules.parse(command([save]))) == semantic(before)
        print(json.dumps({"backend": prefix, "cleanup_and_rollback": "passed"}))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Never change the caller's firewall. Mutations require both new user
        # and network namespaces, even when the caller is already root.
        result = subprocess.run(
            [
                "unshare",
                "-Urn",
                sys.executable,
                str(Path(__file__).resolve()),
                "--isolated",
                os.readlink("/proc/self/ns/net"),
            ],
            check=False,
            timeout=90,
        )
        raise SystemExit(result.returncode)
    if (
        len(sys.argv) != 3
        or sys.argv[1] != "--isolated"
        or os.readlink("/proc/self/ns/net") == sys.argv[2]
        or os.getuid() != 0
    ):
        raise RuntimeError("The fixture requires a fresh isolated network namespace")
    exercise()
