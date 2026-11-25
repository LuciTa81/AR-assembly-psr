#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
export PATH=/opt/ar-assembly/runtime/bin:/usr/sbin:/usr/bin:/sbin:/bin
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261125-06-ten-minute
next=/opt/ar-assembly/releases/20261125-07-storage-10gb
test ! -e "$next"
test "$(systemctl is-active ar-supervisor)" = active
test "$(runuser -u postgres -- psql -XAt -d ar_supervisor -c "SELECT count(*) FROM recordings WHERE status='capturing'")" = 0
test "$(runuser -u postgres -- psql -XAt -d ar_supervisor -c "SELECT count(*) FROM (SELECT DISTINCT ON(device_id) state,received_ms FROM events ORDER BY device_id,id DESC) e WHERE state->>'running'='true' AND received_ms>extract(epoch from now())*1000-15000")" = 0
nova_before=$(systemctl is-active nova || true)
umask 077
backup="/var/backups/ar-assembly/pre-storage-10gb-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$backup"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup/database.dump"
cp -a /etc/ar-assembly/relay.env "$backup/relay.env"
printf '%s\n' "$previous" > "$backup/previous-release.txt"
snapshot(){ runuser -u postgres -- psql -XAt -d ar_supervisor -c "SELECT row_to_json(r) FROM recordings r ORDER BY id; SELECT row_to_json(a) FROM recording_accounts a ORDER BY owner_id"; }
snapshot > "$backup/recordings-before.jsonl"
install -d -o ar-supervisor -g ar-supervisor -m 755 "$next"
cp -a "$previous/." "$next/"
tar -xzf /home/ubuntu/ar-storage-10gb-20261125.tar.gz -C "$next"
chown -R ar-supervisor:ar-supervisor "$next"
rollback(){ cp -a "$backup/relay.env" /etc/ar-assembly/relay.env; ln -sfn "$previous" /opt/ar-assembly/current; systemctl restart ar-supervisor; printf 'Rolled back: %s\n' "$previous" >&2; }
trap rollback ERR
cd "$next"
node --input-type=module <<'NODE'
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {parseEnv} from 'node:util';
import {readConfig} from './server/config.ts';
const path='/etc/ar-assembly/relay.env',text=readFileSync(path,'utf8'),before=parseEnv(text);
assert.equal(before.MULTI_USER,'false');
assert.equal(before.RECORDING_ENABLED,'true');
assert.equal(before.RECORDING_MAX_SECONDS,'600');
assert.equal(before.RECORDING_CONCURRENT,'1');
let updated=text;
const changes={RECORDING_FILE_BYTES:'300000000',RECORDING_OWNER_BYTES:'10000000000'};
for(const [key,value] of Object.entries(changes)){
  assert.equal(before[key],'100000000');
  const pattern=new RegExp('^'+key+'=100000000$','gm');
  assert.equal(updated.match(pattern)?.length,1);
  updated=updated.replace(pattern,key+'='+value);
}
const after=parseEnv(updated);
assert.deepEqual(after,{...before,...changes});
readConfig(after);
writeFileSync(path,updated,{mode:0o600});
NODE
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-storage-10gb.ts "$(systemctl show ar-supervisor -p MainPID --value)"
snapshot > "$backup/recordings-after.jsonl"
cmp "$backup/recordings-before.jsonl" "$backup/recordings-after.jsonl"
test "$(systemctl is-active nova || true)" = "$nova_before"
trap - ERR
printf '\nPASS: %s\nBackup: %s\n' "$next" "$backup"
