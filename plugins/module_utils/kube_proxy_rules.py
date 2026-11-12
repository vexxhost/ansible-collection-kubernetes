# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Plan removal of kube-proxy rules without touching other firewall owners."""

import json
import re
import shlex

OWNED = frozenset(
    {
        "KUBE-SERVICES",
        "KUBE-NODEPORTS",
        "KUBE-POSTROUTING",
        "KUBE-MARK-MASQ",
        "KUBE-EXTERNAL-SERVICES",
        "KUBE-FORWARD",
        "KUBE-PROXY-FIREWALL",
        "KUBE-PROXY-CANARY",
    }
)
PREFIXES = ("KUBE-SVC-", "KUBE-SEP-", "KUBE-EXT-", "KUBE-SVL-", "KUBE-FW-")
RETAINED = {"KUBE-FIREWALL", "KUBE-KUBELET-CANARY", "KUBE-IPTABLES-HINT"}


def owned(name):
    return name in OWNED or name.startswith(PREFIXES)


def target(rule):
    for option in ("-j", "--jump", "-g", "--goto"):
        if option in rule:
            return rule[rule.index(option) + 1]
    return ""


def render(tokens):
    if any(any(c in token for c in "\n\r\0") for token in tokens):
        raise ValueError("Invalid control character in firewall rule")
    return " ".join(json.dumps(t) if re.search(r'[\s"\\]', t) else t for t in tokens)


def parse(text):
    tables = {}
    current = None
    for raw in text.splitlines():
        line = re.sub(r"^\[\d+:\d+\] ", "", raw)
        if line.startswith("*"):
            current = tables.setdefault(line[1:], {"chains": {}, "rules": []})
        elif line.startswith(":"):
            fields = line.split()
            current["chains"][fields[0][1:]] = fields[1]
        elif line.startswith("-A "):
            current["rules"].append(shlex.split(line))
    return tables


def projection(tables):
    return {
        table: {
            "chains": {n: p for n, p in v["chains"].items() if not owned(n)},
            "rules": [
                r for r in v["rules"] if not owned(r[1]) and not owned(target(r))
            ],
        }
        for table, v in tables.items()
    }


def cleanup_plan(tables):
    lines, count = [], 0
    for table, values in tables.items():
        chains = [n for n in values["chains"] if owned(n)]
        if not chains:
            continue
        unknown = [
            n
            for n in values["chains"]
            if n.startswith("KUBE-") and not owned(n) and n not in RETAINED
        ]
        if unknown:
            raise ValueError(f"Unknown Kubernetes firewall owner: {unknown}")
        hooks = [r for r in values["rules"] if not owned(r[1]) and owned(target(r))]
        if any(
            values["chains"][r[1]] == "-" or "kubernetes" not in " ".join(r).lower()
            for r in hooks
        ):
            raise ValueError("Unexpected reference to kube-proxy chains")
        lines.append("*" + table)
        lines.extend(":" + n + " - [0:0]" for n in chains)
        # --noflush also preserves inter-chain references on the nft backend.
        # Flush only chains whose ownership was established above.
        lines.extend("-F " + n for n in chains)
        lines.extend(render(["-D", *r[1:]]) for r in hooks)
        lines.extend("-X " + n for n in chains)
        lines.append("COMMIT")
        count += len(chains)
    return "\n".join(lines) + "\n", count


def restore_plan(original, current):
    lines = []
    for table, values in original.items():
        chains = [n for n in values["chains"] if owned(n)]
        if not chains:
            continue
        lines.append("*" + table)
        lines.extend(":" + n + " - [0:0]" for n in chains)
        lines.extend("-F " + n for n in chains)
        lines.extend(render(r) for r in values["rules"] if owned(r[1]))
        positions = {}
        existing = current.get(table, {}).get("rules", [])
        for rule in values["rules"]:
            positions[rule[1]] = positions.get(rule[1], 0) + 1
            if not owned(rule[1]) and owned(target(rule)) and rule not in existing:
                lines.append(
                    render(["-I", rule[1], str(positions[rule[1]]), *rule[2:]])
                )
        lines.append("COMMIT")
    return "\n".join(lines) + "\n"
