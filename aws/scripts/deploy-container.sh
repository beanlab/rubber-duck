#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "usage: deploy-container.sh <image-digest-uri> <commit-sha> <human-readable-tag>" >&2
}

[[ ${EUID:-$(id -u)} -eq 0 ]] || {
  echo "deploy-container.sh must run as root" >&2
  exit 1
}
[[ $# -eq 3 ]] || {
  usage
  exit 2
}

IMAGE_URI=$1
COMMIT_SHA=$2
IMAGE_TAG=$3
[[ $IMAGE_URI =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-zA-Z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || {
  echo "invalid ECR digest URI" >&2
  exit 2
}
[[ $COMMIT_SHA =~ ^[0-9a-f]{40}$ ]] || {
  echo "commit SHA must contain 40 lowercase hexadecimal characters" >&2
  exit 2
}
[[ $IMAGE_TAG == production-$COMMIT_SHA ]] || {
  echo "image tag must be production-<full-commit-sha>" >&2
  exit 2
}

read_setting() {
  local path=$1
  [[ -f $path ]] || {
    echo "missing fixed instance setting: $path" >&2
    exit 1
  }
  local value
  value=$(<"$path")
  [[ -n $value ]] || {
    echo "empty fixed instance setting: $path" >&2
    exit 1
  }
  printf '%s' "$value"
}

ENVIRONMENT=$(read_setting /etc/rubber-duck/environment)
CONFIG_BASE_URI=$(read_setting /etc/rubber-duck/config-uri)
SECRET_ID=$(read_setting /etc/rubber-duck/secret-id)
AWS_REGION=$(read_setting /etc/rubber-duck/aws-region)
[[ $ENVIRONMENT == production ]] || {
  echo "unsupported environment: $ENVIRONMENT" >&2
  exit 1
}
[[ $CONFIG_BASE_URI == s3://rubber-duck-config/environments/$ENVIRONMENT/config.yaml ]] || {
  echo "unexpected configuration base URI" >&2
  exit 1
}
# Keep the fixed host setting as the base; select the config paired with this image.
CONFIG_URI="${CONFIG_BASE_URI%/*}/production-config-$COMMIT_SHA.yaml"

CONTAINER_NAME="rubber-duck-$ENVIRONMENT"
DATA_DIR=/var/lib/rubber-duck
DATABASE_PATH=$DATA_DIR/rubber-duck.db
RELEASE_FILE=$DATA_DIR/release.json
REGISTRY=${IMAGE_URI%%/*}
REPOSITORY=${IMAGE_URI%@sha256:*}

exec 9>/run/lock/rubber-duck-deploy.lock
flock -n 9 || {
  echo "another deployment is already running" >&2
  exit 1
}

secret_json=$(mktemp)
env_file=$(mktemp)
release_tmp=$(mktemp "$DATA_DIR/.release.XXXXXX")
cleanup() {
  status=$?
  docker logout "$REGISTRY" >/dev/null 2>&1 || true
  rm -f "$secret_json" "$env_file" "$release_tmp"
  trap - EXIT
  exit "$status"
}
trap cleanup EXIT
chmod 0600 "$secret_json" "$env_file" "$release_tmp"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker pull "$IMAGE_URI"
[[ $(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$IMAGE_URI") == "$COMMIT_SHA" ]] || {
  echo "image revision does not match the requested commit/configuration" >&2
  exit 1
}
# Fail before stopping the current container if the matching config is unavailable.
aws s3api head-object \
  --region "$AWS_REGION" \
  --bucket rubber-duck-config \
  --key "environments/$ENVIRONMENT/production-config-$COMMIT_SHA.yaml" >/dev/null

[[ -f $DATABASE_PATH ]] || install -m 0640 -o root -g root /dev/null "$DATABASE_PATH"

aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString \
  --output text >"$secret_json"

jq -e '
  type == "object" and
  length > 0 and
  (has("AWS_ACCESS_KEY_ID") | not) and
  (has("AWS_SECRET_ACCESS_KEY") | not) and
  (has("AWS_SESSION_TOKEN") | not) and
  all(to_entries[];
    (.key | test("^[A-Za-z_][A-Za-z0-9_]*$")) and
    (.value | type == "string") and
    (.value | test("[\\r\\n]") | not)
  )
' "$secret_json" >/dev/null || {
  echo "runtime secret must be a non-empty JSON object of single-line string values" >&2
  exit 1
}
jq -r 'to_entries[] | "\(.key)=\(.value)"' "$secret_json" >"$env_file"

if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  docker stop "$CONTAINER_NAME"
  docker rm "$CONTAINER_NAME"
fi

docker run \
  --detach \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --env-file "$env_file" \
  --env "AWS_REGION=$AWS_REGION" \
  --env "AWS_DEFAULT_REGION=$AWS_REGION" \
  --env "CONFIG_FILE_S3_PATH=$CONFIG_URI" \
  --mount "type=bind,src=$DATABASE_PATH,dst=/rubber-duck.db" \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  "$IMAGE_URI"

if ! /usr/local/sbin/health-check.sh "$CONTAINER_NAME"; then
  docker logs --tail 200 "$CONTAINER_NAME" >&2 || true
  exit 1
fi

jq -n \
  --arg environment "$ENVIRONMENT" \
  --arg commit "$COMMIT_SHA" \
  --arg tag "$IMAGE_TAG" \
  --arg digest_uri "$IMAGE_URI" \
  --arg config_uri "$CONFIG_URI" \
  --arg deployed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{environment:$environment,commit:$commit,tag:$tag,digest_uri:$digest_uri,config_uri:$config_uri,deployed_at:$deployed_at}' \
  >"$release_tmp"
chmod 0600 "$release_tmp"
mv -f "$release_tmp" "$RELEASE_FILE"

current_image_id=$(docker image inspect --format '{{.Id}}' "$IMAGE_URI")
while read -r repository image_id; do
  if [[ $repository == "$REPOSITORY" && $image_id != "$current_image_id" ]]; then
    docker image rm "$image_id" >/dev/null 2>&1 || true
  fi
done < <(docker image ls --no-trunc --format '{{.Repository}} {{.ID}}')

echo "deployed environment=$ENVIRONMENT commit=$COMMIT_SHA tag=$IMAGE_TAG digest_uri=$IMAGE_URI"
