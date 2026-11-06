# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Check the version ranges used for kubelets without pod QoS cgroups."""

from pathlib import Path

import pytest
import yaml
from ansible.plugins.test.core import version_compare
from ansible_collections.vexxhost.kubernetes.plugins.filter.version_ranges import (
    version_matching_ranges,
)
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROLE = Path(__file__).resolve().parents[4] / "roles" / "kubernetes_upgrade_check"


def matching_ranges(version, variable, ranges=None):
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    role_vars = yaml.safe_load((ROLE / "vars/main.yml").read_text())
    env = NativeEnvironment(undefined=StrictUndefined)
    env.tests["ansible.builtin.version"] = version_compare
    env.filters["vexxhost.kubernetes.version_matching_ranges"] = version_matching_ranges
    template = env.from_string(role_vars[variable])
    range_variable = {
        "kubernetes_upgrade_check_cgroups_per_qos_denied_by": (
            "kubernetes_upgrade_check_cgroups_per_qos_denylist"
        ),
        "kubernetes_upgrade_check_cgroups_per_qos_resize_guarded_by": (
            "kubernetes_upgrade_check_cgroups_per_qos_resize_guard_versions"
        ),
    }[variable]
    return template.render(
        kubernetes_version=version,
        **{range_variable: defaults[range_variable] if ranges is None else ranges},
    )


def denied_by(version, denylist=None):
    return matching_ranges(
        version,
        "kubernetes_upgrade_check_cgroups_per_qos_denied_by",
        denylist,
    )


def resize_guarded_by(version, ranges=None):
    return matching_ranges(
        version,
        "kubernetes_upgrade_check_cgroups_per_qos_resize_guarded_by",
        ranges,
    )


def resize_guard_required(target_guarded_by, disabled_hosts, installed_guard_hosts):
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    task = next(
        task
        for task in tasks
        if task["name"] == "Record the cluster pod QoS cgroup state"
    )
    expression = task["ansible.builtin.set_fact"][
        "kubernetes_upgrade_check_resize_admission_guard_required"
    ]
    env = NativeEnvironment(undefined=StrictUndefined)
    return env.from_string(expression).render(
        kubernetes_upgrade_check_cgroups_per_qos_resize_guarded_by=target_guarded_by,
        kubernetes_upgrade_check_detected_disabled_hosts=disabled_hosts,
        kubernetes_upgrade_check_detected_resize_guard_hosts=installed_guard_hosts,
    )


def test_check_mode_reads_the_installed_kubelet_version():
    tasks = yaml.safe_load((ROLE / "tasks/cgroups-per-qos-node.yml").read_text())
    task = next(
        task for task in tasks if task["name"] == "Read the installed kubelet version"
    )
    assert task["check_mode"] is False


def test_failed_fallback_file_reads_remain_unknown():
    tasks = yaml.safe_load((ROLE / "tasks/cgroups-per-qos-node.yml").read_text())
    tasks_by_name = {task["name"]: task for task in tasks}

    for name in (
        "Check which kubelet files exist",
        "Read the existing kubelet flags and configuration",
    ):
        task = tasks_by_name[name]
        assert task["ignore_errors"] is True
        assert "failed_when" not in task

    state_task = tasks_by_name["Record whether the node runs pods in QoS cgroups"]
    evidence_expression = state_task["vars"][
        "kubernetes_upgrade_check_fallback_file_reads_succeeded"
    ]
    env = NativeEnvironment(undefined=StrictUndefined)
    template = env.from_string(evidence_expression)

    assert (
        template.render(
            kubernetes_upgrade_check_kubelet_file_stats={
                "results": [{"failed": True, "msg": "permission denied"}]
            },
            kubernetes_upgrade_check_kubelet_files={"results": []},
        )
        is False
    )
    assert (
        template.render(
            kubernetes_upgrade_check_kubelet_file_stats={
                "results": [{"failed": False, "stat": {"exists": False}}]
            },
            kubernetes_upgrade_check_kubelet_files={"results": []},
        )
        is True
    )


@pytest.mark.parametrize(
    "version",
    ["1.28.13", "1.34.12", "1.35.0", "1.35.6", "1.35.8", "1.36.0", "1.36.2", "1.36.3"],
)
def test_allowed(version):
    assert denied_by(version) == []


@pytest.mark.parametrize(
    "version", ["1.35.9", "1.35.10", "1.36.4", "1.36.6", "1.37.0", "1.37.2"]
)
def test_denied(version):
    assert len(denied_by(version)) == 1


@pytest.mark.parametrize(
    "version,denied",
    [
        ("1.35.11", True),
        ("1.35.12", False),
        ("1.36.7", True),
        ("1.36.8", False),
        ("1.37.3", True),
        ("1.37.4", False),
        ("1.38.0", False),
    ],
)
def test_branches_are_lifted_separately(version, denied):
    denylist = [
        {"min": "1.35.9", "max": "1.35.12"},
        {"min": "1.36.4", "max": "1.36.8"},
        {"min": "1.37.0", "max": "1.37.4"},
    ]
    assert bool(denied_by(version, denylist)) is denied


def test_max_is_exclusive():
    denylist = [{"min": "1.36.4", "max": "1.36.8"}]
    assert len(denied_by("1.36.7", denylist)) == 1
    assert denied_by("1.36.8", denylist) == []


@pytest.mark.parametrize("version", ["1.34.12", "1.34.99"])
def test_resize_guard_not_required_before_1_35(version):
    assert resize_guarded_by(version) == []


@pytest.mark.parametrize(
    "version", ["1.35.0", "1.35.6", "1.35.9", "1.36.0", "1.36.4", "1.37.0"]
)
def test_resize_guard_required_until_upstream_fix(version):
    assert len(resize_guarded_by(version)) == 1


@pytest.mark.parametrize(
    "version,guarded",
    [
        ("1.35.11", True),
        ("1.35.12", False),
        ("1.36.7", True),
        ("1.36.8", False),
        ("1.37.3", True),
        ("1.37.4", False),
        ("1.38.0", False),
    ],
)
def test_resize_guard_branches_are_lifted_separately(version, guarded):
    ranges = [
        {"min": "1.35.0", "max": "1.35.12"},
        {"min": "1.36.0", "max": "1.36.8"},
        {"min": "1.37.0", "max": "1.37.4"},
    ]
    assert bool(resize_guarded_by(version, ranges)) is guarded


def test_affected_target_requires_guard_before_kubelet_upgrade():
    assert resize_guard_required([{"min": "1.35.0"}], ["worker"], []) is True


def test_affected_installed_kubelet_keeps_guard_after_target_is_fixed():
    assert resize_guard_required([], ["worker"], ["worker"]) is True


def test_fixed_target_removes_guard_after_installed_kubelets_are_fixed():
    assert resize_guard_required([], ["worker"], []) is False


def test_qos_cgroups_do_not_require_guard():
    assert resize_guard_required([{"min": "1.35.0"}], [], []) is False
