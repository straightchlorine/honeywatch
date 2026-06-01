#!/usr/bin/env bash
# Build a Cowrie fs.pickle that mirrors a CentOS Stream 10 KVM cloud guest.
#
# Why: the bundled Cowrie fs.pickle is an ancient Debian 7 (2013) tree. Our
# honeypot advertises CentOS Stream 10, so `ls -la /`, `/etc/apt`, missing
# dnf/rpm, and 2013 mtimes instantly unmask it. This rebuilds the simulated
# filesystem from a real CentOS Stream 10 package set installed into a clean
# --installroot (no docker/.dockerenv/sysfs artifacts), seeds the /proc and
# /sys nodes our honeyfs overrides need, then runs Cowrie's own createfs.
#
# Output: cowrie/fs/centos-stream10.pickle  (mounted over the package
# fs.pickle by docker-compose; see the cowrie service volumes).
#
# Re-run any time; it is deterministic apart from package versions + the
# build-time mtimes. Requires docker. Safe to run on the dev box or CI.
set -euo pipefail

COWRIE_IMAGE="${COWRIE_IMAGE:-cowrie/cowrie:sha-cd0770d}"
CENTOS_IMAGE="${CENTOS_IMAGE:-quay.io/centos/centos:stream10}"
# Stable machine-id for the persona; honeyfs/etc/machine-id and the
# hostnamectl / ps txtcmd outputs MUST match this value.
MACHINE_ID="${MACHINE_ID:-4f8b2d6c9a7e41d3b0c5e6f7a8b9c0d1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_NAME="centos-stream10.pickle"

echo ">> extracting createfs.py from ${COWRIE_IMAGE}"
cid="$(docker create "${COWRIE_IMAGE}")"
trap 'docker rm -f "${cid}" >/dev/null 2>&1 || true' EXIT
docker cp "${cid}:/cowrie/cowrie-git/src/cowrie/scripts/createfs.py" "${SCRIPT_DIR}/.createfs.py"

