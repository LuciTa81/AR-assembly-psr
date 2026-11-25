#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
export PATH=/opt/ar-assembly/runtime/bin:/usr/sbin:/usr/bin:/sbin:/bin
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261125-04-work-history
next=/opt/ar-assembly/releases/20261125-05-work-history-idle
test ! -e "$next"
test "$(systemctl is-active ar-supervisor)" = active
grep -qx 'RECORDING_ENABLED=false' /etc/ar-assembly/relay.env
grep -qx 'MULTI_USER=false' /etc/ar-assembly/relay.env
nova_before=$(systemctl is-active nova || true)
umask 077
backup="/var/backups/ar-assembly/pre-work-history-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$backup"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup/database.dump"
cp -a /etc/ar-assembly/relay.env "$backup/relay.env"
printf '%s\n' "$previous" > "$backup/previous-release.txt"
inventory="COPY (SELECT id,status,bytes,duration_ms,reason,object_key FROM recordings ORDER BY id) TO STDOUT WITH CSV"
runuser -u postgres -- psql -d ar_supervisor -c "$inventory" > "$backup/recordings-before.csv"
install -d -o ar-supervisor -g ar-supervisor -m 755 "$next"
cp -a "$previous/." "$next/"
tar -xzf /home/ubuntu/ar-work-history-20261125.tar.gz -C "$next"
chown -R ar-supervisor:ar-supervisor "$next"
rollback(){ ln -sfn "$previous" /opt/ar-assembly/current; systemctl restart ar-supervisor; printf 'Rolled back: %s\n' "$previous" >&2; }
trap rollback ERR
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
cd "$next"
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-work-history.ts
runuser -u postgres -- psql -d ar_supervisor -c "$inventory" > "$backup/recordings-after.csv"
cmp "$backup/recordings-before.csv" "$backup/recordings-after.csv"
cmp "$backup/relay.env" /etc/ar-assembly/relay.env
test "$(systemctl is-active nova || true)" = "$nova_before"
trap - ERR
printf '\nPASS work history: %s\nBackup: %s\nRecording off; video rows and configuration unchanged.\n' "$next" "$backup"
