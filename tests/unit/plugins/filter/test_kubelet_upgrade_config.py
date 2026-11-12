import copy

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.kubelet_upgrade_config import (
    kubelet_upgrade_config,
)


def config(**values):
    return {
        "apiVersion": "kubelet.config.k8s.io/v1beta1",
        "kind": "KubeletConfiguration",
        **values,
    }


def test_preserves_custom_fields_and_input_while_updating_managed_values():
    stored = config(
        clusterDNS=["10.96.0.53"],
        clusterDomain="site.internal",
        maxPods=87,
        systemReserved={"memory": "1Gi"},
        kubeReserved={"cpu": "500m"},
        resolvConf="/run/custom-resolv.conf",
        cpuManagerPolicy="static",
        cgroupDriver="systemd",
        tlsMinVersion="VersionTLS12",
        featureGates={"SiteGate": True, "InPlacePodVerticalScaling": False},
    )
    original = copy.deepcopy(stored)
    desired = config(
        cgroupDriver="cgroupfs",
        tlsMinVersion="VersionTLS13",
        featureGates={"AnotherGate": False},
    )
    result = kubelet_upgrade_config(stored, desired)
    for key in [
        "clusterDNS",
        "clusterDomain",
        "maxPods",
        "systemReserved",
        "kubeReserved",
        "resolvConf",
        "cpuManagerPolicy",
    ]:
        assert result[key] == stored[key]
    assert (
        result["cgroupDriver"] == "cgroupfs"
        and result["tlsMinVersion"] == "VersionTLS13"
    )
    assert result["featureGates"] == {"SiteGate": True, "AnotherGate": False}
    assert stored == original
    assert kubelet_upgrade_config(result, desired) == result


def test_preserves_managed_resize_gate_when_target_still_renders_it():
    result = kubelet_upgrade_config(
        config(featureGates={"SiteGate": True}),
        config(featureGates={"InPlacePodVerticalScaling": False}),
    )
    assert result["featureGates"] == {
        "SiteGate": True,
        "InPlacePodVerticalScaling": False,
    }


def test_removes_obsolete_owned_gate_without_leaving_an_empty_mapping():
    assert "featureGates" not in kubelet_upgrade_config(
        config(featureGates={"InPlacePodVerticalScaling": False}), config()
    )


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {
            "apiVersion": "kubelet.config.k8s.io/v1alpha1",
            "kind": "KubeletConfiguration",
        },
        {"apiVersion": "kubelet.config.k8s.io/v1beta1", "kind": "Other"},
    ],
)
def test_rejects_unknown_schema_instead_of_silently_defaulting(bad):
    with pytest.raises(AnsibleFilterError, match="schema"):
        kubelet_upgrade_config(bad, config())


def test_rejects_invalid_feature_gate_shape():
    with pytest.raises(AnsibleFilterError, match="mapping"):
        kubelet_upgrade_config(config(featureGates=[]), config())
