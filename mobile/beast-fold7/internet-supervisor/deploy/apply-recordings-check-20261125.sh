#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
export PATH=/opt/ar-assembly/runtime/bin:/usr/sbin:/usr/bin:/sbin:/bin
previous=$(readlink -f /opt/ar-assembly/current)
test "$previous" = /opt/ar-assembly/releases/20261124-03
next=/opt/ar-assembly/releases/20261125-01-recording-check
test ! -e "$next"
test ! -e /etc/systemd/system/ar-supervisor.service.d/recordings-check.conf
test "$(systemctl is-active ar-supervisor)" = active
nova_before=$(systemctl is-active nova || true)
umask 077
backup="/var/backups/ar-assembly/pre-recordings-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$backup"
runuser -u postgres -- pg_dump -Fc ar_supervisor > "$backup/database.dump"
cp -a /etc/ar-assembly/relay.env "$backup/relay.env"
systemctl cat ar-supervisor > "$backup/service.txt"
printf '%s\n' "$previous" > "$backup/previous-release.txt"
install -d -o ar-supervisor -g ar-supervisor -m 755 "$next"
tar -xzf /home/ubuntu/ar-recordings-check-20261125.tar.gz -C "$next"
chown -R ar-supervisor:ar-supervisor "$next"
cd "$next"
# Install the checked lockfile without running package lifecycle scripts.
corepack pnpm@12.23.0 install --prod --frozen-lockfile --ignore-scripts
chown -R ar-supervisor:ar-supervisor "$next"
node --env-file=/etc/ar-assembly/relay.env --input-type=module -e "import {readConfig} from './server/config.ts'; readConfig(process.env); console.log('Existing environment compatible');"
install -d -o ar-supervisor -g ar-supervisor -m 700 /var/lib/ar-assembly/recordings
install -d -m 755 /etc/systemd/system/ar-supervisor.service.d
rollback() {
  cp -a "$backup/relay.env" /etc/ar-assembly/relay.env
  rm -f /etc/systemd/system/ar-supervisor.service.d/recordings-check.conf
  ln -sfn "$previous" /opt/ar-assembly/current
  systemctl daemon-reload
  systemctl restart ar-supervisor
  printf 'Rollback applied; additive schema and backup retained: %s\n' "$backup" >&2
}
trap rollback ERR
node --input-type=module <<'NODE'
import {readFileSync,writeFileSync} from 'node:fs';
import {parseEnv} from 'node:util';
import {readConfig} from './server/config.ts';
const path='/etc/ar-assembly/relay.env';
const text=readFileSync(path,'utf8');
const updates={
  MULTI_USER:'false', RECORDING_ENABLED:'true',
  S3_RECORDING_BUCKET:'safeops-aiserver-706762893591-ap-northeast-2-an',
  AWS_REGION:'ap-northeast-2', RECORDING_DIRECTORY:'/var/lib/ar-assembly/recordings',
  RECORDING_FILE_BYTES:'15000000', RECORDING_OWNER_BYTES:'15000000',
  RECORDING_MAX_SECONDS:'30', RECORDING_CONCURRENT:'1',
};
readConfig({...parseEnv(text),...updates});
const retained=text.split(/\r?\n/).filter(line=>!Object.keys(updates).some(key=>line.startsWith(key+'=')));
writeFileSync(path,retained.join('\n').trimEnd()+'\n'+Object.entries(updates).map(([k,v])=>`${k}=${v}`).join('\n')+'\n',{mode:0o600});
NODE
printf '[Service]\nReadWritePaths=/var/lib/ar-assembly/recordings\nTimeoutStopSec=120\n' > /etc/systemd/system/ar-supervisor.service.d/recordings-check.conf
chmod 644 /etc/systemd/system/ar-supervisor.service.d/recordings-check.conf
ln -sfn "$next" /opt/ar-assembly/current
systemctl daemon-reload
systemctl restart ar-supervisor
for attempt in $(seq 1 30); do
  if curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent -H 'X-Real-IP: 127.0.0.1' http://127.0.0.1:8787/health
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-production.ts
node --env-file=/etc/ar-assembly/relay.env deploy/smoke-video.ts
test "$(systemctl is-active nova || true)" = "$nova_before"
trap - ERR
printf '\nPASS restricted recording release: %s\nBackup: %s\n' "$next" "$backup"
printf 'Owner-only; 30 seconds; 15000000 bytes; one concurrent; phone opt-in required.\n'
