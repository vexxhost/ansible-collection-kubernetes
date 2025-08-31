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
  1.24.17
  1.25.8
  1.25.16
  1.26.3
  1.26.11
  1.26.15
  1.27.8
  1.27.16
  1.28.4
  1.28.13
  1.30.14
  1.31.12
  1.32.8
  1.33.4
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
