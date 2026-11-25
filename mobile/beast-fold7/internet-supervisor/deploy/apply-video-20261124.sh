#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261124-02
next=/opt/ar-assembly/releases/20261124-03
test ! -e "$next"
source=/home/ubuntu/ar-video-20261124
for file in server/relay.ts shared/protocol.ts shared/video.ts shared/avc.ts deploy/smoke-video.ts; do test -f "$source/$file"; done
test "$(systemctl is-active ar-supervisor)" = active
umask 077
backup="/var/backups/ar-assembly/pre-video-$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup"
cp -a "$previous" "$next"
for file in server/relay.ts shared/protocol.ts shared/video.ts shared/avc.ts deploy/smoke-video.ts; do
  install -o ar-supervisor -g ar-supervisor -m 644 "$source/$file" "$next/$file"
done
rollback(){ ln -sfn "$previous" /opt/ar-assembly/current; systemctl restart ar-supervisor; printf 'Rolled back\n' >&2; }
trap rollback ERR
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 20); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
/opt/ar-assembly/runtime/bin/node --env-file=/etc/ar-assembly/relay.env "$next/deploy/smoke-video.ts"
trap - ERR
printf '\nRelease: %s\n' "$(readlink -f /opt/ar-assembly/current)"
systemctl show ar-supervisor -p ActiveState -p Result -p NRestarts
sha256sum "$next/server/relay.ts"
printf 'Database backup: %s\n' "$backup"
test "$(systemctl is-active nova || true)" = inactive
