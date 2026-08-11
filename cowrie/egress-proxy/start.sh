#!/bin/sh
# Egress allowlist sidecar.
#
# Policy: the `honeypot` docker network is flipped to internal:true by
# compose; this container sits on both `honeypot` and a second bridge
# (`egress`, internal:false) and is the ONLY path from the honeypot to
# the internet. iptables enforces the allowlist; tinyproxy gives us
# URL-level visibility for incident response.
#
# Allowlist:
#   - DNS (udp/tcp 53) to pinned Quad9 resolvers only (9.9.9.9, 149.112.112.112)
#   - HTTP  (tcp 80)  from the tinyproxy uid, rate limited
#   - HTTPS (tcp 443) from the tinyproxy uid, rate limited
# Explicit REJECT for SSH/Telnet/SMTP/SMB/NetBIOS/IRC/RDP/VNC.
# Default DROP for everything else on OUTPUT and FORWARD.

set -eu

iptables -P INPUT  ACCEPT
iptables -P OUTPUT DROP
iptables -P FORWARD DROP

# Block all IPv6 egress - without these rules IPv6 bypasses all filtering.
ip6tables -P INPUT  ACCEPT
ip6tables -P OUTPUT DROP
ip6tables -P FORWARD DROP
ip6tables -A OUTPUT -o lo -j ACCEPT
ip6tables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
ip6tables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# Loopback is fine.
iptables -A OUTPUT -o lo -j ACCEPT

# Established/related return traffic for our own outbound connections.
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# ---- Block egress to internal / pivot ranges. Placed BEFORE the
#      uid-owner ACCEPTs below so cowrie cannot use tinyproxy to
#      reach the admin tailnet, RFC1918 internals, or link-local. ----
#   100.64.0.0/10  Tailscale CGNAT (admin tailnet)
#   10.0.0.0/8     RFC1918 (private nets, VPS provider mgmt nets)
#   192.168.0.0/16 RFC1918
#   169.254.0.0/16 link-local (incl. AWS/GCP/Azure metadata services)
#   The docker bridge subnets (172.16.0.0/12 by default) are NOT
#   blocked here; the proxy needs them for its own gateway route.
for SUBNET in 100.64.0.0/10 10.0.0.0/8 192.168.0.0/16 169.254.0.0/16; do
    iptables -A OUTPUT  -d "$SUBNET" -j DROP
    iptables -A FORWARD -d "$SUBNET" -j DROP
done
# IPv6 equivalents. ULA + link-local + Tailscale's ULA prefix.
for SUBNET6 in fc00::/7 fe80::/10 fd7a:115c:a1e0::/48; do
    ip6tables -A OUTPUT  -d "$SUBNET6" -j DROP
    ip6tables -A FORWARD -d "$SUBNET6" -j DROP
done

for DNS in 9.9.9.9 149.112.112.112; do
    iptables -A OUTPUT -p udp -d "$DNS" --dport 53 \
        -m limit --limit 30/minute --limit-burst 10 -j ACCEPT
    iptables -A OUTPUT -p tcp -d "$DNS" --dport 53 \
        -m limit --limit 10/minute --limit-burst 5  -j ACCEPT
done

# ---- HTTP / HTTPS: only from the tinyproxy uid, rate limited. ----
# Cowrie cannot bypass this because it has no route off the internal
# `honeypot` bridge except through this proxy container.
iptables -A OUTPUT -p tcp --dport 80  -m owner --uid-owner tinyproxy \
    -m limit --limit 10/second --limit-burst 20 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 443 -m owner --uid-owner tinyproxy \
    -m limit --limit 10/second --limit-burst 20 -j ACCEPT

# ---- Same allowlist for FORWARD (traffic transiting this container
#      when docker uses it as a gateway). ----
iptables -A FORWARD -p tcp --dport 80 \
    -m limit --limit 10/second --limit-burst 20 -j ACCEPT
iptables -A FORWARD -p tcp --dport 443 \
    -m limit --limit 10/second --limit-burst 20 -j ACCEPT
for DNS in 9.9.9.9 149.112.112.112; do
    iptables -A FORWARD -p udp -d "$DNS" --dport 53 -j ACCEPT
    iptables -A FORWARD -p tcp -d "$DNS" --dport 53 -j ACCEPT
done

# ---- Explicit REJECT for commonly abused ports. Belt + suspenders:
#      default policy is already DROP but returning ICMP makes local
#      egress attempts fail loud in logs. ----
for P in 22 23 25 465 587 445 139 6667 6697 3389 5900; do
    iptables -A OUTPUT  -p tcp --dport "$P" -j REJECT --reject-with icmp-port-unreachable
    iptables -A FORWARD -p tcp --dport "$P" -j REJECT --reject-with icmp-port-unreachable
done
# IRC range
iptables -A OUTPUT  -p tcp --dport 6660:6669 -j REJECT --reject-with icmp-port-unreachable
iptables -A FORWARD -p tcp --dport 6660:6669 -j REJECT --reject-with icmp-port-unreachable

# Drop all capabilities; even if exploited, tinyproxy cannot regain root.
# Requires CAP_SETPCAP in compose (for --bounding-set=-all).
exec setpriv \
    --reuid tinyproxy \
    --regid tinyproxy \
    --clear-groups \
    --reset-env \
    --no-new-privs \
    --bounding-set=-all \
    tinyproxy -d -c /etc/egress-proxy/tinyproxy.conf
