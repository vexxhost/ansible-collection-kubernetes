VERSION 0.7

CURL_IF_UPDATED:
  COMMAND
  ARG --required url
  ARG --required path
  RUN curl \
    -sL ${url} \
    -z ${path} \
    -o ${path}

DOWNLOAD_PROVIDER:
  COMMAND
  ARG --required repository
  ARG --required type
  ARG name
  ARG --required version
  ARG path=${type}-${name}
  RUN mkdir -p roles/cluster_api/files/providers/${path}/${version}
  DO +CURL_IF_UPDATED \
    --url=https://github.com/${repository}/releases/download/${version}/${type}-components.yaml \
    --path=roles/cluster_api/files/providers/${path}/${version}/${type}-components.yaml
  DO +CURL_IF_UPDATED \
    --url=https://github.com/${repository}/releases/download/${version}/metadata.yaml \
    --path=roles/cluster_api/files/providers/${path}/${version}/metadata.yaml

vendor.cluster-api:
  LOCALLY
  ARG capi_version=v$(grep cluster_api_core_version roles/cluster_api/defaults/main.yml | cut -d' ' -f2)
  ARG capo_version=v$(grep cluster_api_infrastructure_version roles/cluster_api/defaults/main.yml | cut -d' ' -f2)
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=core \
    --path=cluster-api \
    --version=${capi_version}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=bootstrap \
    --name=kubeadm \
    --version=${capi_version}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=control-plane \
    --name=kubeadm \
    --version=${capi_version}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api-provider-openstack \
    --type=infrastructure \
    --name=openstack \
    --version=${capo_version}
