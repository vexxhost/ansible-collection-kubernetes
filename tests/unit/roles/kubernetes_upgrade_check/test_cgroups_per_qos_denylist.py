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


def resize_guard_required(
    target_guarded_by,
    disabled_hosts,
    installed_guard_hosts,
    untracked_disabled_nodes=None,
    untracked_guard_nodes=None,
    api_enumeration_succeeded=True,
    fresh_bootstrap=False,
):
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
    env.filters["bool"] = bool
    return env.from_string(expression).render(
        kubernetes_upgrade_check_cgroups_per_qos_inspection_required=True,
        kubernetes_upgrade_check_cgroups_per_qos_resize_guarded_by=target_guarded_by,
        kubernetes_upgrade_check_detected_disabled_hosts=disabled_hosts,
        kubernetes_upgrade_check_detected_resize_guard_hosts=installed_guard_hosts,
        kubernetes_upgrade_check_detected_untracked_disabled_nodes=(
            untracked_disabled_nodes or []
        ),
        kubernetes_upgrade_check_detected_untracked_resize_guard_nodes=(
            untracked_guard_nodes or []
        ),
        kubernetes_upgrade_check_detected_api_enumeration_succeeded=(
            api_enumeration_succeeded
        ),
        kubernetes_upgrade_check_detected_fresh_bootstrap=fresh_bootstrap,
    )


def classify_untracked_node(node):
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    task = next(
        task
        for task in tasks
        if task["name"] == "Record Kubernetes Nodes absent from inventory"
    )
    env = NativeEnvironment(undefined=StrictUndefined)
    env.filters["vexxhost.kubernetes.version_matching_ranges"] = version_matching_ranges
    env.filters["dict2items"] = lambda value: [
        {"key": key, "value": item} for key, item in value.items()
    ]
    env.filters["difference"] = lambda value, other: [
        item for item in value if item not in other
    ]
    context = {
        "kubernetes_upgrade_check_fact_host": "fact-host",
        "hostvars": {
            "fact-host": {
                "kubernetes_upgrade_check_api_inspection": {
                    "nodes": {"stale-node": node}
                },
                "kubernetes_upgrade_check_inventory_nodes": {},
                "kubernetes_upgrade_check_untracked_api_nodes": [],
                "kubernetes_upgrade_check_untracked_disabled_nodes": [],
                "kubernetes_upgrade_check_untracked_unknown_nodes": [],
                "kubernetes_upgrade_check_untracked_resize_guard_nodes": [],
            }
        },
        "kubernetes_upgrade_check_cgroups_per_qos_resize_guard_versions": [
            {"min": "1.35.0"}
        ],
    }
    for variable, expression in task["vars"].items():
        context[variable] = env.from_string(expression).render(**context)

    return {
        fact: env.from_string(expression).render(**context)
        for fact, expression in task["ansible.builtin.set_fact"].items()
    }


def api_inspection_after_attempts(attempts):
    delegate_tasks = yaml.safe_load(
        (ROLE / "tasks/kubelet-configz-delegate.yml").read_text()
    )
    env = NativeEnvironment(undefined=StrictUndefined)
    env.filters["bool"] = bool
    facts = {
        "kubernetes_upgrade_check_api_inspection": {},
        "kubernetes_upgrade_check_api_partial_inspection": {},
    }
    hostvars = {"fact-host": facts}

    for attempt in attempts:
        for task in delegate_tasks[1:]:
            context = {
                "hostvars": hostvars,
                "kubernetes_upgrade_check_fact_host": "fact-host",
                "kubernetes_upgrade_check_api_attempt": attempt,
            }
            if all(
                env.from_string("{{ %s }}" % condition).render(**context)
                for condition in task["when"]
            ):
                for fact, expression in task["ansible.builtin.set_fact"].items():
                    facts[fact] = (
                        env.from_string(expression).render(**context)
                        if isinstance(expression, str)
                        else expression
                    )

    if (
        "nodes" not in facts["kubernetes_upgrade_check_api_inspection"]
        and "nodes" in facts["kubernetes_upgrade_check_api_partial_inspection"]
    ):
        facts["kubernetes_upgrade_check_api_inspection"] = facts[
            "kubernetes_upgrade_check_api_partial_inspection"
        ]

    return facts["kubernetes_upgrade_check_api_inspection"]


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


