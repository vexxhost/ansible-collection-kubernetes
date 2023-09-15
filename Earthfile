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
  ARG capi=v$(grep cluster_api_core_version roles/cluster_api/defaults/main.yml | cut -d' ' -f2)
  ARG capo=v$(grep cluster_api_infrastructure_version roles/cluster_api/defaults/main.yml | cut -d' ' -f2)
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=core \
    --path=cluster-api \
    --version=${capi}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=bootstrap \
    --name=kubeadm \
    --version=${capi}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api \
    --type=control-plane \
    --name=kubeadm \
    --version=${capi}
  DO +DOWNLOAD_PROVIDER \
    --repository=kubernetes-sigs/cluster-api-provider-openstack \
    --type=infrastructure \
    --name=openstack \
    --version=${capo}

mkdocs-image:
  FROM squidfunk/mkdocs-material:9.1.15
  RUN pip install \
    mkdocs-literate-nav
  SAVE IMAGE mkdocs

mkdocs-serve:
  LOCALLY
  WITH DOCKER --load=+mkdocs-image
    RUN docker run --rm -p 8000:8000 -v ${PWD}:/docs mkdocs
  END

mkdocs-build:
  FROM +mkdocs-image
  COPY . /docs
  RUN mkdocs build
  RUN --push --secret GITHUB_TOKEN git remote set-url origin https://x-access-token:${GITHUB_TOKEN}@github.com/vexxhost/magnum-cluster-api.git
  RUN --push mkdocs gh-deploy --force
