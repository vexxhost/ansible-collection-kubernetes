# `kube_vip`

## LoadBalancer Service management

`kube_vip_services_enabled` controls kube-vip's `svc_enable` setting independently
of the VIP mode. It defaults to `true` in ARP mode and `false` in BGP mode,
preserving the existing behavior. Control-plane VIP management remains enabled.

To enable Service management alongside a BGP control-plane VIP:

```yaml
kube_vip_mode: bgp
kube_vip_services_enabled: true
```

To disable Service management in ARP mode:

```yaml
kube_vip_mode: arp
kube_vip_services_enabled: false
```

This setting does not allocate Service IP addresses or install a cloud provider.
Configure Service addresses separately, and ensure BGP peer policies and prefix
limits permit the additional Service VIP advertisements. Existing ARP election
settings and BGP peer settings are unchanged.
