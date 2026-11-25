#!/bin/sh
set -eu

test "$(id -u)" = 0
test "$(uname -m)" = x86_64
test ! -e /opt/ar-assembly/runtime
test ! -e /etc/ar-assembly/relay.env
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends nginx postgresql ca-certificates xz-utils
if ! getent passwd ar-supervisor >/dev/null; then
    useradd --system --home-dir /opt/ar-assembly --shell /usr/sbin/nologin ar-supervisor
fi
install -d -m 0755 /opt/ar-assembly /opt/ar-assembly/downloads
install -d -m 0700 /etc/ar-assembly
install -d -m 0755 /var/lib/ar-acme
cd /opt/ar-assembly/downloads
version=v24.22.3
archive=node-${version}-linux-x64.tar.xz
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
    "https://nodejs.org/dist/${version}/${archive}" -o "$archive"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
    "https://nodejs.org/dist/${version}/SHASUMS256.txt" -o SHASUMS256.txt
awk -v name="$archive" '$2 == name' SHASUMS256.txt > selected.sha256
test "$(wc -l < selected.sha256)" -eq 1
sha256sum -c selected.sha256
tar -xJf "$archive" -C /opt/ar-assembly
ln -s "node-${version}-linux-x64" /opt/ar-assembly/runtime
/opt/ar-assembly/runtime/bin/node --version
systemctl is-active postgresql
# Firewall, TLS accounts, credentials and app deployment are separate steps.
