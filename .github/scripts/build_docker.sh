#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
IMAGE=${IMAGE_NAME:-rubber-duck}
TAG=${IMAGE_TAG:-${GITHUB_SHA:-$(git -C "$ROOT" rev-parse HEAD)}}

[[ "$TAG" =~ ^[0-9a-f]{40}$ ]] || {
  echo "IMAGE_TAG must be a full 40-character Git commit SHA" >&2
  exit 2
}

docker build --pull --tag "$IMAGE:$TAG" "$ROOT"
