# Cowrie egress-proxy sidecar

This sidecar is the only outbound path from the internal `honeypot`
docker network. It runs `tinyproxy` behind an `iptables` allowlist that
permits DNS (UDP/TCP 53) to pinned Cloudflare and Quad9 resolvers and
HTTP/HTTPS (TCP 80/443) rate limited to 10 req/sec, and explicitly
rejects SSH, Telnet, SMTP, SMB, NetBIOS, IRC, RDP and VNC so a
compromised Cowrie container cannot be used as a relay to abuse C2,
mail, or lateral-move onto the admin's infrastructure.

## Files

- `Dockerfile` - Alpine 3.20 + `iptables` + `tinyproxy`, runs `start.sh`.
- `start.sh` - installs iptables rules (OUTPUT + FORWARD), then execs tinyproxy.
- `tinyproxy.conf` - proxy config: listens on :8888, only allows CONNECT to 80/443, URL filter list applied.
- `filter.txt` - optional URL regex blocklist (Tor, common paste hosts).

## Compose wiring (owned by the compose agent, for reference)

The `honeypot` network should be flipped to `internal: true`; this
sidecar joins both `honeypot` (aliased as `egress-proxy`) and a new
`egress: { internal: false }` network. Cowrie's `HTTP_PROXY` /
`HTTPS_PROXY` env vars should point at `http://egress-proxy:8888`.
The container needs `cap_add: [NET_ADMIN, NET_RAW]`, `cap_drop: [ALL]`,
`no-new-privileges: true`.