def test_api_inspection_retries_unreachable_controllers():
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    tasks_by_name = {task["name"]: task for task in tasks}
    initialize = tasks_by_name["Initialize Kubernetes API inspection"]
    inspect = tasks_by_name[
        "Inspect kubelets through a reachable Kubernetes API delegate"
    ]

    assert (
        initialize["ansible.builtin.set_fact"][
            "kubernetes_upgrade_check_api_inspection"
        ]
        == {}
    )
    assert "kubernetes_upgrade_check_api_delegates" in inspect["loop"]
    assert (
        inspect["loop_control"]["loop_var"] == "kubernetes_upgrade_check_api_delegate"
    )

    delegate_tasks = yaml.safe_load(
        (ROLE / "tasks/kubelet-configz-delegate.yml").read_text()
    )
    query = delegate_tasks[0]
    select = next(
        task
        for task in delegate_tasks
        if task["name"] == "Select API inspection without node-level errors"
    )
    assert query["delegate_to"] == "{{ kubernetes_upgrade_check_api_delegate }}"
    assert query["ignore_unreachable"] is True
    assert query["failed_when"] is False
    assert select["delegate_facts"] is True
    assert any(
        "kubernetes_upgrade_check_api_attempt.nodes is defined" in condition
        for condition in select["when"]
    )


def test_api_inspection_retries_after_api_error():
    attempts = [
        {
            "nodes": {"worker": {"cgroups_per_qos": None}},
            "api_error": "admin.conf does not exist",
        },
        {"nodes": {"worker": {"cgroups_per_qos": True}}},
    ]
    assert api_inspection_after_attempts(attempts) == attempts[1]


def test_api_inspection_retries_after_node_level_error():
    attempts = [
        {"nodes": {"worker": {"error": "proxy timeout"}}},
        {"nodes": {"worker": {"cgroups_per_qos": True}}},
    ]

    assert api_inspection_after_attempts(attempts) == attempts[1]


def test_api_inspection_keeps_partial_result_after_all_delegates():
    attempts = [
        {"nodes": {"worker": {"error": "first proxy timeout"}}},
        {"nodes": {"worker": {"error": "second proxy timeout"}}},
    ]

    assert api_inspection_after_attempts(attempts) == attempts[0]


def test_unavailable_api_inspection_records_unknown_nodes():
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    task = next(
        task
        for task in tasks
        if task["name"] == "Record API kubelet inspection results"
    )
    expression = task["vars"]["kubernetes_upgrade_check_api_node"]
    env = NativeEnvironment(undefined=StrictUndefined)

    result = env.from_string(expression).render(
        kubernetes_upgrade_check_cluster_api_inspection={},
        item={"value": "missing-node"},
    )

    assert result["exists"] is False
    assert result["cgroups_per_qos"] is None
    assert result["kubelet_version"] == ""
    assert "unavailable" in result["error"]


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


def test_untracked_vulnerable_api_node_requires_guard():
    assert (
        resize_guard_required(
            [{"min": "1.35.0"}],
            [],
            [],
            untracked_disabled_nodes=["stale-worker"],
            untracked_guard_nodes=["stale-worker"],
        )
        is True
    )


def test_failed_api_enumeration_keeps_guard_on_existing_cluster():
    assert (
        resize_guard_required(
            [{"min": "1.35.0"}],
            [],
            [],
            api_enumeration_succeeded=False,
            fresh_bootstrap=False,
        )
        is True
    )


