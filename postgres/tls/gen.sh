#!/bin/sh
# Generate the self-signed TLS material postgres serves to tailnet clients.
#
# Produces server.crt + server.key in this directory.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TS_IP="${TS_IP:-100.64.0.1}"

# A prior run leaves server.key/server.crt owned by uid 70, which our host uid
# cannot overwrite in place. We can still unlink them via write perm on the dir.
rm -f "$SCRIPT_DIR/server.key" "$SCRIPT_DIR/server.crt"

openssl req -new -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$SCRIPT_DIR/server.key" \
    -out "$SCRIPT_DIR/server.crt" \
    -subj "/CN=honeywatch-postgres" \
    -addext "subjectAltName=IP:${TS_IP},IP:127.0.0.1,DNS:localhost,DNS:honeywatch-db,DNS:postgres"

# postgres:16-alpine runs as uid:gid 70:70.
docker run --rm -v "$SCRIPT_DIR:/tls" alpine:3 sh -c \
    'chown 70:70 /tls/server.key /tls/server.crt && chmod 600 /tls/server.key && chmod 644 /tls/server.crt'

echo "Generated server.crt + server.key in $SCRIPT_DIR (owner 70:70, key 0600). Restart the postgres container to load them."
