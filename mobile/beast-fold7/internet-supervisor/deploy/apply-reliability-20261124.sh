#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261124-01
next=/opt/ar-assembly/releases/20261124-02
test ! -e "$next"
test -f /home/ubuntu/ar-relay-20261124.ts
test -f /home/ubuntu/ar-smoke-20261124.ts
test "$(systemctl is-active ar-supervisor)" = active
umask 077
backup="/var/backups/ar-assembly/pre-reliability-$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup"
cp -a "$previous" "$next"
install -o ar-supervisor -g ar-supervisor -m 644 /home/ubuntu/ar-relay-20261124.ts "$next/server/relay.ts"
install -o ar-supervisor -g ar-supervisor -m 644 /home/ubuntu/ar-smoke-20261124.ts "$next/deploy/smoke-production.ts"
rollback(){
  ln -sfn "$previous" /opt/ar-assembly/current
  systemctl restart ar-supervisor
  printf 'Rolled back to previous release\n' >&2
}
trap rollback ERR
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 20); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
trap - ERR
printf '\nRelease: %s\n' "$(readlink -f /opt/ar-assembly/current)"
systemctl show ar-supervisor -p ActiveState -p Result -p NRestarts
sha256sum "$next/server/relay.ts"
printf 'Database backup: %s\n' "$backup"
test "$(systemctl is-active nova || true)" = inactive
