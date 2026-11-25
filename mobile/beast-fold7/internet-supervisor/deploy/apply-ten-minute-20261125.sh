#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
export PATH=/opt/ar-assembly/runtime/bin:/usr/sbin:/usr/bin:/sbin:/bin
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261125-05-work-history-idle
next=/opt/ar-assembly/releases/20261125-06-ten-minute
test ! -e "$next"
test "$(systemctl is-active ar-supervisor)" = active
nova_before=$(systemctl is-active nova || true)
umask 077
backup="/var/backups/ar-assembly/pre-ten-minute-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$backup"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup/database.dump"
cp -a /etc/ar-assembly/relay.env "$backup/relay.env"
printf '%s\n' "$previous" > "$backup/previous-release.txt"
install -d -o ar-supervisor -g ar-supervisor -m 755 "$next"
cp -a "$previous/." "$next/"
tar -xzf /home/ubuntu/ar-ten-minute-20261125.tar.gz -C "$next"
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
assert.equal(before.RECORDING_ENABLED,'false');
assert.equal(before.RECORDING_MAX_SECONDS,'300');
assert.equal(before.MULTI_USER,'false');
assert.equal(before.RECORDING_FILE_BYTES,'100000000');
assert.equal(before.RECORDING_OWNER_BYTES,'100000000');
assert.equal(text.match(/^RECORDING_ENABLED=false$/gm)?.length,1);
assert.equal(text.match(/^RECORDING_MAX_SECONDS=300$/gm)?.length,1);
const updated=text.replace(/^RECORDING_ENABLED=false$/m,'RECORDING_ENABLED=true').replace(/^RECORDING_MAX_SECONDS=300$/m,'RECORDING_MAX_SECONDS=600');
const after=parseEnv(updated);
assert.deepEqual(after,{...before,RECORDING_ENABLED:'true',RECORDING_MAX_SECONDS:'600'});
assert.equal(readConfig(after).recording.capture.seconds,600);
writeFileSync(path,updated,{mode:0o600});
console.log('Validated: recording enabled, 600 seconds; all other settings unchanged.');
NODE
ln -sfn "$next" /opt/ar-assembly/current
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-ten-minute.ts
test "$(systemctl is-active nova || true)" = "$nova_before"
trap - ERR
printf '\nPASS ten-minute recording: %s\nBackup: %s\n' "$next" "$backup"
