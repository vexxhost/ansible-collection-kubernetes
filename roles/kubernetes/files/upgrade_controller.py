#!/usr/bin/env python3
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Bounded kube-vip handoff and narrowly selected API transport recovery."""

import argparse
from datetime import datetime
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

DIRECTORY = Path("/var/lib/kubernetes/upgrade")
STATE = DIRECTORY / "controller-state.json"
MANIFEST = Path("/etc/kubernetes/manifests/kube-vip.yaml")


def command(argv, timeout=15):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("command failed: " + argv[0] + ": " + result.stderr[-500:])
    return result.stdout


def save(state):
    temporary = STATE.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(STATE)


def restore(state):
    if not state.get("active"):
        return
    backup = Path(state["backup"])
    if backup.is_file():
        if hashlib.sha256(backup.read_bytes()).hexdigest() != state["sha256"]:
            raise RuntimeError("suspended VIP manifest changed")
        if MANIFEST.exists():
            raise RuntimeError("VIP manifest was replaced while suspended")
        backup.replace(MANIFEST)
    elif (
        not MANIFEST.is_file()
        or hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != state["sha256"]
    ):
        raise RuntimeError("cannot locate the original VIP manifest")
    state["active"] = False
    save(state)


def vip_entries(address, interface):
    return [
        entry
        for link in json.loads(
            command(["ip", "-j", "address", "show", "dev", interface])
        )
        for entry in link.get("addr_info", [])
        if entry["local"] == address
    ]


def identity(pid):
    root = Path("/proc") / str(pid)
    return root.joinpath("comm").read_text().strip(), root.joinpath(
        "stat"
    ).read_text().rsplit(")", 1)[1].split()[19]


def api_sockets(address):
    family = "-Htnpe6" if ":" in address else "-Htnpe4"
    rows = []
    for line in command(
        ["ss", family, "state", "established", "dst", address, "dport", "=", "6443"]
    ).splitlines():
        fields = line.split()
        local, peer = fields[2:4]
        source, port = local.rsplit(":", 1)
        if (
            source.strip("[]") != address
            or peer.rsplit(":", 1)[0].strip("[]") != address
        ):
            continue
        users = re.findall(r'\("([^\"]+)",pid=(\d+),fd=(\d+)\)', line)
        inode = re.search(r"\bino:(\d+)\b", line)
        if len(users) != 1 or inode is None:
            raise RuntimeError("ambiguous retired-VIP socket owner")
        name, pid, fd = users[0]
        if name not in ("kubelet", "cilium-agent"):
            continue
        if not port.isdigit() or not 1024 <= int(port) <= 65535 or int(port) == 6443:
            raise RuntimeError("unexpected API client port")
        actual_name, started = identity(pid)
        if (
            actual_name != name
            or os.readlink("/proc/" + pid + "/fd/" + fd) != "socket:[" + inode[1] + "]"
        ):
            raise RuntimeError("socket process identity changed")
        rows.append(
            dict(name=name, pid=pid, fd=fd, inode=inode[1], started=started, port=port)
        )
    return rows


def recover(args, state):
    address = str(ipaddress.ip_address(args.address))
    deadline = time.monotonic() + 90
    while (
        subprocess.run(["pgrep", "-x", "kube-vip"], capture_output=True).returncode == 0
    ):
        if time.monotonic() >= deadline:
            raise RuntimeError("local kube-vip did not stop")
        time.sleep(1)
    entries = vip_entries(address, args.interface)
    for entry in entries:
        # Only remove this role's exact host VIP after its process exited.
        expected_prefix = 128 if ":" in address else 32
        if entry["prefixlen"] != expected_prefix:
            raise RuntimeError("refusing to remove a non-host VIP address")
        command(
            [
                "ip",
                "address",
                "del",
                address + "/" + str(expected_prefix),
                "dev",
                args.interface,
            ]
        )
    if vip_entries(address, args.interface):
        raise RuntimeError("VIP remains local")
    if state["was_owner"]:
        for selected in api_sockets(address):
            if selected not in api_sockets(address):
                continue
            family = "-Knt6" if ":" in address else "-Knt4"
            command(
                [
                    "ss",
                    family,
                    "state",
                    "established",
                    "src",
                    address,
                    "sport",
                    "=",
                    selected["port"],
                    "dst",
                    address,
                    "dport",
                    "=",
                    "6443",
                ]
            )
        if api_sockets(address):
            raise RuntimeError("retired-VIP client sockets remain")
    # A successful readiness request alone does not prove the former owner's
    # kubelet/watch clients recovered. Require sustained fresh lease renewals.
    stable = None
    deadline = time.monotonic() + 240
    since = time.time()
    while True:
        try:
            lease = json.loads(
                command(
                    [
                        "kubectl",
                        "--kubeconfig=/etc/kubernetes/admin.conf",
                        "--request-timeout=8s",
                        "-n",
                        "kube-node-lease",
                        "get",
                        "lease",
                        args.node,
                        "-o",
                        "json",
                    ]
                )
            )
            renewed = datetime.fromisoformat(
                lease["spec"]["renewTime"].replace("Z", "+00:00")
            ).timestamp()
            if renewed < since or time.time() - renewed >= 15:
                raise RuntimeError("controller kubelet lease has not recovered")
            command(
                [
                    "kubectl",
                    "--kubeconfig=/etc/kubernetes/admin.conf",
                    "--request-timeout=8s",
                    "get",
                    "--raw=/readyz",
                ]
            )
            stable = stable or time.monotonic()
            if time.monotonic() - stable >= 60:
                break
        except (RuntimeError, subprocess.TimeoutExpired):
            stable = None
        if time.monotonic() >= deadline:
            raise RuntimeError("API clients did not stabilize after the VIP handoff")
        time.sleep(2)
    image = Path("/etc/kubernetes/manifests/kube-apiserver.yaml").read_text()
    if not re.search(
        r"(?m)^\s*image:\s*\S+:v"
        + re.escape(args.target)
        + r"(?:@sha256:[0-9a-f]+)?\s*$",
        image,
    ):
        containers = json.loads(command(["crictl", "ps", "-o", "json"]))["containers"]
        apis = [c for c in containers if c["metadata"]["name"] == "kube-apiserver"]
        if len(apis) != 1:
            raise RuntimeError("expected one local API server container")
        pid = json.loads(command(["crictl", "inspect", apis[0]["id"]]))["info"]["pid"]
        if identity(pid)[0] != "kube-apiserver":
            raise RuntimeError("unexpected API server process")
        os.kill(pid, signal.SIGTERM)
        time.sleep(20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["suspend", "recover", "restore", "watchdog"])
    parser.add_argument("--node")
    parser.add_argument("--address")
    parser.add_argument("--interface")
    parser.add_argument("--target")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--token")
    args = parser.parse_args()
    if args.action == "watchdog":
        while True:
            time.sleep(1)
            with (DIRECTORY / "controller.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                state = json.loads(STATE.read_text())
                if state["token"] != args.token or not state["active"]:
                    return
                if time.time() >= state["expires"]:
                    restore(state)
                    return
    with (DIRECTORY / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        if args.action == "restore":
            was_active = state.get("active", False)
            restore(state)
            if was_active:
                deadline = time.monotonic() + 90
                while (
                    subprocess.run(
                        ["pgrep", "-x", "kube-vip"], capture_output=True
                    ).returncode
                    != 0
                ):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("restored kube-vip did not start")
                    time.sleep(1)
        elif args.action == "suspend":
            if state.get("active"):
                raise RuntimeError(
                    "a controller operation is already active; restore it first"
                )
            if MANIFEST.is_symlink() or not MANIFEST.is_file():
                raise RuntimeError("expected a regular kube-vip manifest")
            token = uuid.uuid4().hex
            backup = DIRECTORY / ("kube-vip-" + token + ".yaml")
            state = dict(
                active=True,
                token=token,
                backup=str(backup),
                sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                expires=time.time() + args.timeout,
                was_owner=bool(vip_entries(args.address, args.interface)),
            )
            save(state)
            with (DIRECTORY / "controller-watchdog.log").open("ab") as log:
                subprocess.Popen(
                    [sys.executable, __file__, "watchdog", "--token", token],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            MANIFEST.replace(backup)
        else:
            if not state.get("active"):
                raise RuntimeError("VIP suspension is not active")
            recover(args, state)
    print(json.dumps({"action": args.action, "completed": True}))


if __name__ == "__main__":
    main()
