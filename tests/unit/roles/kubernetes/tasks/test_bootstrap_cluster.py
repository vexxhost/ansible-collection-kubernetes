# Copyright (c) 2025 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap

import pytest
import yaml
from jinja2 import Environment


class TestKubeadmInitCommand:
    """Test the kubeadm init command rendering."""

    @pytest.mark.parametrize(
        "remove_kube_proxy,allow_swap,expected",
        [
            (
                False,
                False,
                textwrap.dedent("""\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests"""),
            ),
            (
                False,
                True,
                textwrap.dedent("""\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests,Swap"""),
            ),
            (
                True,
                False,
                textwrap.dedent("""\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --skip-phases=addon/kube-proxy \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests"""),
            ),
            (
                True,
                True,
                textwrap.dedent("""\
                    kubeadm init --config /etc/kubernetes/kubeadm.yaml --upload-certs \\
                      --skip-phases=addon/kube-proxy \\
                      --ignore-preflight-errors=DirAvailable--etc-kubernetes-manifests,Swap"""),
            ),
        ],
    )
    def test_renders_expected_command(self, remove_kube_proxy, allow_swap, expected):
        """Verify the exact command rendered for each variable combination."""
        task_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "..", "..",
            "roles", "kubernetes", "tasks", "bootstrap-cluster.yml",
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
