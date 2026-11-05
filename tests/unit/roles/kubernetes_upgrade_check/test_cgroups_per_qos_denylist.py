# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Check which versions the kubernetes_upgrade_check role denies on nodes
without pod QoS cgroups."""

from pathlib import Path

import pytest
import yaml
from ansible.plugins.test.core import version_compare
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROLE = Path(__file__).resolve().parents[4] / "roles" / "kubernetes_upgrade_check"


def denied_by(version, denylist=None):
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    role_vars = yaml.safe_load((ROLE / "vars/main.yml").read_text())
    env = NativeEnvironment(undefined=StrictUndefined)
    env.tests["ansible.builtin.version"] = version_compare
    template = env.from_string(
        role_vars["kubernetes_upgrade_check_cgroups_per_qos_denied_by"]
    )
    return template.render(
        kubernetes_version=version,
        kubernetes_upgrade_check_cgroups_per_qos_denylist=(
            defaults["kubernetes_upgrade_check_cgroups_per_qos_denylist"]
            if denylist is None
            else denylist
        ),
    )


@pytest.mark.parametrize(
    "version",
    ["1.28.13", "1.34.12", "1.35.0", "1.35.6", "1.35.8", "1.36.0", "1.36.1", "1.36.3"],
)
def test_allowed(version):
    assert denied_by(version) == []


@pytest.mark.parametrize(
    "version", ["1.35.9", "1.35.10", "1.36.2", "1.36.4", "1.36.6", "1.37.0", "1.37.2"]
)
def test_denied(version):
    assert len(denied_by(version)) == 1


@pytest.mark.parametrize(
    "version,denied",
    [
        ("1.35.11", True),
        ("1.35.12", False),
        ("1.36.2", True),
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
        {"min": "1.36.2", "max": "1.36.3"},
        {"min": "1.36.4", "max": "1.36.8"},
        {"min": "1.37.0", "max": "1.37.4"},
    ]
    assert bool(denied_by(version, denylist)) is denied


def test_max_is_exclusive():
    denylist = [{"min": "1.36.4", "max": "1.36.8"}]
    assert len(denied_by("1.36.7", denylist)) == 1
    assert denied_by("1.36.8", denylist) == []
