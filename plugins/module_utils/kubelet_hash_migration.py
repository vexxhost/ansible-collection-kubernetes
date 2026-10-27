# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Migrate kubelet container hashes across the Kubernetes 1.31 boundary.

Kubernetes 1.31 changed how the kubelet hashes a container: it used to hash
the whole container spec, and now hashes only its name and image (see
kubernetes/kubernetes#124220).  The kubelet stores the hash as the
"io.kubernetes.container.hash" annotation on every container and restarts a
container when it no longer matches, so upgrading a kubelet from 1.30 to 1.31
restarts every running container on the node.

This rewrites the stored annotation to the 1.31 value so the new kubelet
keeps existing containers running.  It is used by the
vexxhost.kubernetes.kubelet_container_hash_migration module and needs the
standard library only.

collect() reads running containers through crictl and computes the new hashes
from the pod specs (the images exactly as written in the pod spec, which is
what the kubelet hashes).  apply() rewrites containerd's metadata database,
which must not be in use (containerd stopped).

containerd keeps container records in a BoltDB file as protobuf-encoded
google.protobuf.Any messages whose value is JSON.  Hashes are hex without
leading zeros, so the new value can be shorter or longer than the old one.
Each affected value is decoded, rewritten and re-encoded with the correct
lengths, and the leaf page holding it is repacked within its existing
allocation.  Anything unexpected (inline buckets, values that are not Any
messages, pages without room) aborts the migration without writing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import shutil
import struct
import subprocess
import tempfile
import time

HASH_ANNOTATION = "io.kubernetes.container.hash"
POD_UID_LABEL = "io.kubernetes.pod.uid"
CONTAINER_NAME_LABEL = "io.kubernetes.container.name"
STATIC_POD_MIRROR_ANNOTATION = "kubernetes.io/config.mirror"
CONTAINERD_METADATA_DB = "/var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db"

BOLT_MAGIC = 0xED0CDAED
BOLT_PAGE_HEADER = struct.Struct("<QHHI")
BOLT_LEAF_ELEMENT = struct.Struct("<IIII")
BOLT_BRANCH_PAGE = 0x01
BOLT_LEAF_PAGE = 0x02
BOLT_META_PAGE = 0x04
BOLT_FREELIST_PAGE = 0x10
BOLT_BUCKET_LEAF = 0x01


class MigrationError(Exception):
    pass


def selected_fields_hash(name, image):
    """Return the Kubernetes 1.31+ container hash for a name and image.

    This matches HashContainer() in pkg/kubelet/container/helpers.go: the
    JSON encoding of {"image": ..., "name": ...} is formatted by
    hashutil.DeepHashObject (spew "%#v" of a []byte) and hashed with
    FNV-1a 32-bit.  The kubelet formats the result with
    strconv.FormatUint(hash, 16), so there is no zero padding.
    """
    payload = json.dumps(
        {"image": image, "name": name}, separators=(",", ":"), sort_keys=True
    ).encode()
    spew = "([]uint8)[" + " ".join(str(byte) for byte in payload) + "]"

    value = 0x811C9DC5
    for byte in spew.encode():
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return format(value, "x")


def valid_hash(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 8
        and all(char in "0123456789abcdef" for char in value)
    )


def _crictl(*args):
    return subprocess.run(
        ["crictl", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    ).stdout


def pod_images(pods):
    """Map pod UID to container name to image, as written in the pod specs.

    Static pods are keyed by the UID in their mirror pod annotation, which is
    the UID the kubelet uses for their containers.
    """
    images = {}
    for pod in pods:
        metadata = pod.get("metadata") or {}
        spec = pod.get("spec") or {}
        containers = dict(
            (container["name"], container.get("image", ""))
            for container in (spec.get("initContainers") or [])
            + (spec.get("containers") or [])
        )
        images[metadata.get("uid")] = containers
        mirror = (metadata.get("annotations") or {}).get(STATIC_POD_MIRROR_ANNOTATION)
        if mirror:
            images[mirror] = containers
    return images


def plan_migrations(containers, images):
    """Compute hash migrations for inspected containers.

    containers: crictl inspect output for each running container.
    images: {pod UID: {container name: image as written in the pod spec}}.
    """
    migrations = []
    skipped = []
    for container in containers:
        status = container.get("status") or {}
        labels = status.get("labels") or {}
        annotations = status.get("annotations") or {}
        container_id = status.get("id", "")
        old_hash = annotations.get(HASH_ANNOTATION)
        uid = labels.get(POD_UID_LABEL)
        name = labels.get(CONTAINER_NAME_LABEL)
        if not (old_hash and uid and name):
            continue

        image = (images.get(uid) or {}).get(name)
        if image is None:
            skipped.append({"container_id": container_id, "name": name, "uid": uid})
            continue

        new_hash = selected_fields_hash(name, image)
        if not valid_hash(old_hash):
            raise MigrationError(f"unexpected hash {old_hash!r} on {container_id}")
        if old_hash != new_hash:
            migrations.append(
                {
                    "container_id": container_id,
                    "name": name,
                    "image": image,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                }
            )
    return {"containers": len(containers), "migrations": migrations, "skipped": skipped}


def collect(images):
    try:
        container_ids = [line for line in _crictl("ps", "-q").splitlines() if line]
        containers = [
            json.loads(_crictl("inspect", "--output", "json", container_id))
            for container_id in container_ids
        ]
    except subprocess.CalledProcessError as exc:
        raise MigrationError(f"crictl failed: {exc.stderr or exc}")
    return plan_migrations(containers, images)


def _read_varint(data, offset):
    value = 0
    shift = 0
    while True:
        if offset >= len(data) or shift > 63:
            raise MigrationError("truncated protobuf varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def _write_varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_any(data):
    """Decode a google.protobuf.Any into (type_url, value)."""
    fields = {}
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        field, wire_type = key >> 3, key & 0x07
        if field not in (1, 2) or wire_type != 2 or field in fields:
            raise MigrationError("value is not a protobuf Any message")
        length, offset = _read_varint(data, offset)
        if offset + length > len(data):
            raise MigrationError("truncated protobuf Any message")
        end = offset + length
        fields[field] = data[offset:end]
        offset = end
    return fields.get(1, b""), fields.get(2, b"")


def encode_any(type_url, value):
    out = bytearray()
    for field, payload in ((1, type_url), (2, value)):
        if payload:
            out += _write_varint((field << 3) | 2)
            out += _write_varint(len(payload))
            out += payload
    return bytes(out)


def _tokens(replacements):
    return [
        (
            old,
            f'"{HASH_ANNOTATION}":"{old}"'.encode(),
            f'"{HASH_ANNOTATION}":"{new}"'.encode(),
        )
        for old, new in sorted(replacements.items())
    ]


def rewrite_value(value, tokens, counts):
    """Rewrite hash annotations inside a protobuf Any value, if present."""
    if not any(old_token in value for _, old_token, _ in tokens):
        return value

    type_url, payload = decode_any(value)
    for old, old_token, new_token in tokens:
        occurrences = payload.count(old_token)
        if occurrences:
            payload = payload.replace(old_token, new_token)
            counts[old] += occurrences
    json.loads(payload)
    if any(old_token in type_url for _, old_token, _ in tokens):
        raise MigrationError("hash annotation found outside the Any value")
    return encode_any(type_url, payload)


def _rewrite_elements(page, start, end, count, tokens, counts, inline):
    """Rewrite the values of a leaf page's elements.

    Returns (elements, changed) where elements are (header offset, flags,
    key, value) tuples, or (None, False) if the page does not look like a
    live leaf page.
    """
    data_start = start + BOLT_PAGE_HEADER.size + count * BOLT_LEAF_ELEMENT.size
    elements = []
    changed = False
    for index in range(count):
        element = start + BOLT_PAGE_HEADER.size + index * BOLT_LEAF_ELEMENT.size
        flags, pos, key_size, value_size = BOLT_LEAF_ELEMENT.unpack_from(page, element)
        key_start = element + pos
        value_start = key_start + key_size
        value_end = value_start + value_size
        if not data_start <= key_start <= value_start <= value_end <= end:
            if inline:
                raise MigrationError("invalid inline bucket page")
            return None, False
        key = bytes(page[key_start:value_start])
        value = bytes(page[value_start:value_end])

        if not flags & BOLT_BUCKET_LEAF:
            new_value = rewrite_value(value, tokens, counts)
        elif any(old_token in value for _, old_token, _ in tokens):
            if inline:
                raise MigrationError("nested inline bucket")
            new_value = rewrite_inline_bucket(value, tokens, counts)
        else:
            new_value = value
        changed = changed or new_value != value
        elements.append((element - start, flags, key, new_value))
    return elements, changed


def _pack_elements(page, start, end, elements):
    """Write elements back into a leaf page that starts at start."""
    cursor = start + BOLT_PAGE_HEADER.size + len(elements) * BOLT_LEAF_ELEMENT.size
    for element, flags, key, value in elements:
        if cursor + len(key) + len(value) > end:
            raise MigrationError("rewritten values do not fit in their BoltDB page")
        BOLT_LEAF_ELEMENT.pack_into(
            page, start + element, flags, cursor - start - element, len(key), len(value)
        )
        record = key + value
        record_end = cursor + len(record)
        page[cursor:record_end] = record
        cursor = record_end
    page[cursor:end] = b"\x00" * (end - cursor)
    return cursor


def rewrite_inline_bucket(value, tokens, counts):
    """Rewrite an inline bucket: a bucket header followed by a leaf page.

    BoltDB stores small buckets without sub-buckets inside their parent's
    value.  The embedded page has its own element offsets and sizes, so it is
    rebuilt, and the parent value changes size.
    """
    root, sequence = struct.unpack_from("<QQ", value, 0)
    if root != 0 or len(value) < 16 + BOLT_PAGE_HEADER.size:
        raise MigrationError("hash annotation found in a bucket header")
    page = bytearray(value[16:])
    _, flags, count, _ = BOLT_PAGE_HEADER.unpack_from(page, 0)
    if flags != BOLT_LEAF_PAGE:
        raise MigrationError("inline bucket is not a leaf page")
    elements, _ = _rewrite_elements(page, 0, len(page), count, tokens, counts, True)
    size = BOLT_PAGE_HEADER.size + count * BOLT_LEAF_ELEMENT.size
    size += sum(len(key) + len(element_value) for _, _, key, element_value in elements)
    rebuilt = bytearray(size)
    rebuilt[: BOLT_PAGE_HEADER.size] = page[: BOLT_PAGE_HEADER.size]
    _pack_elements(rebuilt, 0, size, elements)
    return struct.pack("<QQ", root, sequence) + bytes(rebuilt)


def bolt_page_size(data):
    if len(data) < 2 * BOLT_PAGE_HEADER.size + 16:
        raise MigrationError("metadata database is too small")
    magic, _, page_size, _ = struct.unpack_from("<IIII", data, BOLT_PAGE_HEADER.size)
    if magic != BOLT_MAGIC:
        raise MigrationError("metadata database is not a BoltDB file")
    if page_size < 512 or page_size > 65536 or len(data) % page_size:
        raise MigrationError(f"invalid BoltDB page size {page_size}")
    return page_size


def rewrite_database(data, replacements):
    """Return (data, counts) with hash annotations replaced in a BoltDB file."""
    page_size = bolt_page_size(data)
    tokens = _tokens(replacements)
    counts = {old: 0 for old in replacements}
    updated = bytearray(data)

    offset = 0
    while offset < len(updated):
        page_id, flags, count, overflow = BOLT_PAGE_HEADER.unpack_from(updated, offset)
        page_end = offset + (overflow + 1) * page_size
        # NOTE: Unused pages can hold stale bytes, so only trust headers that
        #       carry their own page id and a known page type.
        if (
            page_id != offset // page_size
            or flags
            not in (
                BOLT_BRANCH_PAGE,
                BOLT_LEAF_PAGE,
                BOLT_META_PAGE,
                BOLT_FREELIST_PAGE,
            )
            or page_end > len(updated)
        ):
            offset += page_size
            continue

        if flags == BOLT_LEAF_PAGE and count:
            _rewrite_leaf_page(updated, offset, page_end, count, tokens, counts)
        offset = page_end

    return bytes(updated), counts


def _rewrite_leaf_page(page, start, end, count, tokens, counts):
    # NOTE: Pages that do not parse as live leaf pages (for example, stale
    #       free pages) are left untouched.
    elements, changed = _rewrite_elements(
        page, start, end, count, tokens, counts, False
    )
    if changed:
        _pack_elements(page, start, end, elements)


def apply(migrations, db_path=CONTAINERD_METADATA_DB):
    replacements = {}
    for migration in migrations:
        old, new = migration.get("old_hash"), migration.get("new_hash")
        if not (valid_hash(old) and valid_hash(new)):
            raise MigrationError(f"invalid migration entry {migration!r}")
        if replacements.setdefault(old, new) != new:
            raise MigrationError(f"hash {old} maps to more than one new hash")
    if not replacements:
        return {"changed": False}

    with open(db_path, "rb") as db_file:
        data = db_file.read()
    rewritten, counts = rewrite_database(data, replacements)

    missing = sorted(old for old, found in counts.items() if not found)
    if missing:
        raise MigrationError(f"hashes not found in the database: {missing}")
    leftover = [old for old, token, _ in _tokens(replacements) if token in rewritten]
    if leftover:
        raise MigrationError(f"hashes left in the database: {sorted(leftover)}")

    backup = f"{db_path}.pre-kubelet-hash-migration-{time.strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(db_path, backup)
    db_dir = os.path.dirname(db_path)
    fd, tmp_path = tempfile.mkstemp(prefix=".meta.db.", dir=db_dir)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(rewritten)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        shutil.copystat(db_path, tmp_path)
        db_stat = os.stat(db_path)
        os.chown(tmp_path, db_stat.st_uid, db_stat.st_gid)
        os.replace(tmp_path, db_path)
        dir_fd = os.open(db_dir, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {"changed": True, "backup": backup, "replacements": counts}
