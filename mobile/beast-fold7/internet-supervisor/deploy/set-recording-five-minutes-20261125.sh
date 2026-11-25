#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
test "$(readlink -f /opt/ar-assembly/current)" = /opt/ar-assembly/releases/20261125-01-recording-check
cd /opt/ar-assembly/current
/opt/ar-assembly/runtime/bin/node --input-type=module <<'NODE'
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,copyFileSync,constants} from 'node:fs';
import {parseEnv} from 'node:util';
import {readConfig} from './server/config.ts';
const path='/etc/ar-assembly/relay.env',text=readFileSync(path,'utf8'),before=parseEnv(text);
assert.equal(before.RECORDING_ENABLED,'false');
assert.equal(before.RECORDING_MAX_SECONDS,'30');
assert.equal(text.match(/^RECORDING_MAX_SECONDS=30$/gm)?.length,1);
const updated=text.replace(/^RECORDING_MAX_SECONDS=30$/m,'RECORDING_MAX_SECONDS=300');
const after=parseEnv(updated);
assert.deepEqual(after,{...before,RECORDING_MAX_SECONDS:'300'});
readConfig(after);
assert.equal(readConfig({...after,RECORDING_ENABLED:'true'}).recording.capture.seconds,300);
copyFileSync(path,'/var/backups/ar-assembly/pre-recordings-20261125T055020Z/before-five-minute-limit.env',constants.COPYFILE_EXCL);
writeFileSync(path,updated,{mode:0o600});
console.log('Validated: 300 seconds; every other setting unchanged; recording remains off.');
NODE
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
