#!/bin/bash
# 서버(Lightsail, Amazon Linux 2023)를 이 프로젝트가 돌 수 있게 만든다. 여러 번 돌려도 된다.
#   bash bootstrap.sh
#   RUNNER_URL=https://github.com/<소유자>/<저장소> RUNNER_TOKEN=<등록 토큰> bash bootstrap.sh   러너까지 등록
# 설치하는 것: Docker · Compose (없을 때만), Task, /srv/news/, GitHub self-hosted 러너(라벨 lightsail)
# 버킷은 콘솔에서 만들고 이 인스턴스를 "리소스 액세스"에 붙인다 — 키를 서버에 두지 않는다.
set -euo pipefail
TASK_VERSION=v3.54.0 # 내 PC 와 같은 판
RUNNER_DIR=$HOME/actions-runner-news

if ! command -v docker > /dev/null; then
  sudo dnf install -y docker
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  echo "docker 그룹에 넣었다 — 다시 접속한 뒤 이 스크립트를 한 번 더 돌린다"
fi
if ! docker compose version > /dev/null 2>&1; then
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
if [ "$(task --version 2> /dev/null)" != "${TASK_VERSION#v}" ]; then
  curl -fsSL https://taskfile.dev/install.sh | sudo sh -s -- -b /usr/local/bin "$TASK_VERSION"
fi

sudo mkdir -p /srv/news/models
sudo chown -R "$USER:$USER" /srv/news

if [ -n "${RUNNER_TOKEN:-}" ] && [ ! -f "$RUNNER_DIR/.runner" ]; then
  : "${RUNNER_URL:?RUNNER_URL 이 없다}"
  mkdir -p "$RUNNER_DIR" && cd "$RUNNER_DIR"
  VER=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | grep -oP '"tag_name": "v\K[^"]+')
  curl -fsSL "https://github.com/actions/runner/releases/download/v$VER/actions-runner-linux-x64-$VER.tar.gz" | tar xz
  ./config.sh --unattended --url "$RUNNER_URL" --token "$RUNNER_TOKEN" --name news-lightsail --labels lightsail --replace
  sudo ./svc.sh install "$USER"
  sudo ./svc.sh start
fi

echo "docker  : $(docker --version)"
echo "compose : $(docker compose version --short)"
echo "task    : $(task --version)"
echo "aws     : $(aws --version 2>&1 | cut -d' ' -f1)"
echo "폴더    : $(ls -d /srv/news /srv/news/models | tr '\n' ' ')"
echo "러너    : $([ -f "$RUNNER_DIR/.runner" ] && echo 등록됨 || echo 없음)"
