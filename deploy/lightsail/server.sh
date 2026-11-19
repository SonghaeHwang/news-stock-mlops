#!/bin/bash
# 서버(Lightsail)에서 도는 배포 스크립트. 러너가 `task deploy:*` 로 부른다.
#   server.sh image <태그> <이미지>   코드 배포. GHCR 토큰은 환경 변수 GHCR_TOKEN 으로 받는다
#   server.sh model <버전>            /srv/news/models/<버전>/ 에 놓인 모델로 바꾼다 (승격 · 롤백 공통)
#   server.sh status                  .env, 컨테이너, /health
# 둘 다 "바꿔서 띄운다 → /health 로 확인한다 → 안 뜨면 이전 값으로 되돌린다" 순서다.
set -euo pipefail
SRV=/srv/news
HERE=$(cd "$(dirname "$0")" && pwd)
cp "$HERE/compose.yml" "$SRV/compose.yml" # 배포 파일은 언제나 저장소의 것으로
cd "$SRV"
touch .env

# setenv 키 값 : .env 의 그 키 줄을 새 값으로 바꾼다.  getenv 키 : 없으면 빈 문자열
setenv() { grep -v "^$1=" .env > .env.new || true; echo "$1=$2" >> .env.new; mv .env.new .env; }
getenv() { grep "^$1=" .env | cut -d= -f2- || true; }
unsetenv() { grep -v "^$1=" .env > .env.new || true; mv .env.new .env; }

# health [키 값] : /health 가 답할 때까지 30초 기다린다. 키 값을 주면 응답의 그 키가 그 값일 때만 성공
health() {
  local H
  for _ in $(seq 1 30); do
    H=$(curl -fsS localhost/health 2>/dev/null) && { [ -z "${1:-}" ] || echo "$H" | grep -q "\"$1\":\"$2\""; } \
      && echo "$H" && return 0
    sleep 1
  done
  echo "health 실패${1:+ — $1 이 $2 가 아니다}" >&2
  docker compose logs --tail 20 api >&2 || true
  return 1
}

case "${1:-}" in
  image)
    TAG=$2 IMAGE=$3
    [[ $TAG =~ ^v[0-9]+(\.[0-9]+)*$ ]] || { echo "태그 형식이 아니다: $TAG" >&2; exit 1; }
    [[ $IMAGE =~ ^[a-z0-9./_-]+$ ]] || { echo "이미지 이름 형식이 아니다: $IMAGE" >&2; exit 1; }
    : "${GHCR_TOKEN:?GHCR_TOKEN 이 없다}"
    # 로그인 정보는 임시 폴더에 두고 끝나면 지운다 (서버에 토큰을 남기지 않는다)
    DOCKER_CONFIG=$(mktemp -d); export DOCKER_CONFIG
    trap 'rm -rf "$DOCKER_CONFIG"' EXIT
    printf %s "$GHCR_TOKEN" | docker login ghcr.io -u token --password-stdin > /dev/null
    PREV_TAG=$(getenv TAG) PREV_IMAGE=$(getenv IMAGE)
    docker pull -q "$IMAGE:$TAG"
    setenv IMAGE "$IMAGE"; setenv TAG "$TAG"
    docker compose up -d
    if ! health app_version "$TAG"; then
      if [ -n "$PREV_TAG" ]; then
        echo "$TAG 이 뜨지 않았다 → 이전 태그 $PREV_TAG 로 되돌린다" >&2
        setenv IMAGE "$PREV_IMAGE"; setenv TAG "$PREV_TAG"; docker compose up -d
      fi
      exit 1
    fi
    ;;
  model)
    VER=$2
    [[ $VER =~ ^m[0-9]{8}-[0-9]+$ ]] || { echo "모델 버전 형식이 아니다: $VER" >&2; exit 1; }
    [ -f "models/$VER/model.onnx" ] && [ -f "models/$VER/model.json" ] || { echo "models/$VER 가 없다" >&2; exit 1; }
    [ -n "$(getenv TAG)" ] || { echo "이미지를 먼저 배포해야 한다 (v* 태그)" >&2; exit 1; }
    PREV=$(getenv MODEL_VERSION)
    setenv MODEL_VERSION "$VER"; setenv MODEL_DIR "/models/$VER"
    docker compose up -d
    if ! health model_version "$VER"; then
      echo "$VER 이 뜨지 않았다 → 이전 모델 ${PREV:-(없음, 기준선)} 로 되돌린다" >&2
      if [ -n "$PREV" ]; then setenv MODEL_VERSION "$PREV"; setenv MODEL_DIR "/models/$PREV"
      else unsetenv MODEL_VERSION; unsetenv MODEL_DIR; fi
      docker compose up -d
      exit 1
    fi
    ;;
  status)
    [ -n "$(getenv TAG)" ] || { echo "아직 배포한 이미지가 없다"; exit 0; }
    cat .env
    docker compose ps --format '{{.Service}} {{.Image}} {{.Status}}'
    health
    ;;
  *)
    echo "사용: server.sh image <태그> <이미지> | model <버전> | status" >&2; exit 2 ;;
esac
