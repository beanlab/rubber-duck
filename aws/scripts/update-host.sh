#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || {
  echo "update-host.sh must run as root" >&2
  exit 1
}

log=$(mktemp)
trap 'status=$?; if (( status != 0 )); then cat "$log" >&2; fi; rm -f "$log"; exit "$status"' EXIT

{
  for _ in $(seq 1 120); do
    locked=false
    for lock in /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock; do
      if fuser "$lock" >/dev/null 2>&1; then
        locked=true
        break
      fi
    done
    [[ $locked == false ]] && break
    sleep 5
  done
  [[ $locked == false ]] || {
    echo "timed out waiting for package-manager locks"
    exit 1
  }

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y
  apt-get autoremove -y
  apt-get clean
} >"$log" 2>&1

if [[ -f /var/run/reboot-required ]]; then
  echo "reboot-required=true"
else
  echo "reboot-required=false"
fi
