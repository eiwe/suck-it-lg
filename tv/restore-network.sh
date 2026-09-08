#!/bin/sh
set -eu
touch /var/luna/preferences/lg_owner_network_privacy_off
if iptables -C OUTPUT -j LG_OWNER_PRIVACY 2>/dev/null; then
    iptables -D OUTPUT -j LG_OWNER_PRIVACY
fi
iptables -F LG_OWNER_PRIVACY 2>/dev/null || true
iptables -X LG_OWNER_PRIVACY 2>/dev/null || true
for iface in eth0 wlan0 p2p0 sit0; do
    path="/proc/sys/net/ipv6/conf/$iface/disable_ipv6"
    if [ -e "$path" ]; then printf '0\n' > "$path"; fi
done
echo 'Network block disabled. IPv6 enabled. Consent choices unchanged.'
