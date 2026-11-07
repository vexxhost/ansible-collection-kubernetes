# Copyright (c) 2025 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap

import pytest
import yaml
from jinja2 import Environment


def load_tasks(filename):
    task_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "..",
        "roles",
        "kubernetes",
        "tasks",
        filename,
    )
    with open(task_path) as task_file:
        return yaml.safe_load(task_file)


def task_names(filename):
    return [task["name"] for task in load_tasks(filename)]


class TestKubeadmInitCommand:
    """Test the kubeadm init command rendering."""

    @pytest.mark.parametrize(
        "remove_kube_proxy,allow_swap,expected",
        [
            (
                False,
                False,
                textwrap.dedent(
                    """\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests"""
                ),
            ),
            (
                False,
                True,
                textwrap.dedent(
                    """\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests,Swap"""
                ),
            ),
            (
                True,
                False,
                textwrap.dedent(
                    """\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --skip-phases=addon/kube-proxy \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests"""
                ),
            ),
            (
                True,
                True,
                textwrap.dedent(
                    """\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --skip-phases=addon/kube-proxy \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests,Swap"""
                ),
            ),
        ],
    )
    def test_renders_expected_command(self, remove_kube_proxy, allow_swap, expected):
        """Verify the exact command rendered for each variable combination."""
        task_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "..",
            "..",
            "roles",
            "kubernetes",
            "tasks",
            "bootstrap-cluster.yml",
        )
        with open(task_path, "r") as f:
            tasks = yaml.safe_load(f)
        for task in tasks:
            if task.get("name") == "Initialize cluster":
                template_str = task.get("ansible.builtin.shell")
                break
        else:
            raise ValueError("Task 'Initialize cluster' not found")

        env = Environment()
        template = env.from_string(template_str)
        rendered = template.render(
            kubernetes_remove_kube_proxy=remove_kube_proxy,
            kubernetes_allow_unsafe_swap=allow_swap,
        )

        assert rendered == expected


def test_resize_guard_precedes_additional_control_plane_joins():
    names = task_names("bootstrap-cluster.yml")
    assert names.index(
        "Guard in-place pod resize before additional control planes join"
    ) < names.index("Join cluster")


def test_resize_guard_precedes_worker_setup():
    names = task_names("main.yml")
    assert names.index(
        "Guard in-place pod resize on kubelets without pod QoS cgroups"
    ) < names.index("Setup nodes")
    assert names.index(
        "Guard in-place pod resize on kubelets without pod QoS cgroups"
    ) < names.index("Upgrade the kubelets one node at a time")


def test_resize_guard_waits_for_every_api_server_to_enforce_it():
    tasks = load_tasks("resize-admission-guard.yml")
    names = [task["name"] for task in tasks]
    barrier = next(
        task
        for task in tasks
        if task["name"] == "Wait for the kubelet resize admission guard to be enforced"
    )
    barrier_tasks = {task["name"]: task for task in barrier["block"]}
    create = barrier_tasks["Create the resize admission enforcement probe"]
    visibility = barrier_tasks[
        "Wait for every API server to observe the enforcement probe"
    ]
    probe = barrier_tasks["Verify every API server enforces the resize admission guard"]
    cleanup = barrier["always"][0]
    argv = probe["ansible.builtin.command"]["argv"]
    metadata = create["kubernetes.core.k8s"]["definition"]["metadata"]

    assert names.index("Bind the kubelet resize admission policy") < names.index(
        "Wait for the kubelet resize admission guard to be enforced"
    )
    assert "name" not in metadata
    assert metadata["generateName"] == "vexxhost-resize-admission-probe-"
    assert create["register"] == "kubernetes_resize_admission_guard_probe_create"
    assert visibility["loop"] == (
        "{{ kubernetes_resize_admission_guard_api_endpoints }}"
    )
    assert "failed_when" not in visibility
    assert "--server=https://{{ item }}" in argv
    assert "--subresource=resize" in argv
    assert "--dry-run=server" in argv
    assert (
        "{{ kubernetes_resize_admission_guard_probe_create.result.metadata.name }}"
        in argv
    )
    assert probe["loop"] == "{{ kubernetes_resize_admission_guard_api_endpoints }}"
    assert probe["failed_when"] is not False
    assert any(
        "kubernetes_resize_admission_guard_policy_denial" in condition
        for condition in probe["until"]
    )
    assert any(
        "kubernetes_resize_admission_guard_validation_message" in condition
        for condition in probe["until"]
    )
    assert cleanup["name"] == "Remove the resize admission enforcement probe"
    assert cleanup["kubernetes.core.k8s"]["name"] == (
        "{{ kubernetes_resize_admission_guard_probe_create.result.metadata.name }}"
    )
    assert cleanup["when"]


@pytest.mark.parametrize(
    "rc,stderr,expected_failure",
    [
        (
            1,
            "ValidatingAdmissionPolicy 'guard' denied request: expected message",
            False,
        ),
        (0, "", True),
        (1, 'pods "guard-probe" not found', True),
        (1, "ValidatingAdmissionPolicy 'guard' denied request: wrong message", True),
    ],
)
def test_resize_guard_probe_accepts_only_the_managed_policy_denial(
    rc, stderr, expected_failure
):
    tasks = load_tasks("resize-admission-guard.yml")
    barrier = next(
        task
        for task in tasks
        if task["name"] == "Wait for the kubelet resize admission guard to be enforced"
    )
    probe = next(
        task
        for task in barrier["block"]
        if task["name"] == "Verify every API server enforces the resize admission guard"
    )
    expression = probe["failed_when"]
    rendered = (
        Environment()
        .from_string("{{ " + expression + " }}")
        .render(
            kubernetes_resize_admission_guard_probe={"rc": rc, "stderr": stderr},
            kubernetes_resize_admission_guard_policy_denial=(
                "ValidatingAdmissionPolicy 'guard'"
            ),
            kubernetes_resize_admission_guard_validation_message="expected message",
        )
    )

    assert yaml.safe_load(rendered) is expected_failure
