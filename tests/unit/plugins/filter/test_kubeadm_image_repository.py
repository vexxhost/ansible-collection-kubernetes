import copy

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubeadm_image_repository import (
    kubeadm_image_repository,
)


@pytest.mark.parametrize("api", ["v1beta2", "v1beta3", "v1beta4"])
def test_replaces_owned_repositories_and_preserves_other_cluster_settings(api):
    stored = {
        "apiVersion": "kubeadm.k8s.io/" + api,
        "kind": "ClusterConfiguration",
        "imageRepository": "old.example/k8s",
        "dns": {
            "imageRepository": "old.example/dns",
            "imageTag": "custom",
            "disabled": True,
        },
        "networking": {"dnsDomain": "custom.internal"},
        "etcd": {"external": {"endpoints": ["https://db.example:2379"]}},
        "apiServer": {"certSANs": ["api.example"]},
    }
    original = copy.deepcopy(stored)
    result = kubeadm_image_repository(stored, "mirror.example:5000/k8s/")
    assert result["imageRepository"] == "mirror.example:5000/k8s"
    assert result["dns"] == {
        "imageRepository": "mirror.example:5000/k8s/coredns",
        "imageTag": "custom",
        "disabled": True,
    }
    for field in ["networking", "etcd", "apiServer", "apiVersion", "kind"]:
        assert result[field] == stored[field]
    assert stored == original
    assert kubeadm_image_repository(result, "mirror.example:5000/k8s") == result


@pytest.mark.parametrize("requested", ["registry.k8s.io", "k8s.gcr.io"])
def test_return_to_default_clears_old_mirror_without_deleting_dns_options(requested):
    result = kubeadm_image_repository(
        {
            "imageRepository": "old.example",
            "dns": {"imageRepository": "old.example/dns", "imageTag": "custom"},
        },
        requested,
    )
    assert result["imageRepository"] == "registry.k8s.io"
    assert result["dns"] == {
        "imageRepository": "registry.k8s.io/coredns",
        "imageTag": "custom",
    }


def test_older_kubeadm_defaults_can_be_selected_explicitly():
    result = kubeadm_image_repository({}, "registry.k8s.io", "k8s.gcr.io", "k8s.gcr.io")
    assert result == {
        "imageRepository": "k8s.gcr.io",
        "dns": {"imageRepository": "k8s.gcr.io"},
    }


@pytest.mark.parametrize(
    "repository", ["", "https://mirror.example", "bad registry", None]
)
def test_invalid_repository_is_rejected_before_any_write(repository):
    with pytest.raises(AnsibleFilterError):
        kubeadm_image_repository({}, repository)


def test_invalid_stored_dns_shape_is_not_overwritten():
    with pytest.raises(AnsibleFilterError, match="DNS"):
        kubeadm_image_repository({"dns": "unexpected"}, "mirror.example")
