# Egress allowlist sidecar for the Cowrie honeypot network.
#
# Runs iptables + tinyproxy so traffic from the internal `honeypot`
# docker network can only leave via this container, and only on the
# allowlisted ports (DNS to pinned resolvers, HTTP/HTTPS rate limited).
FROM alpine:3.23@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11

RUN set -e && \
    apk add --no-cache \
        iptables \
        ip6tables \
        tinyproxy \
        ca-certificates \
        bind-tools \
        util-linux && \
    test -x /usr/sbin/iptables && \
    test -x /sbin/setpriv -o -x /usr/bin/setpriv -o -x /bin/setpriv && \
    test -x /usr/bin/tinyproxy && \
    addgroup -S tinyproxy 2>/dev/null || true; \
    adduser  -S -G tinyproxy tinyproxy 2>/dev/null || true; \
    id tinyproxy >/dev/null

COPY start.sh       /usr/local/bin/start.sh
COPY tinyproxy.conf /etc/egress-proxy/tinyproxy.conf
COPY filter.txt     /etc/egress-proxy/filter.txt

RUN chmod 0755 /usr/local/bin/start.sh

EXPOSE 8888

# Sidecar needs NET_ADMIN + NET_RAW (granted by compose) to install
# iptables rules. It drops everything else.
ENTRYPOINT ["/usr/local/bin/start.sh"]
