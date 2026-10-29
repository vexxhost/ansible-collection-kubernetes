# Copyright (c) 2026 VEXXHOST, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Write the kubelet's actuated pod resources checkpoint.

From Kubernetes 1.35, in-place pod resize is always on and the kubelet keeps
the resources it has applied to each running container in
/var/lib/kubelet/actuated_pods_state.  A container without a record there is
treated as having no resources, so the kubelet tries to resize every running
container that has requests or limits.  On nodes running with
--cgroups-per-qos=false that resize panics in doPodResizeAction, and the
kubelet crash-loops.

Kubelets before 1.35 only write this file when in-place resize is enabled, so
a node upgraded from 1.34 has no records.  Before 1.35, in-place resize never
changed a running container, so the pod specs describe exactly what is
applied: this writes the checkpoint from them, the same way the kubelet
builds its allocated state (pkg/kubelet/allocation).

The checkpoint is JSON holding the data as a string and a checksum of it:
FNV-32a over spew's "%#v" rendering of a Go string, which is the string
prefixed with "(string)" (pkg/kubelet/checkpointmanager/checksum).
"""

import json

MIRROR_POD_ANNOTATION = "kubernetes.io/config.mirror"


def checksum(data):
    """Return the kubelet checkpoint checksum of a data string."""
    value = 0x811C9DC5
    for byte in ("(string)" + data).encode("utf-8"):
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def _marshal(value):
    # NOTE: Same output as Go's json.Marshal: compact, sorted map keys and
    #       HTML characters escaped.
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        text = text.replace(char, escaped)
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _resources(resources):
    # NOTE: Field order of v1.ResourceRequirements; empty fields are omitted.
    resources = resources or {}
    result = {}
    for field in ("limits", "requests"):
        if resources.get(field):
            result[field] = dict(sorted(resources[field].items()))
    if resources.get("claims"):
        result["claims"] = [
            {key: claim[key] for key in ("name", "request") if claim.get(key)}
            for claim in resources["claims"]
        ]
    return result


def pod_uid(pod):
    """Return the UID the kubelet uses for a pod (the config hash for static pods)."""
    metadata = pod.get("metadata", {})
    annotations = metadata.get("annotations") or {}
    return annotations.get(MIRROR_POD_ANNOTATION) or metadata["uid"]


def entries(pods):
    """Return the checkpoint entries for the given pods, keyed by pod UID."""
    result = {}
    for pod in pods:
        if pod.get("status", {}).get("phase") in ("Succeeded", "Failed"):
            continue
        spec = pod.get("spec", {})
        containers = {}
        for container in spec.get("containers") or []:
            containers[container["name"]] = _resources(container.get("resources"))
        for container in spec.get("initContainers") or []:
            if container.get("restartPolicy") == "Always":
                containers[container["name"]] = _resources(container.get("resources"))
        result[pod_uid(pod)] = {
            "ContainerResources": dict(sorted(containers.items())),
            "PodLevelResources": None,
        }
    return dict(sorted(result.items()))


def checkpoint(pods):
    """Return the checkpoint file content for the given pods."""
    data = _marshal({"entries": entries(pods)})
    return _marshal({"data": data, "checksum": checksum(data)})
