"""Regression tests for kube-vip Service-mode manifest rendering."""

from pathlib import Path

import pytest
import yaml
from ansible.plugins.filter.core import to_bool
from ansible.plugins.test.core import version_compare
from jinja2 import Environment, StrictUndefined

ROLE = Path(__file__).resolve().parents[2] / "roles" / "kube_vip"


@pytest.mark.parametrize("mode,expected_default", [("arp", True), ("bgp", False)])
@pytest.mark.parametrize("override", [None, True, False, "true", "false"])
def test_service_mode(mode, expected_default, override):
    env = Environment(undefined=StrictUndefined)
    env.filters["bool"] = to_bool
    env.filters["vexxhost.kubernetes.docker_image"] = lambda image, _: image
    env.tests["ansible.builtin.version"] = version_compare
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    default_value = env.from_string(defaults["kube_vip_services_enabled"]).render(
        kube_vip_mode=mode
    )
    assert to_bool(default_value) == expected_default
    value = default_value if override is None else override
    rendered = env.from_string(
        (ROLE / "templates/kube-vip.yaml.j2").read_text()
    ).render(
        kube_vip_mode=mode,
        kube_vip_services_enabled=value,
        kube_vip_interface="eth0",
        kube_vip_address="192.0.2.200",
        kube_vip_image="ghcr.io/kube-vip/kube-vip:v0.6.4",
        kubernetes_version="1.22.17",
    )
    pod = yaml.safe_load(rendered)
    entries = pod["spec"]["containers"][0]["env"]
    values = {entry["name"]: entry["value"] for entry in entries}
    assert len(values) == len(entries)
    assert values["svc_enable"] == str(to_bool(value)).lower()
    assert values["cp_enable"] == "true"
    assert values["vip_cidr"] == "32"
    if mode == "bgp":
        assert values["bgp_enable"] == "true"
        assert "vip_leaderelection" not in values
    else:
        assert values["vip_leaderelection"] == "true"
        assert values["svc_leasename"] == "plndr-svcs-lock"
