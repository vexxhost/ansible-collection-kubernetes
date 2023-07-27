#!/bin/bash

BINS=(
  kubeadm
  kubectl
  kubelet
)
ARCHS=(
  amd64
  arm64
)
VERSIONS=(
  1.19.16
  1.20.15
  1.21.14
  1.22.17
  1.23.17
  1.24.12
  1.25.12
  1.26.7
)

for b in "${BINS[@]}"; do
  echo "${b}_checksums:";
  for a in "${ARCHS[@]}"; do
    echo "  ${a}:";
    for i in "${VERSIONS[@]}"; do
      echo "    ${i}: $(curl -sL https://dl.k8s.io/v${i}/bin/linux/${a}/${b}.sha256)";
    done;
  done;
done;
