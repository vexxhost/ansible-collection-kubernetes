#!/bin/bash

# Copyright (c) 2023 VEXXHOST, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# This script is used to sync the charts from the upstream repositories into
# the charts directory.  It is used to update the charts to the versions which
# are defined in this file.

set -xe

# Determine the root path
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"

# Clean-up all of the existing charts
rm -rfv ${ROOT}/charts/*

CERT_MANAGER_VERSION=v1.7.1
curl -sL https://charts.jetstack.io/charts/cert-manager-${CERT_MANAGER_VERSION}.tgz \
  | tar -xz -C ${ROOT}/charts

CILIUM_VERSION=1.13.3
curl -sL https://helm.cilium.io/cilium-${CILIUM_VERSION}.tgz \
  | tar -xz -C ${ROOT}/charts
