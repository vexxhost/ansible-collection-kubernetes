#!/usr/bin/env bash

# Copyright (c) 2025 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

set -eo pipefail

# This script bumps Kubernetes component versions and checksums in defaults/main.yml files
# for kubeadm, kubectl, and kubelet roles. It uses versions from endoflife.date
# and fetches checksums from the official Kubernetes release site.

# Advanced version selection starting from 1.19.16
# For 1.19: only include 1.19.16
# For 1.20+: include all patch versions from .0 to latest
get_kubernetes_versions() {
	local releases_json=$(curl -s https://endoflife.date/api/v1/products/kubernetes)

	# Get all release cycles starting from 1.19 onwards
	local cycles=$(echo "$releases_json" | jq -r '.result.releases[] | select(.name | test("^1\\.(1[9]|[2-9][0-9])$")) | "\(.name):\(.latest.name)"')

	local versions=()

	while IFS=: read -r minor_version latest_version; do
		local latest_patch=$(echo "$latest_version" | cut -d. -f3)

		if [[ "$minor_version" == "1.19" ]]; then
			# For 1.19, only include 1.19.16
			versions+=("1.19.16")
		else
			# For 1.20+, include all patches from .0 to latest
			for ((patch=0; patch<=latest_patch; patch++)); do
				versions+=("$minor_version.$patch")
			done
		fi
	done <<< "$cycles"

	# Remove duplicates and sort
	printf '%s\n' "${versions[@]}" | sort -V | uniq
}

VERSIONS=$(get_kubernetes_versions)

# Display available Kubernetes versions
echo "Available Kubernetes versions:"
for version in $VERSIONS; do
	echo "  - $version"
done
echo

# Architectures to support
ARCHES=(amd64 arm64)

# Components and their roles
COMPONENTS="kubeadm:roles/kubeadm/defaults/main.yml kubectl:roles/kubectl/defaults/main.yml kubelet:roles/kubelet/defaults/main.yml"

# Function to fetch checksum for a given component, version, and arch
fetch_checksum() {
	local component="$1"
	local version="$2"
	local arch="$3"
	curl -sSL "https://dl.k8s.io/release/v${version}/bin/linux/${arch}/${component}.sha256" || echo ""
}

# Function to extract existing checksums from YAML file
extract_existing_checksums() {
	local yaml_file="$1"
	local component="$2"
	awk -v component="${component}_checksums:" '
		$0 ~ component { in_checksums=1; next }
		in_checksums && /^[a-zA-Z_]+_/ && !/^  / { in_checksums=0 }
		in_checksums && /^  [a-z0-9]+:/ { arch=$1; gsub(/:/, "", arch); current_arch=arch; next }
		in_checksums && /^    [0-9.]+:/ {
			version=$1; gsub(/:/, "", version);
			checksum=$2;
			print current_arch ":" version ":" checksum
		}
	' "$yaml_file"
}

# Update YAML files
for component_pair in $COMPONENTS; do
	component="${component_pair%:*}"
	yaml_file="${component_pair#*:}"
	echo "Updating $component checksums in $yaml_file"

	# Extract existing checksums to a temporary file
	existing_checksums_file=$(mktemp)
	extract_existing_checksums "$yaml_file" "$component" > "$existing_checksums_file"

	# Prepare new checksums block
	echo "${component}_checksums:" > "${yaml_file}.new"
	for arch in "${ARCHES[@]}"; do
		echo "  $arch:" >> "${yaml_file}.new"

		# Get all versions (existing + new ones) and sort them properly
		all_versions=$(
			{
				echo "$VERSIONS"
				awk -F: -v arch="$arch" '$1 == arch {print $2}' "$existing_checksums_file"
			} | sort -V | uniq
		)

		for version in $all_versions; do
			# Check if we have an existing checksum
			existing_checksum=$(awk -F: -v arch="$arch" -v ver="$version" '$1 == arch && $2 == ver {print $3}' "$existing_checksums_file")

			# Always fetch the online checksum to verify
			online_checksum=$(fetch_checksum "$component" "$version" "$arch")

			if [[ -n "$online_checksum" ]]; then
				if [[ -n "$existing_checksum" ]]; then
					if [[ "$existing_checksum" != "$online_checksum" ]]; then
						echo "    WARNING: Checksum mismatch for $component $version ($arch)"
						echo "             Existing: $existing_checksum"
						echo "             Online:   $online_checksum"
						echo "             Using online version."
					fi
				fi
				# Always use the online checksum when available
				echo "    $version: $online_checksum" >> "${yaml_file}.new"
			elif [[ -n "$existing_checksum" ]]; then
				# Online checksum not available, use existing
				echo "    WARNING: Could not fetch online checksum for $component $version ($arch), using existing"
				echo "    $version: $existing_checksum" >> "${yaml_file}.new"
			fi
		done
	done

	# Replace old checksums block in YAML file
	# First, extract everything before checksums (including comments and headers)
	awk '/^[a-zA-Z_]+_checksums:/ {exit} {print}' "$yaml_file" > "${yaml_file}.tmp"

	# Add new checksums
	cat "${yaml_file}.new" >> "${yaml_file}.tmp"

	# Add blank line after checksums
	echo "" >> "${yaml_file}.tmp"

	# Add everything after checksums block
	awk '
		BEGIN { after_checksums = 0 }
		/^[a-zA-Z_]+_checksums:/ {
			in_checksums = 1
			next
		}
		in_checksums && /^[a-zA-Z_]+/ && !/^  / {
			after_checksums = 1
			in_checksums = 0
		}
		after_checksums { print }
	' "$yaml_file" >> "${yaml_file}.tmp"
	mv "${yaml_file}.tmp" "$yaml_file"
	rm "${yaml_file}.new" "$existing_checksums_file"

done

echo "Kubernetes component versions and checksums updated."
