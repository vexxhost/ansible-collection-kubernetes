# Changelog

## [1.10.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.9.1...v1.10.0) (2023-10-13)


### Features

* upgrade CAPI version to 1.5.1 ([#62](https://github.com/vexxhost/ansible-collection-kubernetes/issues/62)) ([65f8a63](https://github.com/vexxhost/ansible-collection-kubernetes/commit/65f8a63ea06d062334822330f3d958f98d5f7e2a))

## [1.9.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.9.0...v1.9.1) (2023-09-25)


### Bug Fixes

* Update CAPO version ([#58](https://github.com/vexxhost/ansible-collection-kubernetes/issues/58)) ([c204d44](https://github.com/vexxhost/ansible-collection-kubernetes/commit/c204d448d535d7442e97549d4980d85c429cf22a))


### Documentation

* add upgrade docs ([#40](https://github.com/vexxhost/ansible-collection-kubernetes/issues/40)) ([e9cb5dd](https://github.com/vexxhost/ansible-collection-kubernetes/commit/e9cb5dd8dfdca8f2872eccd37fe26707a0b44dca))

## [1.9.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.8.2...v1.9.0) (2023-09-15)


### Features

* add offline installs for capi ([#56](https://github.com/vexxhost/ansible-collection-kubernetes/issues/56)) ([cdf3ddb](https://github.com/vexxhost/ansible-collection-kubernetes/commit/cdf3ddbca0b1da08ee73885de45ac4456d9f2c56))

## [1.8.2](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.8.1...v1.8.2) (2023-09-06)


### Bug Fixes

* loosen kubernetes.core to above 2.3.2 ([f7ce48f](https://github.com/vexxhost/ansible-collection-kubernetes/commit/f7ce48fa3d61949d9ae9c75f8d1fb6efd7e59733))

## [1.8.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.8.0...v1.8.1) (2023-08-23)


### Bug Fixes

* Set default values for imagePullPolicy in kubeadmConfigSpec of CRDs ([ebf9dd1](https://github.com/vexxhost/ansible-collection-kubernetes/commit/ebf9dd100ef133153d1632e786a771440bc0d420))

## [1.8.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.7.2...v1.8.0) (2023-07-26)


### Features

* Set node selector for CAPI components ([6719b63](https://github.com/vexxhost/ansible-collection-kubernetes/commit/6719b639696c067ad70030dd0c11b8279470b91e))

## [1.7.2](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.7.1...v1.7.2) (2023-07-21)


### Bug Fixes

* use kubelet_hostname instead of inventory_hostname_short ([5c08c72](https://github.com/vexxhost/ansible-collection-kubernetes/commit/5c08c72a944c2cc53f1eca09eecf7112b6805a53))
* use SSH ARGs from command line if provided ([39fcd5c](https://github.com/vexxhost/ansible-collection-kubernetes/commit/39fcd5c14ade33f17ae79a942ffcb748689c6724))

## [1.7.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.7.1...v1.7.1) (2023-07-05)


### Features

* add capi ([6f5a8f1](https://github.com/vexxhost/ansible-collection-kubernetes/commit/6f5a8f149c043e8ad285f34eab0a0e247dd7cb4b))
* **helm:** add role ([a3e74bc](https://github.com/vexxhost/ansible-collection-kubernetes/commit/a3e74bc086d4352e69820dddf8ea5e1f2dd3a8f2))
* **k8s:** add roles ([#2](https://github.com/vexxhost/ansible-collection-kubernetes/issues/2)) ([7d883be](https://github.com/vexxhost/ansible-collection-kubernetes/commit/7d883be1c411d4eb5a9f43c443f21f37c8390650))
* **role:cilium:** Upgrade cilium version ([e783aad](https://github.com/vexxhost/ansible-collection-kubernetes/commit/e783aad4190a797c3037849f176e07b179aace23))
* support multiple k8s versions ([7b03230](https://github.com/vexxhost/ansible-collection-kubernetes/commit/7b03230dbc29869df921c90fb59c9ce6bd5feab8))
* update CAPI release ([faf7048](https://github.com/vexxhost/ansible-collection-kubernetes/commit/faf7048aa167314b850b1b4fff817472d5688b4c))


### Bug Fixes

* add checksums + linters ([e1956c1](https://github.com/vexxhost/ansible-collection-kubernetes/commit/e1956c1d0e32835ff5f9ebb877ec4911459277bc))
* add synchornize workaround ([db81203](https://github.com/vexxhost/ansible-collection-kubernetes/commit/db81203c80ba2e37f0a04054861fa1db8f306558))
* adjust package dependencies for rocky linux ([c698d41](https://github.com/vexxhost/ansible-collection-kubernetes/commit/c698d413591fc10838133e0c4b22e1113ea358f7))
* avoid trailing slash with prefix ([5a3f11e](https://github.com/vexxhost/ansible-collection-kubernetes/commit/5a3f11e6bf9601adc03e014aab8857742e1a9e24))
* bump cilium version ([5b12aeb](https://github.com/vexxhost/ansible-collection-kubernetes/commit/5b12aeb647a15b6f83513752897ad449741daca4))
* **containerd:** bump to 100G ([858e977](https://github.com/vexxhost/ansible-collection-kubernetes/commit/858e977e4a8532a5375422f140cb120183ef6648))
* **containerd:** properly forget package ([2bbb2f7](https://github.com/vexxhost/ansible-collection-kubernetes/commit/2bbb2f7eb9c96c48df8cde99d57a2d74fc5f95b8))
* **containerd:** re-add missing containerd_download_unarchive_dest ([74a58af](https://github.com/vexxhost/ansible-collection-kubernetes/commit/74a58afa0616fe6c27c45bd571de7f50473eca52))
* forget packages instead of remove them ([eda79d4](https://github.com/vexxhost/ansible-collection-kubernetes/commit/eda79d4551f3764df0e7747c39a48c3b565a020b))
* **helm:** install curl-minimal for el9 ([420af8a](https://github.com/vexxhost/ansible-collection-kubernetes/commit/420af8a87b16453c63630ae676dbc56f68db679f))
* idempotence ([3d05147](https://github.com/vexxhost/ansible-collection-kubernetes/commit/3d0514753f2393c16cc0e65bd770855280133978))
* make kube component versioning consistent ([8d6df7e](https://github.com/vexxhost/ansible-collection-kubernetes/commit/8d6df7e82794b9337da12d5fcf46ae865b1d8c44))
* only override if registry isn't default ([3270fdd](https://github.com/vexxhost/ansible-collection-kubernetes/commit/3270fdddaed5d86e8c133dce510939af6154bfbf))
* refactor {atmosphere,kubernetes}_image_repository ([4ffc20b](https://github.com/vexxhost/ansible-collection-kubernetes/commit/4ffc20bd032715c953cca91c32843db9fd70e5d1))
* restore symlinks ([7648382](https://github.com/vexxhost/ansible-collection-kubernetes/commit/76483827bd1aef073b280ebce2b573ea3714df14))
* revert distro package dependencies ([761277a](https://github.com/vexxhost/ansible-collection-kubernetes/commit/761277a7478d6978f254ac07ba381ddfab9a6ae1))
* rhel9 ulimit for containerd ([8403e6f](https://github.com/vexxhost/ansible-collection-kubernetes/commit/8403e6f8020a371d6d3d0db27269303d6a5d84f8))


### Miscellaneous Chores

* release 1.7.1 ([c80912b](https://github.com/vexxhost/ansible-collection-kubernetes/commit/c80912bf15c06ef98ecef9315438d3ee64549457))

## [1.7.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.7.0...v1.7.1) (2023-07-05)


### Miscellaneous Chores

* release 1.7.1 ([c80912b](https://github.com/vexxhost/ansible-collection-kubernetes/commit/c80912bf15c06ef98ecef9315438d3ee64549457))

## [1.7.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.6.0...v1.7.0) (2023-07-01)


### Features

* update CAPI release ([faf7048](https://github.com/vexxhost/ansible-collection-kubernetes/commit/faf7048aa167314b850b1b4fff817472d5688b4c))


### Bug Fixes

* add checksums + linters ([e1956c1](https://github.com/vexxhost/ansible-collection-kubernetes/commit/e1956c1d0e32835ff5f9ebb877ec4911459277bc))

## [1.6.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.5.1...v1.6.0) (2023-06-22)


### Features

* **role:cilium:** Upgrade cilium version ([e783aad](https://github.com/vexxhost/ansible-collection-kubernetes/commit/e783aad4190a797c3037849f176e07b179aace23))


### Bug Fixes

* **containerd:** properly forget package ([2bbb2f7](https://github.com/vexxhost/ansible-collection-kubernetes/commit/2bbb2f7eb9c96c48df8cde99d57a2d74fc5f95b8))

## [1.5.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.5.0...v1.5.1) (2023-04-26)


### Bug Fixes

* **containerd:** bump to 100G ([858e977](https://github.com/vexxhost/ansible-collection-kubernetes/commit/858e977e4a8532a5375422f140cb120183ef6648))

## [1.5.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.4.0...v1.5.0) (2023-04-25)


### Features

* add capi ([6f5a8f1](https://github.com/vexxhost/ansible-collection-kubernetes/commit/6f5a8f149c043e8ad285f34eab0a0e247dd7cb4b))

## [1.3.3](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.3.2...v1.3.3) (2023-03-28)


### Bug Fixes

* avoid trailing slash with prefix ([5a3f11e](https://github.com/vexxhost/ansible-collection-kubernetes/commit/5a3f11e6bf9601adc03e014aab8857742e1a9e24))

## [1.3.2](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.3.1...v1.3.2) (2023-03-28)


### Bug Fixes

* only override if registry isn't default ([3270fdd](https://github.com/vexxhost/ansible-collection-kubernetes/commit/3270fdddaed5d86e8c133dce510939af6154bfbf))

## [1.3.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.3.0...v1.3.1) (2023-03-28)


### Bug Fixes

* adjust package dependencies for rocky linux ([c698d41](https://github.com/vexxhost/ansible-collection-kubernetes/commit/c698d413591fc10838133e0c4b22e1113ea358f7))
* bump cilium version ([5b12aeb](https://github.com/vexxhost/ansible-collection-kubernetes/commit/5b12aeb647a15b6f83513752897ad449741daca4))
* make kube component versioning consistent ([8d6df7e](https://github.com/vexxhost/ansible-collection-kubernetes/commit/8d6df7e82794b9337da12d5fcf46ae865b1d8c44))
* refactor {atmosphere,kubernetes}_image_repository ([4ffc20b](https://github.com/vexxhost/ansible-collection-kubernetes/commit/4ffc20bd032715c953cca91c32843db9fd70e5d1))
* restore symlinks ([7648382](https://github.com/vexxhost/ansible-collection-kubernetes/commit/76483827bd1aef073b280ebce2b573ea3714df14))
* revert distro package dependencies ([761277a](https://github.com/vexxhost/ansible-collection-kubernetes/commit/761277a7478d6978f254ac07ba381ddfab9a6ae1))
* rhel9 ulimit for containerd ([8403e6f](https://github.com/vexxhost/ansible-collection-kubernetes/commit/8403e6f8020a371d6d3d0db27269303d6a5d84f8))

## [1.3.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.2.1...v1.3.0) (2023-03-21)


### Features

* support multiple k8s versions ([7b03230](https://github.com/vexxhost/ansible-collection-kubernetes/commit/7b03230dbc29869df921c90fb59c9ce6bd5feab8))


### Bug Fixes

* add synchornize workaround ([db81203](https://github.com/vexxhost/ansible-collection-kubernetes/commit/db81203c80ba2e37f0a04054861fa1db8f306558))

## [1.2.1](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.2.0...v1.2.1) (2023-03-21)


### Bug Fixes

* forget packages instead of remove them ([eda79d4](https://github.com/vexxhost/ansible-collection-kubernetes/commit/eda79d4551f3764df0e7747c39a48c3b565a020b))

## [1.2.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.1.0...v1.2.0) (2023-03-19)


### Features

* **k8s:** add roles ([#2](https://github.com/vexxhost/ansible-collection-kubernetes/issues/2)) ([7d883be](https://github.com/vexxhost/ansible-collection-kubernetes/commit/7d883be1c411d4eb5a9f43c443f21f37c8390650))

## [1.1.0](https://github.com/vexxhost/ansible-collection-kubernetes/compare/v1.0.0...v1.1.0) (2023-03-18)


### Features

* **helm:** add role ([a3e74bc](https://github.com/vexxhost/ansible-collection-kubernetes/commit/a3e74bc086d4352e69820dddf8ea5e1f2dd3a8f2))


### Bug Fixes

* **containerd:** re-add missing containerd_download_unarchive_dest ([74a58af](https://github.com/vexxhost/ansible-collection-kubernetes/commit/74a58afa0616fe6c27c45bd571de7f50473eca52))
* **helm:** install curl-minimal for el9 ([420af8a](https://github.com/vexxhost/ansible-collection-kubernetes/commit/420af8a87b16453c63630ae676dbc56f68db679f))
* idempotence ([3d05147](https://github.com/vexxhost/ansible-collection-kubernetes/commit/3d0514753f2393c16cc0e65bd770855280133978))

## Changelog
