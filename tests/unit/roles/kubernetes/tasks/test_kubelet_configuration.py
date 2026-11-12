from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]


def test_target_validation_precedes_upload_and_cleanup_is_unconditional():
    tasks = yaml.safe_load(
        (ROOT / "roles/kubernetes/tasks/kubelet-configuration.yml").read_text()
    )
    lifecycle = next(
        t
        for t in tasks
        if t["name"] == "Validate and upload the preserved kubelet configuration"
    )
    block = lifecycle["block"]
    validation = next(
        i
        for i, t in enumerate(block)
        if t["name"] == "Validate preserved fields against the target kubeadm schema"
    )
    upload = next(
        i
        for i, t in enumerate(block)
        if t["name"] == "Upload only the validated kubelet component configuration"
    )
    assert validation < upload
    assert "unknown field" in block[validation]["failed_when"]
    assert lifecycle["always"][0]["ansible.builtin.file"]["state"] == "absent"
    # Configuration may contain authentication headers; retain no extra copy.
    for task in tasks:
        assert "ansible.builtin.copy" not in task
    for task in block:
        if "ansible.builtin.copy" in task:
            copy = task["ansible.builtin.copy"]
            assert copy["dest"].startswith("{{ kubernetes_kubelet_staging.path }}/")
            assert copy["mode"] == "0600"


def test_preserving_upload_runs_before_the_control_plane_command():
    tasks = yaml.safe_load(
        (ROOT / "roles/kubernetes/tasks/control-plane.yml").read_text()
    )
    block = next(t for t in tasks if t["name"] == "Upgrade if necessary")["block"]
    include = block[0]["ansible.builtin.include_tasks"]
    assert include["file"] == "kubelet-configuration.yml"
    assert "delegate_to" not in block[0]
    assert include["apply"]["delegate_to"] == (
        "{{ kubernetes_bootstrap_node | default(groups[kubernetes_control_plane_group][0]) }}"
    )
    assert block[1]["ansible.builtin.include_tasks"] == "controller-upgrade-command.yml"
