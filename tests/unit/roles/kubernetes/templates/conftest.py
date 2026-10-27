# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Render kubernetes role templates with the role's defaults and vars."""

from pathlib import Path

import pytest
import yaml
from ansible.plugins.filter.core import combine, to_bool, to_json, to_nice_yaml
from ansible.plugins.test.core import version_compare
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_args import (
    kubeadm_args,
)
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROLE = Path(__file__).resolve().parents[5] / "roles" / "kubernetes"

INVENTORY = {
    "ansible_connection": "ssh",
    "inventory_hostname": "controller-0",
    "groups": {"controllers": ["controller-0"]},
    "kubernetes_bootstrap_node": "controller-0",
    "kubelet_node_ip": "192.0.2.10",
    "kubelet_cri_socket": "unix:///run/containerd/containerd.sock",
    "kubelet_allow_unsafe_swap": False,
    "kubernetes_hostname": "kubernetes.example.com",
}


def _environment(cls, **kwargs):
    # NOTE: trim_blocks matches the Ansible template module defaults.
    env = cls(undefined=StrictUndefined, trim_blocks=True, **kwargs)
    env.filters.update(
        bool=to_bool,
        combine=combine,
        to_json=to_json,
        to_nice_yaml=to_nice_yaml,
    )
    env.filters["vexxhost.kubernetes.kubeadm_args"] = kubeadm_args
    env.tests["version"] = version_compare
    env.tests["ansible.builtin.version"] = version_compare
    return env


def role_variables(**overrides):
    """Resolve the role's defaults and vars the way Ansible would."""
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    role_vars = yaml.safe_load((ROLE / "vars/main.yml").read_text()) or {}
    raw = {**defaults, **role_vars, **INVENTORY, **overrides}
    env = _environment(NativeEnvironment)
    resolved = {}

    def resolve(name, stack=()):
        if name in resolved:
            return resolved[name]
        value = raw[name]
        if isinstance(value, str) and "{{" in value:
            names = [key for key in raw if key in value and key not in stack]
            context = {key: resolve(key, stack + (name,)) for key in names}
            value = env.from_string(value).render(**context)
        resolved[name] = value
        return value

    return {name: resolve(name) for name in raw if not str(raw[name]).count("undef(")}


@pytest.fixture
def role_vars():
    return role_variables


@pytest.fixture
def render_kubeadm():
    def render(**overrides):
        env = _environment(Environment, loader=FileSystemLoader(ROLE / "templates"))
        variables = role_variables(**overrides)
        documents = yaml.safe_load_all(
            env.get_template("kubeadm.yaml.j2").render(**variables)
        )
        return {document["kind"]: document for document in documents}

    return render
