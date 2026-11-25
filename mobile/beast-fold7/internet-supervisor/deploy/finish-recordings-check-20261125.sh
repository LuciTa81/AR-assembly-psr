#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
test "$(readlink -f /opt/ar-assembly/current)" = /opt/ar-assembly/releases/20261125-01-recording-check
cd /opt/ar-assembly/current
/opt/ar-assembly/runtime/bin/node --input-type=module <<'NODE'
import {readFileSync,writeFileSync,copyFileSync,constants} from 'node:fs';
import {parseEnv} from 'node:util';
import {readConfig} from './server/config.ts';
const path='/etc/ar-assembly/relay.env',text=readFileSync(path,'utf8');
const matches=text.match(/^RECORDING_ENABLED=true$/gm);
if(matches?.length!==1)throw new Error('Expected exactly one enabled recording configuration');
const updated=text.replace(/^RECORDING_ENABLED=true$/m,'RECORDING_ENABLED=false');
readConfig(parseEnv(updated));
copyFileSync(path,'/var/backups/ar-assembly/pre-recordings-20261125T055020Z/recording-test-enabled.env',constants.COPYFILE_EXCL);
writeFileSync(path,updated,{mode:0o600});
NODE
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
printf '\nNew recording disabled; S3 configuration, existing recording and expiry cleanup retained.\n'