echo ">> building CentOS Stream 10 rootfs + pickle inside ${CENTOS_IMAGE}"
# The in-container build: install a believable server package set into a clean
# installroot, add the cloud user, seed /proc + /sys/class/dmi nodes that our
# honeyfs overrides attach to, then pickle the tree with createfs.
docker run --rm \
  -v "${SCRIPT_DIR}:/work" \
  -e MACHINE_ID="${MACHINE_ID}" \
  "${CENTOS_IMAGE}" bash -euo pipefail -c '
    ROOT=/centosfs
    dnf -y --installroot="$ROOT" --releasever=10 --setopt=install_weak_deps=False \
        --setopt=tsflags=nodocs install \
        centos-stream-release setup filesystem bash glibc coreutils util-linux \
        procps-ng iproute net-tools openssh-server openssh-clients sudo curl wget \
        less which hostname tar gzip ca-certificates systemd chrony rsyslog cronie \
        NetworkManager dnf rpm python3 vim-minimal passwd shadow-utils gawk sed \
        grep findutils >/dev/null

    # Cloud user (uid 1000, wheel) so /home/centos exists and matches passwd.
    chroot "$ROOT" /usr/sbin/useradd -m -u 1000 -U -G wheel -s /bin/bash centos 2>/dev/null || true
    # Seed a couple of plausible dotfiles + an attacker-bait history.
    printf "# .bashrc\n[ -f /etc/bashrc ] \&\& . /etc/bashrc\n" > "$ROOT/home/centos/.bashrc" 2>/dev/null || true
    : > "$ROOT/root/.bash_history" 2>/dev/null || true

    # Stable machine-id (honeyfs override supplies content, but the node must exist).
    printf "%s\n" "$MACHINE_ID" > "$ROOT/etc/machine-id"
    mkdir -p "$ROOT/var/lib/dbus"
    printf "%s\n" "$MACHINE_ID" > "$ROOT/var/lib/dbus/machine-id"

    # Cowrie attaches honeyfs content only to T_FILE nodes and createfs stores
    # no file bytes, so an OS-identity file that ships as a symlink would cat
    # EMPTY. Flatten the most-cat-ed identity files to real nodes so the matching
    # honeyfs/etc/* override renders. (Real CentOS has os-release as a symlink;
    # a regular file here is a negligible tell vs an empty os-release.)
    for f in os-release redhat-release system-release; do
        rm -f "$ROOT/etc/$f"; : > "$ROOT/etc/$f"
    done
    # /etc/centos-release is already a real file from centos-stream-release.

    # Nodes that installroot does not create but a running box always has, and
    # that recon reads. Content comes from honeyfs at runtime; node must exist.
    : > "$ROOT/etc/hostname"
    : > "$ROOT/etc/resolv.conf"
    : > "$ROOT/etc/fstab"
    mkdir -p "$ROOT/etc/selinux"; : > "$ROOT/etc/selinux/config"
    # yum compat symlink (CentOS ships /usr/bin/yum -> dnf-3); makes `which yum` honest.
    ln -sf dnf-3 "$ROOT/usr/bin/yum" 2>/dev/null || true

    # Seed /proc nodes our honeyfs overrides attach to (content comes from honeyfs
    # at runtime; only the node must exist in the pickle). installroot /proc is empty.
    mkdir -p "$ROOT/proc"
    for f in cpuinfo meminfo mounts version modules cmdline loadavg uptime stat filesystems swaps; do
        : > "$ROOT/proc/$f"
    done

    # Fake DMI so dmidecode/cat /sys/class/dmi/id/* reads like a QEMU/KVM guest
    # instead of returning ENOENT (the classic container tell).
    mkdir -p "$ROOT/sys/class/dmi/id"
    printf "%s\n" "Standard PC (Q35 + ICH9, 2009)" > "$ROOT/sys/class/dmi/id/product_name"
    printf "%s\n" "QEMU"                            > "$ROOT/sys/class/dmi/id/sys_vendor"
    printf "%s\n" "QEMU"                            > "$ROOT/sys/class/dmi/id/board_vendor"
    printf "%s\n" "SeaBIOS"                         > "$ROOT/sys/class/dmi/id/bios_vendor"
    printf "%s\n" "pc-q35-9.0"                      > "$ROOT/sys/class/dmi/id/product_version"
    printf "%s\n" "1.16.3-2.el10"                   > "$ROOT/sys/class/dmi/id/bios_version"
    printf "%s\n" "QEMU"                            > "$ROOT/sys/class/dmi/id/chassis_vendor"

    # Minimal /boot so kernel/initramfs listings look right (real names, recent).
    mkdir -p "$ROOT/boot"
    : > "$ROOT/boot/vmlinuz-6.12.0-116.el10.x86_64"
    : > "$ROOT/boot/initramfs-6.12.0-116.el10.x86_64.img"
    : > "$ROOT/boot/System.map-6.12.0-116.el10.x86_64"
    : > "$ROOT/boot/config-6.12.0-116.el10.x86_64"

    # Tidy: drop installroot detritus that would not exist on a running box.
    rm -f  "$ROOT/.dockerenv" 2>/dev/null || true
    rm -rf "$ROOT/run/secrets" 2>/dev/null || true
    rm -rf "$ROOT"/var/cache/dnf/* 2>/dev/null || true
    rm -rf "$ROOT"/var/log/dnf* 2>/dev/null || true

    echo ">> running createfs over $ROOT"
    rm -f /work/'"${OUT_NAME}"'
    cd /
    python3 /work/.createfs.py -l "$ROOT" -o /work/'"${OUT_NAME}"'
    echo ">> pickle written"
  '

rm -f "${SCRIPT_DIR}/.createfs.py"
echo ">> done: ${SCRIPT_DIR}/${OUT_NAME}"
ls -la "${SCRIPT_DIR}/${OUT_NAME}"
