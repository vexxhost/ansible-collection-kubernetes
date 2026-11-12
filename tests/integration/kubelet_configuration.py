# /// script
# requires-python = ">=3.10"
# dependencies = ["ansible-core>=2.17,<2.19", "PyYAML>=6,<7"]
# ///
# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Render the real Ansible copy task and validate with supplied kubeadm binaries.

Requires kubernetes.core for the dynamic control-plane task parse. Everything
executes locally in temporary directories; no cluster is contacted or uploaded.
"""

import argparse
import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def execute(argv, environment):
    result = subprocess.run(
        argv, env=environment, text=True, capture_output=True, timeout=90, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeadm", action="append", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "roles/kubernetes/tasks"
    tasks = yaml.safe_load((source / "kubelet-configuration.yml").read_text())
    lifecycle = next(
        task
        for task in tasks
        if task["name"] == "Validate and upload the preserved kubelet configuration"
    )["block"]
    render = copy.deepcopy(
        next(
            task
            for task in lifecycle
            if task["name"]
            == "Write target validation input without bootstrap credentials"
        )
    )
    with tempfile.TemporaryDirectory(prefix="kubelet-config-integration-") as folder:
        temporary = Path(folder)
        namespace = temporary / "collections/ansible_collections/vexxhost"
        namespace.mkdir(parents=True)
        (namespace / "kubernetes").symlink_to(ROOT, target_is_directory=True)
        environment = {
            **os.environ,
            "ANSIBLE_COLLECTIONS_PATH": str(temporary / "collections")
            + ":"
            + os.environ.get(
                "ANSIBLE_COLLECTIONS_PATH", str(Path.home() / ".ansible/collections")
            ),
            "ANSIBLE_LOCAL_TEMP": str(temporary / "ansible-tmp"),
            "ANSIBLE_VARS_ENABLED": "host_group_vars",
            "ANSIBLE_NOCOLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        parse = temporary / "parse.yml"
        parse.write_text(
            yaml.safe_dump(
                [
                    {
                        "hosts": "localhost",
                        "gather_facts": False,
                        "tasks": [
                            {
                                "ansible.builtin.import_tasks": str(
                                    source / "control-plane.yml"
                                )
                            }
                        ],
                    }
                ]
            )
        )
        execute(
            ["ansible-playbook", str(parse), "-i", "localhost,", "--syntax-check"],
            environment,
        )
        results = []
        for supplied in args.kubeadm:
            binary = supplied.resolve(strict=True)
            version = json.loads(
                execute([str(binary), "version", "-o", "json"], environment).stdout
            )["clientVersion"]["gitVersion"]
            for invalid in [False, True]:
                case = temporary / (version + ("-invalid" if invalid else "-valid"))
                case.mkdir()
                stored = {
                    "apiVersion": "kubelet.config.k8s.io/v1beta1",
                    "kind": "KubeletConfiguration",
                    "cgroupDriver": "systemd",
                    "maxPods": 87,
                    "clusterDNS": ["10.96.0.53"],
                    "clusterDomain": "custom.internal",
                    "systemReserved": {"memory": "1Gi"},
                    "resolvConf": "/run/custom-resolv.conf",
                }
                if invalid:
                    stored["notARealKubeletField"] = "must fail validation"
                cluster = {
                    "apiVersion": "kubeadm.k8s.io/v1beta4",
                    "kind": "ClusterConfiguration",
                    "kubernetesVersion": version,
                }
                variables = {
                    "stored": stored,
                    "desired": {
                        "apiVersion": "kubelet.config.k8s.io/v1beta1",
                        "kind": "KubeletConfiguration",
                        "cgroupDriver": "cgroupfs",
                    },
                    "kubernetes_upgrade_configs": [cluster],
                    "kubernetes_kubelet_staging": {"path": str(case)},
                }
                playbook = case / "render.yml"
                playbook.write_text(
                    yaml.safe_dump(
                        [
                            {
                                "hosts": "localhost",
                                "connection": "local",
                                "gather_facts": False,
                                "vars": variables,
                                "tasks": [
                                    {
                                        "name": "Merge preserved settings through the collection filter",
                                        "ansible.builtin.set_fact": {
                                            "kubernetes_merged_kubelet_config": "{{ stored | vexxhost.kubernetes.kubelet_upgrade_config(desired) }}"
                                        },
                                    },
                                    render,
                                ],
                            }
                        ],
                        sort_keys=False,
                    )
                )
                execute(
                    ["ansible-playbook", str(playbook), "-i", "localhost,"], environment
                )
                target = case / "validate.yaml"
                configs = list(yaml.safe_load_all(target.read_text()))
                assert [config["kind"] for config in configs] == [
                    "ClusterConfiguration",
                    "KubeletConfiguration",
                ]
                assert configs[0]["apiVersion"] == "kubeadm.k8s.io/v1beta4"
                assert configs[1]["apiVersion"] == "kubelet.config.k8s.io/v1beta1"
                assert (
                    configs[1]["maxPods"] == 87
                    and configs[1]["cgroupDriver"] == "cgroupfs"
                )
                assert configs[1]["clusterDNS"] == stored["clusterDNS"]
                validation = subprocess.run(
                    [str(binary), "config", "validate", "--config", str(target)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                rejected = validation.returncode != 0 or any(
                    value in validation.stderr
                    for value in ["unknown field", "strict decoding error"]
                )
                assert rejected == invalid, validation.stderr
                results.append(
                    {
                        "version": version,
                        "invalid_field": invalid,
                        "expected_result_verified": True,
                    }
                )
        print(
            json.dumps(
                {
                    "passed": True,
                    "dynamic_tasks_parsed": True,
                    "cluster_contacted": False,
                    "cases": results,
                }
            )
        )


if __name__ == "__main__":
    main()
