from pathlib import Path

import pytest
import yaml
from ansible.plugins.filter.core import combine
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_cluster_args import (
    kubeadm_cluster_args,
)
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_image_repository import (
    kubeadm_image_repository,
)
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[5]


@pytest.mark.parametrize("proxy", [None, {}, {"disabled": False}, {"disabled": True}])
def test_existing_proxy_intent_is_enforced_without_replacing_other_fields(proxy):
    tasks = yaml.safe_load(
        (ROOT / "roles/kubernetes/tasks/cluster-configuration.yml").read_text()
    )
    task = next(
        t for t in tasks if t["name"].startswith("Update the component arguments")
    )
    env = NativeEnvironment()
    env.filters.update(combine=combine, bool=bool)
    env.filters["vexxhost.kubernetes.kubeadm_cluster_args"] = kubeadm_cluster_args
    env.filters["vexxhost.kubernetes.kubeadm_image_repository"] = (
        kubeadm_image_repository
    )
    original = {
        "apiVersion": "kubeadm.k8s.io/v1beta4",
        "kind": "ClusterConfiguration",
        "networking": {"dnsDomain": "custom.internal"},
    }
    if proxy is not None:
        original["proxy"] = proxy
    result = env.from_string(
        task["vars"]["kubernetes_kubeadm_cluster_configuration"]
    ).render(
        kubernetes_kubeadm_stored_cluster_configuration=original,
        kubernetes_remove_kube_proxy=True,
        kubernetes_kubeadm_etcd_args={},
        kubernetes_kubeadm_api_server_args={},
        kubernetes_kubeadm_controller_manager_args={},
        kubernetes_kubeadm_scheduler_args={},
        kubernetes_image_repository="registry.k8s.io",
        kubernetes_kubeadm_default_image_repository="registry.k8s.io",
        kubernetes_kubeadm_default_dns_image_repository="registry.k8s.io/coredns",
    )
    assert result["proxy"] == {"disabled": True}
    assert result["networking"] == original["networking"]


def test_proxy_preflight_precedes_application_changes():
    tasks = yaml.safe_load(
        (ROOT / "roles/kubernetes/tasks/bootstrap-cluster.yml").read_text()
    )
    guard = next(
        i
        for i, t in enumerate(tasks)
        if t.get("ansible.builtin.include_tasks") == "kube-proxy-check.yml"
    )
    application = next(
        i
        for i, t in enumerate(tasks)
        if t["name"] == "Prepare existing-cluster application prerequisites"
    )
    assert guard < application


def test_worker_recovery_checks_host_state_before_setup():
    tasks = yaml.safe_load((ROOT / "roles/kubernetes/tasks/main.yml").read_text())
    guard = next(
        i
        for i, t in enumerate(tasks)
        if t["name"] == "Check proxy-free state during worker-only recovery"
    )
    setup = next(i for i, t in enumerate(tasks) if t["name"] == "Setup nodes")
    assert guard < setup
