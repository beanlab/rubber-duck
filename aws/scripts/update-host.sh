#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || {
  echo "update-host.sh must run as root" >&2
  exit 1
}

log=$(mktemp)
trap 'status=$?; if (( status != 0 )); then cat "$log" >&2; fi; rm -f "$log"; exit "$status"' EXIT

apt_get() {
  local deadline=$((SECONDS + ${APT_LOCK_TIMEOUT:-600})) remaining output status line locked other
  local lock_error='^E: (Could not get lock /(var/lib/dpkg/lock(-frontend)?|var/lib/apt/lists/lock|var/cache/apt/archives/lock)([ .]|$)|Unable to acquire the dpkg frontend lock([ (]|$)|Unable to lock directory /(var/lib/apt/lists|var/cache/apt/archives)/?([ ,.]|$))'
  while (( SECONDS < deadline )); do
    remaining=$((deadline - SECONDS))
    if output=$(LC_ALL=C apt-get -o "DPkg::Lock::Timeout=$remaining" "$@" 2>&1); then
      printf '%s\n' "$output"
      return 0
    else
      status=$?
    fi
    printf '%s\n' "$output" >&2
    locked=false
    other=false
    while IFS= read -r line; do
      if [[ $line =~ $lock_error ]]; then
        locked=true
      elif [[ $line == E:* ]]; then
        other=true
      fi
    done <<<"$output"
    [[ $locked == true && $other == false ]] || return "$status"
    remaining=$((deadline - SECONDS))
    (( remaining > 0 )) || break
    echo "APT lock busy; retrying $*" >&2
    sleep "$((remaining < 5 ? remaining : 5))"
  done
  echo "timed out waiting for APT locks: $*" >&2
  return 1
}

{
  apt_get update
  DEBIAN_FRONTEND=noninteractive apt_get full-upgrade -y
  apt_get autoremove -y
  apt_get clean
} >"$log" 2>&1

if [[ -f /var/run/reboot-required ]]; then
  echo "reboot-required=true"
else
  echo "reboot-required=false"
fi
