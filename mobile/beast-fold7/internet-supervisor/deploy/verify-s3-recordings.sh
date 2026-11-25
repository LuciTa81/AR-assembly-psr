#!/usr/bin/env bash
set -euo pipefail
umask 077
bucket=safeops-aiserver-706762893591-ap-northeast-2-an
region=ap-northeast-2
tmp=$(mktemp -d /tmp/ar-s3-verification.XXXXXXXX)
key="recordings/__verification/$(date -u +%Y%m%dT%H%M%SZ)-$(cat /proc/sys/kernel/random/uuid).txt"
uploaded=false
cleanup() {
  if "$uploaded"; then
    aws s3api delete-object --bucket "$bucket" --key "$key" --region "$region" >/dev/null || return 1
  fi
  rm -f -- "$tmp/source.txt" "$tmp/download.txt"
  rmdir -- "$tmp"
}
trap cleanup EXIT
printf 'AR Assembly authorized storage permission check; synthetic text only.\n' > "$tmp/source.txt"
# Only this invocation's unique synthetic object may be written or removed.
uploaded=true
aws s3api put-object --bucket "$bucket" --key "$key" --body "$tmp/source.txt" --content-type text/plain --server-side-encryption AES256 --region "$region" >/dev/null
aws s3api get-object --bucket "$bucket" --key "$key" --region "$region" "$tmp/download.txt" >/dev/null
cmp "$tmp/source.txt" "$tmp/download.txt"
aws s3api delete-object --bucket "$bucket" --key "$key" --region "$region" >/dev/null
uploaded=false
count=$(aws s3api list-objects-v2 --bucket "$bucket" --prefix "$key" --region "$region" --no-paginate --query KeyCount --output text)
test "$count" = 0
printf 'PASS: synthetic object upload, matching download, deletion, absence verified. No camera data.\n'
