# API 이미지. 빌드 위치는 저장소 루트다:  task api:image
# scikit-learn · 수집 도구는 넣지 않는다 (의존성 그룹 api 만). 모델도 넣지 않는다 — 서버가 /models 에 붙인다.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"

# 의존성 층을 코드보다 먼저 만든다 — 코드만 바뀌면 이 층은 다시 받지 않는다
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --only-group api

# 특징 계산(features/)과 종목 설정은 학습과 같은 파일을 그대로 넣는다
COPY config/tickers.yml config/lexicon.yml config/
COPY collect/__init__.py collect/config.py collect/
COPY features/ features/
COPY api/ api/

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION MODEL_DIR=/models/none
USER nobody
EXPOSE 8080
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8080"]
