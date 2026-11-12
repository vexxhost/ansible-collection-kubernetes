import copy

import pytest
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (
    kube_proxy_rules as rules,
)

RAW = """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:KUBE-FORWARD - [0:0]
:KUBE-FIREWALL - [0:0]
:CILIUM_FORWARD - [0:0]
:ts-forward - [0:0]
[1:80] -A FORWARD -m comment --comment "kubernetes forwarding rules" -j KUBE-FORWARD
[2:90] -A FORWARD -m comment --comment "cilium-feeder" -j CILIUM_FORWARD
-A FORWARD -j ts-forward
-A KUBE-FORWARD -m conntrack --ctstate INVALID -j DROP
-A KUBE-FIREWALL -s 127.0.0.0/8 -j DROP
-A CILIUM_FORWARD -i lxc+ -j ACCEPT
COMMIT
"""


def test_plan_removes_only_proxy_owned_hooks_and_chains():
    tables = rules.parse(RAW)
    original = copy.deepcopy(tables)
    plan, count = rules.cleanup_plan(tables)
    assert count == 1
    assert "-X KUBE-FORWARD" in plan
    assert "-F KUBE-FORWARD" in plan
    assert (
        '-D FORWARD -m comment --comment "kubernetes forwarding rules" -j KUBE-FORWARD'
        in plan
    )
    assert (
        "KUBE-FIREWALL" not in plan
        and "CILIUM" not in plan
        and "ts-forward" not in plan
    )
    assert tables == original


def test_counter_changes_do_not_change_rule_identity():
    assert rules.parse(RAW) == rules.parse(RAW.replace("[1:80]", "[500:90000]"))


def test_nonproxy_projection_keeps_rule_order_and_policy():
    before = rules.parse(RAW)
    after = copy.deepcopy(before)
    after["filter"]["chains"].pop("KUBE-FORWARD")
    after["filter"]["rules"] = [
        r
        for r in after["filter"]["rules"]
        if r[1] != "KUBE-FORWARD" and rules.target(r) != "KUBE-FORWARD"
    ]
    assert rules.projection(before) == rules.projection(after)
    assert rules.cleanup_plan(after)[1] == 0
    restored = rules.restore_plan(before, after)
    assert "-I FORWARD 1" in restored
    assert "-A KUBE-FORWARD" in restored
    assert "-F KUBE-FORWARD" in restored
    assert "CILIUM" not in restored


@pytest.mark.parametrize(
    "name", ["KUBE-FIREWALL", "KUBE-IPTABLES-HINT", "KUBE-KUBELET-CANARY"]
)
def test_kubelet_chains_are_not_proxy_owned(name):
    assert not rules.owned(name)


def test_unknown_owner_blocks_cleanup():
    with pytest.raises(ValueError, match="Unknown"):
        rules.cleanup_plan(
            rules.parse(RAW.replace(":INPUT", ":KUBE-OTHER - [0:0]\n:INPUT"))
        )


def test_custom_chain_reference_blocks_cleanup():
    raw = RAW.replace(":INPUT", ":CUSTOM - [0:0]\n:INPUT").replace(
        "-A FORWARD -m comment", "-A CUSTOM -m comment", 1
    )
    with pytest.raises(ValueError, match="Unexpected"):
        rules.cleanup_plan(rules.parse(raw))


def test_restore_is_idempotent_for_existing_hooks():
    original = rules.parse(RAW)
    assert "-I FORWARD" not in rules.restore_plan(original, original)


def test_renderer_rejects_control_characters():
    with pytest.raises(ValueError):
        rules.render(["--comment", "bad\nCOMMIT"])
