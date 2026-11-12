from types import SimpleNamespace

import pytest
from ansible_collections.vexxhost.kubernetes.plugins.modules import (
    kube_proxy_state as module,
)

RAW = """*filter
:FORWARD ACCEPT [0:0]
:KUBE-FORWARD - [0:0]
:KUBE-FIREWALL - [0:0]
-A FORWARD -m comment --comment "kubernetes forwarding rules" -j KUBE-FORWARD
-A KUBE-FORWARD -m conntrack --ctstate INVALID -j DROP
-A KUBE-FIREWALL -s 127.0.0.0/8 -j DROP
COMMIT
"""
CLEAN = """*filter
:FORWARD ACCEPT [0:0]
:KUBE-FIREWALL - [0:0]
-A KUBE-FIREWALL -s 127.0.0.0/8 -j DROP
COMMIT
"""


class Result(BaseException):
    def __init__(self, value):
        self.value = value


def invoke(monkeypatch, tmp_path, state="checked", fail_family=None, check_mode=False):
    actual = {"iptables-save": RAW, "ip6tables-save": RAW}
    calls = []
    failed = []

    class Fake:
        def __init__(self):
            self.params = {"state": state}

        def exit_json(self, **kwargs):
            raise Result({"failed": False, **kwargs})

        def fail_json(self, **kwargs):
            raise Result({"failed": True, **kwargs})

    fake = Fake()
    fake.check_mode = check_mode

    def command(argv, body=None, **kwargs):
        calls.append((argv, body))
        if argv[0].endswith("-save"):
            return SimpleNamespace(stdout=actual[argv[0]])
        family = "iptables-save" if argv[0] == "iptables-restore" else "ip6tables-save"
        if "--test" not in argv:
            if fail_family == family and not failed:
                failed.append(True)
                raise RuntimeError("injected restore failure")
            actual[family] = (
                RAW if "-I FORWARD" in body or "-A KUBE-FORWARD" in body else CLEAN
            )
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(module, "AnsibleModule", lambda **kw: fake)
    monkeypatch.setattr(module, "command", command)
    monkeypatch.setattr(module, "containers_without_proxy", list)
    monkeypatch.setattr(module, "replacement_ready", lambda: "same-agent")
    monkeypatch.setattr(module.os, "umask", lambda value: None)
    directory = tmp_path / "backup"
    directory.mkdir()
    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda **kw: str(directory))
    with pytest.raises(Result) as result:
        module.main()
    return result.value.value, actual, calls, directory


def test_default_guard_is_read_only_and_reports_orphans(monkeypatch, tmp_path):
    value, _actual, calls, _ = invoke(monkeypatch, tmp_path)
    assert value["failed"] and not value["changed"]
    assert value["proxy_chains"] == {"v4": 1, "v6": 1}
    assert all(argv[0].endswith("-save") for argv, body in calls)


def test_explicit_recovery_checks_both_families_and_saves_originals(
    monkeypatch, tmp_path
):
    value, actual, calls, directory = invoke(monkeypatch, tmp_path, "absent")
    assert not value["failed"] and value["changed"]
    assert all(raw == CLEAN for raw in actual.values())
    assert (directory / "before.v4").read_text() == RAW
    assert (directory / "before.v6").read_text() == RAW
    assert sum("--test" in argv for argv, _ in calls) == 2


def test_failed_second_family_restores_first_without_full_table_flush(
    monkeypatch, tmp_path
):
    value, actual, calls, _ = invoke(monkeypatch, tmp_path, "absent", "ip6tables-save")
    assert value["failed"] and not value["rollback_errors"]
    assert all(raw == RAW for raw in actual.values())
    assert all(
        "--noflush" in argv for argv, body in calls if argv[0].endswith("-restore")
    )


def test_check_mode_never_applies_recovery(monkeypatch, tmp_path):
    value, actual, calls, _ = invoke(monkeypatch, tmp_path, "absent", check_mode=True)
    assert not value["failed"] and value["changed"]
    assert all(raw == RAW for raw in actual.values())
    assert all(argv[0].endswith("-save") for argv, _ in calls)


def test_replacement_requires_enabled_healthy_mode(monkeypatch):
    monkeypatch.setattr(
        module,
        "containers_without_proxy",
        lambda: [{"metadata": {"name": "cilium-agent"}, "id": "agent"}],
    )
    monkeypatch.setattr(
        module,
        "command",
        lambda *a, **kw: SimpleNamespace(
            stdout='{"cilium":{"state":"Ok"},"kube-proxy-replacement":{"mode":"False"}}'
        ),
    )
    with pytest.raises(RuntimeError, match="not healthy"):
        module.replacement_ready()
