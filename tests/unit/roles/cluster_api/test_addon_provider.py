from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
ROLE = ROOT / "roles" / "cluster_api"


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def test_addon_provider_is_disabled_by_default() -> None:
    defaults = read_yaml(ROLE / "defaults" / "main.yml")

    assert defaults["cluster_api_addon_provider_enabled"] is False
    assert defaults["cluster_api_addon_provider"] == "helm"
    assert defaults["cluster_api_addon_provider_version"] == "0.6.4"
    assert "@sha256:" in defaults["cluster_api_addon_provider_image"]


def test_addon_patch_is_guarded_by_explicit_enablement() -> None:
    tasks = read_yaml(ROLE / "tasks" / "main.yml")
    addon = next(
        task for task in tasks if task["name"] == "Patch Cluster API add-on provider"
    )

    assert addon["when"][0] == "cluster_api_addon_provider_enabled"
    assert "not ansible_check_mode" in addon["when"][1]
    assert "AddonProvider" in addon["when"][1]
    assert "providerName" in addon["when"][1]


def test_vendored_provider_uses_digest_pinned_controller() -> None:
    manifest = (
        ROLE / "files" / "providers" / "addon-helm" / "v0.6.4" / "addon-components.yaml"
    )
    documents = [
        document for document in yaml.safe_load_all(manifest.read_text()) if document
    ]
    deployment = next(
        document
        for document in documents
        if document.get("kind") == "Deployment"
        and document["metadata"]["name"] == "caaph-controller-manager"
    )
    image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]

    assert image == (
        "registry.k8s.io/cluster-api-helm/cluster-api-helm-controller@sha256:"
        "97d2a86f8e35d23bb4656b26f4564b35f109e47a0dc4860b71089e52eb6e6a24"
    )


def test_generic_provider_files_contain_no_gpu_or_os_policy() -> None:
    policy_paths = [
        ROLE / "defaults" / "main.yml",
        ROLE / "meta" / "main.yml",
        ROLE / "vars" / "main.yml",
        *sorted((ROLE / "tasks").glob("*.yml")),
    ]
    public_role = "\n".join(path.read_text() for path in policy_paths).lower()

    assert "nvidia" not in public_role
    assert "h200" not in public_role
    assert "ubuntu-2404" not in public_role
