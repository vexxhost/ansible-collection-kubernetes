# Configure PKI certificates manually for Kubernetes cluster
Kubernetes requires PKI for cluster operations such as authentication and
encryption. Kubeadm generates all required certificates so normally users don't
need to care about them.

If you don't want kubeadm to generate the required certificates, you can create
a single root CA, controlled by an administrator. And then create multiple
intermediate CAs(Kubernetes general CA, etcd CA, front-end proxy CA), and delegate
all further creation to Kubernetes itself.

You can configure those intermediate CAs by using the following variables.

```yaml
kubernetes_allow_custom_ca: true
kubernetes_custom_ca_key: |
    INPUT CA KEY CONTENT HERE
kubernetes_custom_ca_cert: |
    INPUT CA CERT CONTENT HERE
kubernetes_custom_etcd_ca_key: |
    INPUT ETCD CA KEY CONTENT HERE
kubernetes_custom_etcd_ca_cert: |
    INPUT ETCD CERT KEY CONTENT HERE
kubernetes_custom_front_proxy_ca_key: |
    INPUT FRONT PROXY CA KEY CONTENT HERE
kubernetes_custom_front_proxy_ca_cert: |
    INPUT FRONT PROXY CA CERT CONTENT HERE
```
