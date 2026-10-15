#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || {
  echo "instance-bootstrap.sh must run as root" >&2
  exit 1
}
[[ $# -eq 1 && $1 =~ ^vol-[0-9a-f]+$ ]] || {
  echo "usage: instance-bootstrap.sh <ebs-volume-id>" >&2
  exit 2
}

VOLUME_ID=$1
MOUNT_POINT=/var/lib/rubber-duck
BOOTSTRAP_STATE=/var/lib/rubber-duck-bootstrap

wait_for_apt() {
  local lock
  for _ in $(seq 1 120); do
    for lock in /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock; do
      if fuser "$lock" >/dev/null 2>&1; then
        sleep 5
        continue 2
      fi
    done
    return 0
  done
  echo "timed out waiting for package-manager locks" >&2
  return 1
}

wait_for_apt
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y awscli ca-certificates docker.io jq util-linux

systemctl enable --now docker
if systemctl list-unit-files --type=service --no-legend | awk '$1 == "amazon-ssm-agent.service" { found = 1 } END { exit !found }'; then
  ssm_unit=amazon-ssm-agent.service
elif systemctl list-unit-files --type=service --no-legend | awk '$1 == "snap.amazon-ssm-agent.amazon-ssm-agent.service" { found = 1 } END { exit !found }'; then
  ssm_unit=snap.amazon-ssm-agent.amazon-ssm-agent.service
else
  echo "Canonical SSM agent service was not found" >&2
  exit 1
fi
systemctl enable --now "$ssm_unit"
systemctl is-active --quiet "$ssm_unit" || {
  echo "Canonical SSM agent failed to start" >&2
  exit 1
}

install -d -m 0755 /etc/rubber-duck "$BOOTSTRAP_STATE"
install -d -m 0750 "$MOUNT_POINT"

volume_token=${VOLUME_ID//-/}
device=""
for _ in $(seq 1 120); do
  for candidate in /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${VOLUME_ID} /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volume_token}; do
    if [[ -e $candidate ]]; then
      device=$(readlink -f "$candidate")
      break 2
    fi
  done
  sleep 5
done
[[ -n $device && -b $device ]] || {
  echo "could not resolve expected EBS volume $VOLUME_ID through /dev/disk/by-id" >&2
  exit 1
}

filesystem=$(blkid -o value -s TYPE "$device" || true)
if [[ -z $filesystem ]]; then
  if ! cmp -n $((4 * 1024 * 1024)) "$device" /dev/zero >/dev/null 2>&1; then
    echo "refusing to format $VOLUME_ID because its first 4 MiB are not empty" >&2
    exit 1
  fi
  mkfs.ext4 -F "$device"
elif [[ $filesystem != ext4 ]]; then
  echo "unexpected filesystem on $VOLUME_ID: $filesystem" >&2
  exit 1
fi

uuid=$(blkid -o value -s UUID "$device")
[[ -n $uuid ]] || {
  echo "could not determine filesystem UUID for $VOLUME_ID" >&2
  exit 1
}

if ! grep -qE "^[[:space:]]*UUID=${uuid}[[:space:]]" /etc/fstab; then
  printf 'UUID=%s %s ext4 defaults,nofail 0 2\n' "$uuid" "$MOUNT_POINT" >>/etc/fstab
fi
if mountpoint -q "$MOUNT_POINT"; then
  mounted_uuid=$(findmnt -nro UUID --target "$MOUNT_POINT")
  [[ $mounted_uuid == "$uuid" ]] || {
    echo "$MOUNT_POINT is mounted from an unexpected filesystem" >&2
    exit 1
  }
else
  mount "$MOUNT_POINT"
fi
chown root:root "$MOUNT_POINT"
chmod 0750 "$MOUNT_POINT"

install -d -m 0755 /etc/systemd/journald.conf.d
cat >/etc/systemd/journald.conf.d/rubber-duck-retention.conf <<'EOF'
[Journal]
SystemMaxUse=500M
MaxRetentionSec=14day
EOF
systemctl restart systemd-journald

touch "$BOOTSTRAP_STATE/complete"
chmod 0644 "$BOOTSTRAP_STATE/complete"
