#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 1 && -n $1 ]] || {
  echo "usage: health-check.sh <container-name>" >&2
  exit 2
}

CONTAINER_NAME=$1
STARTUP_SECONDS=${STARTUP_SECONDS:-30}

for _ in $(seq 1 "$STARTUP_SECONDS"); do
  state=$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)
  if [[ $state != true ]]; then
    echo "container $CONTAINER_NAME is not running" >&2
    docker ps -a --filter "name=^/${CONTAINER_NAME}$" >&2 || true
    docker logs --tail 200 "$CONTAINER_NAME" >&2 || true
    exit 1
  fi
  sleep 1
done

status=$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME")
echo "container=$CONTAINER_NAME status=$status startup-seconds=$STARTUP_SECONDS"