@pytest.mark.parametrize(
    "assert_fresh_bootstrap,play_hosts,markers,expected",
    [
        (False, ["controller", "worker"], [], False),
        (
            True,
            ["controller", "worker"],
            [{"stat": {"exists": False}}, {"stat": {"exists": False}}],
            True,
        ),
        (
            True,
            ["controller", "worker"],
            [{"stat": {"exists": True}}, {"stat": {"exists": False}}],
            False,
        ),
        (True, ["controller"], [], False),
        (
            True,
            ["controller", "worker"],
            [{"failed": True}, {"stat": {"exists": False}}],
            False,
        ),
        (
            True,
            ["controller", "worker"],
            [{"unreachable": True}, {"stat": {"exists": False}}],
            False,
        ),
    ],
)
def test_fresh_bootstrap_requires_explicit_full_inventory_assertion(
    assert_fresh_bootstrap, play_hosts, markers, expected
):
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    task = next(
        task
        for task in tasks
        if task["name"] == "Record whether API failure is a fresh bootstrap"
    )
    expression = task["ansible.builtin.set_fact"][
        "kubernetes_upgrade_check_fresh_bootstrap"
    ]
    env = NativeEnvironment(undefined=StrictUndefined)
    env.filters["bool"] = bool
    env.filters["difference"] = lambda value, other: [
        item for item in value if item not in other
    ]

    result = env.from_string(expression).render(
        groups={"kubernetes": ["controller", "worker"]},
        kubernetes_upgrade_check_group="kubernetes",
        ansible_play_hosts_all=play_hosts,
        kubernetes_upgrade_check_assert_fresh_bootstrap=assert_fresh_bootstrap,
        kubernetes_upgrade_check_asserted_fresh_bootstrap_marker_results=markers,
    )

    assert result is expected


def test_fresh_bootstrap_assertion_defaults_to_false():
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())

    assert defaults["kubernetes_upgrade_check_assert_fresh_bootstrap"] is False


def test_limited_api_failure_does_not_probe_hosts_outside_the_play():
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    task = next(
        task
        for task in tasks
        if task["name"]
        == "Check join markers before accepting a fresh-bootstrap assertion"
    )

    assert task["loop"] == "{{ ansible_play_hosts_all }}"
    assert any(
        "difference(ansible_play_hosts_all)" in condition.replace("\n", "")
        for condition in task["when"]
    )


def test_explicit_fresh_bootstrap_can_skip_unknown_api_nodes():
    assert (
        resize_guard_required(
            [{"min": "1.35.0"}],
            [],
            [],
            api_enumeration_succeeded=False,
            fresh_bootstrap=True,
        )
        is False
    )


def test_cluster_safety_facts_are_published_to_every_play_host():
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    tasks_by_name = {task["name"]: task for task in tasks}
    aggregate = tasks_by_name["Record the cluster pod QoS cgroup state"]
    publish = tasks_by_name["Publish cluster pod QoS cgroup state to every play host"]
    deny = tasks_by_name["Refuse denylisted kubelets cluster-wide"]

    assert aggregate["run_once"] is True
    assert aggregate["delegate_facts"] is True
    assert publish["run_once"] is True
    assert publish["delegate_facts"] is True
    assert publish["loop"] == "{{ ansible_play_hosts_all }}"
    assert deny["any_errors_fatal"] is True


def test_untracked_qos_enabled_api_node_does_not_require_guard():
    classified = classify_untracked_node(
        {"cgroups_per_qos": True, "kubelet_version": "1.36.2"}
    )

    assert classified["kubernetes_upgrade_check_untracked_api_nodes"] == ["stale-node"]
    assert classified["kubernetes_upgrade_check_untracked_disabled_nodes"] == []
    assert classified["kubernetes_upgrade_check_untracked_unknown_nodes"] == []
    assert classified["kubernetes_upgrade_check_untracked_resize_guard_nodes"] == []


def test_untracked_disabled_api_node_is_guarded():
    classified = classify_untracked_node(
        {"cgroups_per_qos": False, "kubelet_version": "1.36.2"}
    )

    assert classified["kubernetes_upgrade_check_untracked_disabled_nodes"] == [
        "stale-node"
    ]
    assert classified["kubernetes_upgrade_check_untracked_resize_guard_nodes"] == [
        "stale-node"
    ]


def test_untracked_unavailable_api_node_is_guarded_as_unknown():
    classified = classify_untracked_node(
        {"cgroups_per_qos": None, "kubelet_version": ""}
    )

    assert classified["kubernetes_upgrade_check_untracked_unknown_nodes"] == [
        "stale-node"
    ]
    assert classified["kubernetes_upgrade_check_untracked_resize_guard_nodes"] == [
        "stale-node"
    ]
