#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
export PATH=/opt/ar-assembly/runtime/bin:/usr/sbin:/usr/bin:/sbin:/bin
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261125-02-quota-fix
next=/opt/ar-assembly/releases/20261125-03-segment-recovery
test ! -e "$next"
test "$(systemctl is-active ar-supervisor)" = active
grep -qx 'RECORDING_ENABLED=false' /etc/ar-assembly/relay.env
grep -qx 'MULTI_USER=false' /etc/ar-assembly/relay.env
grep -qx 'RECORDING_MAX_SECONDS=300' /etc/ar-assembly/relay.env
grep -qx 'RECORDING_FILE_BYTES=100000000' /etc/ar-assembly/relay.env
grep -qx 'RECORDING_OWNER_BYTES=100000000' /etc/ar-assembly/relay.env
nova_before=$(systemctl is-active nova || true)
umask 077
backup="/var/backups/ar-assembly/pre-segment-recovery-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$backup"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup/database.dump"
cp -a /etc/ar-assembly/relay.env "$backup/relay.env"
printf '%s\n' "$previous" > "$backup/previous-release.txt"
inventory="COPY (SELECT id,status,bytes,duration_ms,reason,object_key FROM recordings ORDER BY id) TO STDOUT WITH CSV"
runuser -u postgres -- psql -d ar_supervisor -c "$inventory" > "$backup/recordings-before.csv"
install -d -o ar-supervisor -g ar-supervisor -m 755 "$next"
cp -a "$previous/." "$next/"
tar -xzf /home/ubuntu/ar-segment-recovery-20261125.tar.gz -C "$next"
chown -R ar-supervisor:ar-supervisor "$next"
rollback() {
  # Recording is off throughout this deployment, so no multi-segment rows can have been created.
  ln -sfn "$previous" /opt/ar-assembly/current
  systemctl restart ar-supervisor
  printf 'Rolled back to %s; backup %s\n' "$previous" "$backup" >&2
}
trap rollback ERR
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
cd "$next"
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-recording-quota.ts
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-production.ts
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-video.ts
runuser -u postgres -- psql -d ar_supervisor -c "$inventory" > "$backup/recordings-after.csv"
cmp "$backup/recordings-before.csv" "$backup/recordings-after.csv"
cmp "$backup/relay.env" /etc/ar-assembly/relay.env
test "$(systemctl is-active nova || true)" = "$nova_before"
trap - ERR
printf '\nPASS segment recovery: %s\nBackup: %s\nRecording remains off; existing video rows unchanged.\n' "$next" "$backup"
