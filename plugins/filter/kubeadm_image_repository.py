# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Reconcile explicitly owned registry fields while keeping cluster settings."""

import copy

from ansible.errors import AnsibleFilterError


def kubeadm_image_repository(
    configuration,
    repository,
    default_repository="registry.k8s.io",
    default_dns_repository="registry.k8s.io/coredns",
):
    if not isinstance(configuration, dict):
        raise AnsibleFilterError("ClusterConfiguration must be a mapping")
    if (
        not isinstance(repository, str)
        or not repository.strip("/")
        or any(c.isspace() for c in repository)
        or "://" in repository
    ):
        raise AnsibleFilterError(
            "image repository must be a nonempty image prefix without a URL scheme"
        )
    repository = repository.rstrip("/")
    default = repository in ("registry.k8s.io", "k8s.gcr.io")
    desired = default_repository if default else repository
    dns_repository = default_dns_repository if default else repository + "/coredns"
    result = copy.deepcopy(configuration)
    if "dns" in result and not isinstance(result["dns"], dict):
        raise AnsibleFilterError("Stored DNS configuration must be a mapping")
    result["imageRepository"] = desired
    result.setdefault("dns", {})["imageRepository"] = dns_repository
    return result


class FilterModule:
    def filters(self):
        return {"kubeadm_image_repository": kubeadm_image_repository}
