# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Apply a hash migration plan from main.go to a metadata database."""

import importlib.util
import json
import pathlib
import sys

LIBRARY = (
    pathlib.Path(__file__).resolve().parents[2]
    / "plugins"
    / "module_utils"
    / "kubelet_hash_migration.py"
)

spec = importlib.util.spec_from_file_location("kubelet_hash_migration", LIBRARY)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

database, plan = sys.argv[1], json.load(open(sys.argv[2]))
print(json.dumps(migration.apply(plan, database), sort_keys=True))
