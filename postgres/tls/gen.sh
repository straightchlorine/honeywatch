#!/bin/sh
# Generate the self-signed cert+key postgres serves to tailnet clients.
# Writes server.crt + server.key here (both gitignored). PG16 needs the key
# owned by uid 70 (the postgres:16-alpine user) at mode 0600. Restart postgres
# after regen - the cert is read only at startup.
set -eu

dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TS_IP="${TS_IP:-100.64.0.1}"

# Prior files are owned by uid 70; remove via dir write perm before regen.
rm -f "$dir/server.key" "$dir/server.crt"

openssl req -new -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$dir/server.key" -out "$dir/server.crt" \
    -subj "/CN=honeywatch-postgres" \
    -addext "subjectAltName=IP:${TS_IP},IP:127.0.0.1,DNS:localhost,DNS:honeywatch-db,DNS:postgres"

# Hand the files to uid 70 at the mode PG16 demands. As root (e.g. `sudo` on a
# deploy host), chown on the host directly. Otherwise borrow a throwaway root
# container; ':z' relabels the mount so SELinux (CentOS) permits the chown.
if [ "$(id -u)" = 0 ]; then
    chown 70:70 "$dir/server.key" "$dir/server.crt"
    chmod 600 "$dir/server.key"
    chmod 644 "$dir/server.crt"
else
    docker run --rm -v "$dir:/tls:z" alpine:3 sh -c \
        'chown 70:70 /tls/server.key /tls/server.crt && chmod 600 /tls/server.key && chmod 644 /tls/server.crt'
fi

echo "Generated server.crt + server.key in $dir (owner 70:70, key 0600). Restart postgres to load them."
