#!/usr/bin/env bash
# Download GeoLite2-City and GeoLite2-ASN mmdb files into the target dir.
# Requires MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY in the environment.
#
# Usage: ./scripts/fetch-mmdb.sh <target-dir>
# --

set -euo pipefail

TARGET_DIR="${1:?usage: $0 <target-dir>}"

: "${MAXMIND_ACCOUNT_ID:?MAXMIND_ACCOUNT_ID not set}"
: "${MAXMIND_LICENSE_KEY:?MAXMIND_LICENSE_KEY not set}"

mkdir -p "$TARGET_DIR"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Keep the MaxMind credential OUT of the process argv.
# Curl reads it from a 0600 config file inside the 0700 mktemp dir instead.
cred_cfg="$TMP/curl-cred.cfg"
( umask 077; printf 'user = "%s:%s"\n' "$MAXMIND_ACCOUNT_ID" "$MAXMIND_LICENSE_KEY" > "$cred_cfg" )

curl_opts=(
    --fail --silent --show-error --location
    --retry 5 --retry-delay 30 --retry-all-errors
    --config "$cred_cfg"
)

fetch_edition() {
    local edition="$1"
    local out_name="$2"
    local target="$TARGET_DIR/$out_name"
    local base="https://download.maxmind.com/geoip/databases/${edition}/download"
    local tarball="$TMP/${edition}.tar.gz"
    local sha_sidecar="$TMP/${edition}.tar.gz.sha256"

    echo "==> Fetching $edition"
    curl "${curl_opts[@]}" -o "$tarball"     "${base}?suffix=tar.gz"
    curl "${curl_opts[@]}" -o "$sha_sidecar" "${base}?suffix=tar.gz.sha256"

    local expected
    expected=$(awk '{print $1}' "$sha_sidecar")
    if [ -z "$expected" ]; then
        echo "could not parse sha256 sidecar for $edition" >&2
        exit 1
    fi
    printf '%s  %s\n' "$expected" "$(basename "$tarball")" \
        > "$TMP/${edition}.checksum"
    (cd "$TMP" && sha256sum -c "${edition}.checksum" >/dev/null)

    tar -xzf "$tarball" -C "$TMP"

    # MaxMind tarballs extract to ${edition}_YYYYMMDD/
    local extracted
    extracted=$(find "$TMP" -maxdepth 1 -type d -name "${edition}_*" | head -n 1)
    if [ -z "$extracted" ]; then
        echo "could not locate extracted dir for $edition" >&2
        exit 1
    fi

    mv -f "${extracted}/${edition}.mmdb" "$target"
    echo "    wrote $target ($(du -h "$target" | cut -f1))"
}

fetch_edition GeoLite2-City GeoLite2-City.mmdb
fetch_edition GeoLite2-ASN GeoLite2-ASN.mmdb

echo "mmdb files ready in $TARGET_DIR"
