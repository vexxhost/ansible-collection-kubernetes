# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest
from ansible.errors import AnsibleFilterError
from ansible_collections.vexxhost.kubernetes.plugins.filter.version_ranges import (
    version_matching_ranges,
)

RANGES = [
    {"min": "1.35.0", "max": "1.36.0"},
    {"min": "1.36.0", "max": "1.36.8"},
]


@pytest.mark.parametrize(
    "version,count",
    [("1.34.9", 0), ("1.35.0", 1), ("1.36.0", 1), ("1.36.8", 0)],
)
def test_version_matching_ranges(version, count):
    assert len(version_matching_ranges(version, RANGES)) == count


def test_ranges_require_minimum_version():
    with pytest.raises(AnsibleFilterError):
        version_matching_ranges("1.35.0", [{"max": "1.36.0"}])
