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

fetch_edition() {
    local edition="$1"
    local out_name="$2"
    local target="$TARGET_DIR/$out_name"

    # `download.maxmind.com/geoip/databases/<edition>/download` returns a 302
    # to an R2 presigned URL; -L follows it.
    echo "==> Fetching $edition"
    curl -fsSL \
        --user "${MAXMIND_ACCOUNT_ID}:${MAXMIND_LICENSE_KEY}" \
        -o "$TMP/${edition}.tar.gz" \
        "https://download.maxmind.com/geoip/databases/${edition}/download?suffix=tar.gz"

    tar -xzf "$TMP/${edition}.tar.gz" -C "$TMP"
    # MaxMind tarballs extract to ${edition}_YYYYMMDD/
    local extracted
    extracted=$(find "$TMP" -maxdepth 1 -type d -name "${edition}_*" | head -n 1)
    if [ -z "$extracted" ]; then
        echo "could not locate extracted dir for $edition" >&2
        exit 1
    fi
    mv "${extracted}/${edition}.mmdb" "$target"
    echo "    wrote $target ($(du -h "$target" | cut -f1))"
}

fetch_edition GeoLite2-City GeoLite2-City.mmdb
fetch_edition GeoLite2-ASN GeoLite2-ASN.mmdb

echo "mmdb files ready in $TARGET_DIR"
