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
assert.equal(before.RECORDING_MAX_SECONDS,'300');
let updated=text;
for(const key of ['RECORDING_FILE_BYTES','RECORDING_OWNER_BYTES']){
  assert.equal(before[key],'15000000');
  const pattern=new RegExp('^'+key+'=15000000$','gm');
  assert.equal(updated.match(pattern)?.length,1);
  updated=updated.replace(pattern,key+'=100000000');
}
const after=parseEnv(updated);
assert.deepEqual(after,{...before,RECORDING_FILE_BYTES:'100000000',RECORDING_OWNER_BYTES:'100000000'});
readConfig(after);
const capture=readConfig({...after,RECORDING_ENABLED:'true'}).recording.capture;
assert.equal(capture.seconds,300);
assert.equal(capture.fileBytes,100000000);
assert.equal(capture.ownerBytes,100000000);
copyFileSync(path,'/var/backups/ar-assembly/pre-recordings-20261125T055020Z/before-100mb-limit.env',constants.COPYFILE_EXCL);
writeFileSync(path,updated,{mode:0o600});
console.log('Validated: 300 seconds, 100000000 bytes per file and owner; capture remains off.');
NODE
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
