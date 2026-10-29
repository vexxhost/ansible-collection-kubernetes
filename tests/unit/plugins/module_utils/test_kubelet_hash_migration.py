# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the kubelet container hash migration."""

import json
import struct

import pytest
from ansible_collections.vexxhost.kubernetes.plugins.module_utils import (
    kubelet_hash_migration as migration,
)

PAGE_SIZE = 4096


def test_hash_matches_kubernetes():
    # NOTE: Expected value from TestHashContainer in
    #       pkg/kubelet/container/helpers_test.go (v1.31 through v1.36).
    assert migration.selected_fields_hash("test_container", "foo/image:v1") == (
        "8e45cbd0"
    )


def inspected(container_id, uid, name, old_hash):
    return {
        "status": {
            "id": container_id,
            "labels": {
                migration.POD_UID_LABEL: uid,
                migration.CONTAINER_NAME_LABEL: name,
            },
            "annotations": {migration.HASH_ANNOTATION: old_hash},
        }
    }


def test_plan_uses_pod_spec_images():
    image = "registry.example.com/app:v1@sha256:" + "0" * 64
    new_hash = migration.selected_fields_hash("app", image)
    containers = [
        inspected("a", "uid-1", "app", "1234abc"),
        inspected("b", "uid-2", "app", new_hash),
        inspected("c", "uid-unknown", "app", "1234abc"),
    ]

    plan = migration.plan_migrations(
        containers, {"uid-1": {"app": image}, "uid-2": {"app": image}}
    )

    assert plan["migrations"] == [
        {
            "container_id": "a",
            "name": "app",
            "image": image,
            "old_hash": "1234abc",
            "new_hash": new_hash,
        }
    ]
    assert plan["skipped"] == [
        {"container_id": "c", "name": "app", "uid": "uid-unknown"}
    ]


@pytest.mark.parametrize("size", [1, 126, 127, 128, 16383, 16384])
def test_any_round_trip(size):
    type_url = b"github.com/containerd/cri/pkg/store/container/Metadata"
    value = b"x" * size

    assert migration.decode_any(migration.encode_any(type_url, value)) == (
        type_url,
        value,
    )


def build_page(page_id, elements):
    """Build a BoltDB leaf page from (flags, key, value) tuples."""
    header = struct.pack("<QHHI", page_id, migration.BOLT_LEAF_PAGE, len(elements), 0)
    table = b""
    data = b""
    data_start = len(header) + 16 * len(elements)
    for index, (flags, key, value) in enumerate(elements):
        pos = data_start + len(data) - (len(header) + 16 * index)
        table += struct.pack("<IIII", flags, pos, len(key), len(value))
        data += key + value
    return header + table + data


def read_page(page, start=0):
    _, _, count, _ = struct.unpack_from("<QHHI", page, start)
    elements = []
    for index in range(count):
        element = start + 16 + 16 * index
        flags, pos, key_size, value_size = struct.unpack_from("<IIII", page, element)
        key_start = element + pos
        value_start = key_start + key_size
        value_end = value_start + value_size
        key = bytes(page[key_start:value_start])
        value = bytes(page[value_start:value_end])
        elements.append((flags, key, value))
    return elements


def metadata_any(hash_value):
    # NOTE: containerd stores compact JSON (Go's json.Marshal).
    payload = json.dumps(
        {"Config": {"annotations": {migration.HASH_ANNOTATION: hash_value}}},
        separators=(",", ":"),
    ).encode()
    return migration.encode_any(b"example.com/Metadata", payload)


def build_database(elements):
    meta = struct.pack("<QHHI", 0, migration.BOLT_META_PAGE, 0, 0)
    meta += struct.pack("<IIII", migration.BOLT_MAGIC, 2, PAGE_SIZE, 0)
    pages = [meta.ljust(PAGE_SIZE, b"\0"), b"\0" * PAGE_SIZE]
    pages.append(build_page(2, elements).ljust(PAGE_SIZE, b"\0"))
    return b"".join(pages)


def test_rewrite_database_handles_values_and_inline_buckets():
    inline = struct.pack("<QQ", 0, 0) + build_page(
        0, [(0, b"io.cri-containerd.container.metadata", metadata_any("abc1234"))]
    )
    database = build_database(
        [
            (0, b"spec", metadata_any("abc1234")),
            (migration.BOLT_BUCKET_LEAF, b"extensions", inline),
            (0, b"image", b"registry.example.com/app:v1"),
        ]
    )

    rewritten, counts = migration.rewrite_database(database, {"abc1234": "deadbeef"})

    assert len(rewritten) == len(database)
    assert counts == {"abc1234": 2}
    spec, extensions, image = read_page(rewritten, 2 * PAGE_SIZE)
    assert image == (0, b"image", b"registry.example.com/app:v1")
    for value in (spec[2], read_page(extensions[2], 16)[0][2]):
        _, payload = migration.decode_any(value)
        annotations = json.loads(payload)["Config"]["annotations"]
        assert annotations == {migration.HASH_ANNOTATION: "deadbeef"}


def test_rewrite_database_refuses_values_that_are_not_any_messages():
    database = build_database(
        [(0, b"raw", b'{"io.kubernetes.container.hash":"abc1234"}')]
    )

    with pytest.raises(migration.MigrationError):
        migration.rewrite_database(database, {"abc1234": "deadbeef"})


def test_apply_writes_backup_and_requires_every_hash(tmp_path):
    db_path = tmp_path / "meta.db"
    db_path.write_bytes(build_database([(0, b"spec", metadata_any("abc1234"))]))

    with pytest.raises(migration.MigrationError):
        migration.apply(
            [
                {"old_hash": "abc1234", "new_hash": "deadbeef"},
                {"old_hash": "1111111", "new_hash": "2222222"},
            ],
            str(db_path),
        )
    assert list(tmp_path.iterdir()) == [db_path]

    result = migration.apply(
        [{"old_hash": "abc1234", "new_hash": "deadbeef"}], str(db_path)
    )

    assert result["changed"] is True
    assert b"abc1234" in open(result["backup"], "rb").read()
    assert b"deadbeef" in db_path.read_bytes()


def test_pod_images_key_static_pods_by_mirror_uid():
    pods = [
        {
            "metadata": {"uid": "uid-1"},
            "spec": {"containers": [{"name": "app", "image": "example.com/app:v1"}]},
        },
        {
            "metadata": {
                "uid": "mirror-uid",
                "annotations": {migration.STATIC_POD_MIRROR_ANNOTATION: "static-uid"},
            },
            "spec": {
                "initContainers": [{"name": "init", "image": "example.com/init:v1"}],
                "containers": [
                    {"name": "kube-vip", "image": "example.com/kube-vip:v1"}
                ],
            },
        },
    ]

    static = {"init": "example.com/init:v1", "kube-vip": "example.com/kube-vip:v1"}
    assert migration.pod_images(pods) == {
        "uid-1": {"app": "example.com/app:v1"},
        "mirror-uid": static,
        "static-uid": static,
    }
