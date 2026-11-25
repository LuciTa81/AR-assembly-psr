#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
test "$(systemctl is-active ar-supervisor)" = active
install -d -m 700 /var/backups/ar-assembly
backup="/var/backups/ar-assembly/initial-$(date -u +%Y%m%dT%H%M%SZ).dump"
umask 077
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup"
test "$(runuser -u postgres -- psql -XAtc "SELECT count(*) FROM pg_database WHERE datname='ar_restorecheck_20261124'")" = 0
runuser -u postgres -- createdb ar_restorecheck_20261124
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -c 'REVOKE ALL ON DATABASE ar_restorecheck_20261124 FROM PUBLIC' >/dev/null
runuser -u postgres -- pg_restore --exit-on-error --dbname=ar_restorecheck_20261124 < "$backup"
original=$(runuser -u postgres -- psql -XAt -d ar_supervisor -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
restored=$(runuser -u postgres -- psql -XAt -d ar_restorecheck_20261124 -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
test "$original" = "$restored"
test "$original" = 5
systemctl restart ar-supervisor
for attempt in $(seq 1 20); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
printf '\nPASS: backup restored with %s tables; graceful service restart healthy\n' "$restored"
systemctl show ar-supervisor -p ActiveState -p Result -p NRestarts
stat -c 'Backup permissions: %a %U' "$backup"
ss -lnt | grep -E ':(22|80|443|5432|8787) '
