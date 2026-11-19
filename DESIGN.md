# 설계도 — news-stock-mlops (미니 프로젝트 5)

발표: 2026-11-24(화) 15시, 개인 5분. 작성: 2026-11-18.
만드는 순서와 진행 상황: [docs/PLAN.md](docs/PLAN.md)

## 1. 목표와 원칙

- **질문**: 기업 · 대표 · 대표 상품이 헤드라인에 뜨면 주가에 얼마나 영향을 주는가.
- **서비스**: 헤드라인을 받으면 "다음 거래일에 그 종목이 시장보다 오를 확률"을 돌려주는 API.
- **채점 대상은 파이프라인이다.** 정확도는 50%대 초반을 예상한다. 발표는 "게이트가 통과시킨 날과 막은 날"로 한다.
- **모든 실행은 태스크 러너를 거친다.** 사람도 CI 도 서버도 `task <이름>` 만 친다 (3절).
- **코드와 모델은 다른 길로 배포한다.** 코드는 이미지(GHCR), 모델은 버킷. 수업 구조를 따른다.
- **버킷 접근 키를 만들지 않는다.** 버킷은 Lightsail 서버만 읽고 쓴다 (리소스 액세스).
- 하지 않는 것: 투자 권유, 실시간(분 단위) 예측, 본문 크롤링, 딥러닝 모델, Go/Rust 서빙(시간이 남을 때만).

## 2. 문제 정의

### 2.1 종목

설정은 `config/tickers.yml` 한 파일에 둔다. 코드에 종목을 적지 않는다.

| 종목 | 코드 | 시장 | 비교 지수 | 헤드라인 언어 |
|---|---|---|---|---|
| 삼성전자 | 005930 | 코스피 | KS11 | 한국어 |
| 카카오 | 035720 | 코스피 | KS11 | 한국어 |
| SM엔터테인먼트 | 041510 | 코스닥 | KQ11 | 한국어 |
| 애플 | AAPL | 나스닥 | IXIC | 영어 |
| 엔비디아 | NVDA | 나스닥 | IXIC | 영어 |

종목마다 적는 것: 코드, 시장, 비교 지수, 검색어, 언어, 기업명 별칭, 대표 이름(재임 기간 포함), 대표 상품.

### 2.2 한 행의 정의

- **행**: (종목, 거래일 T) 하나.
- **입력**: 날짜가 T 이상이고 다음 거래일 미만인 헤드라인 전부. 토 · 일 · 공휴일 기사는 직전 거래일 T 에 묶인다.
- **정답**: `(T+1 종가 / T 종가 − 1) − (같은 기간 비교 지수 수익률) > 0` 이면 1.
- 날짜는 그 시장의 현지 날짜로 센다 (한국 종목은 KST, 미국 종목은 미국 동부).
- 근거가 된 사례: 2022-10-15(토) 카카오 장애 → 10-17(월) 카카오 −5.93%, 코스피 +0.32%. 11-11 의 +15.55% 는 코스피도 +3.37% 인 날이라 시장 대비로 재야 한다.

### 2.3 특징 (뉴스만 쓴다)

주가는 정답을 만들 때만 쓰고 모델 입력에는 넣지 않는다. 서빙할 때 실시간 주가를 받아와야 하면 학습과 서빙이 어긋나고, API 가 외부 서비스에 의존하게 되기 때문이다.

| 묶음 | 특징 |
|---|---|
| 언급 유형 | 기업명 언급 건수, 대표 언급 건수, 대표 상품 언급 건수 |
| 뉴스 양 | 건수, 종목 평균 대비 배수 (평균은 학습 때 계산해 모델 카드에 고정) |
| 어휘 | 호재 단어 건수, 악재 단어 건수 (언어별 사전, `config/lexicon.yml`) |
| 달력 | 요일, 묶인 날 수 (주말 · 연휴가 끼면 2 이상) |
| 종목 | 종목 one-hot |

특징 계산은 `features/` 모듈 하나가 한다. 학습과 API 가 같은 함수를 부른다.

### 2.4 모델과 기준선

- 모델: scikit-learn 로지스틱 회귀 (다섯 종목을 한 모델로). 비교용으로 그래디언트 부스팅 하나.
- 기준선(rule): 뉴스를 보지 않고 학습 구간의 다수 쪽으로만 답한다.
- 서빙: ONNX 로 변환해 onnxruntime 으로 실행. 이미지에 scikit-learn 을 넣지 않는다.

## 3. 태스크 러너

### 3.1 도구

[Task](https://taskfile.dev) (`Taskfile.yml`) 를 쓴다.

- 실행 파일 하나라 Windows(내 PC) · Ubuntu(GitHub 러너) · Amazon Linux(Lightsail) 에서 같은 명령이 돈다.
- 서버의 파이썬은 3.9 이고 uv 가 없다. 파이썬에 얹는 러너(poe 등)는 서버에서 못 쓴다.
- 셸 해석기가 내장돼 있어 Windows 에 bash 가 없어도 같은 Taskfile 이 돈다.

### 3.2 규칙

1. 워크플로 YAML 에 로직을 쓰지 않는다. Job 하나는 `checkout → 도구 설치 → task <이름>` 이다.
2. 로컬에서 통과한 `task` 가 CI 에서 그대로 돈다. CI 전용 명령을 만들지 않는다.
3. 단계 하나가 태스크 하나다. 실패는 종료 코드 1 로 알리고, 묶음 태스크는 거기서 멈춘다.
4. 값은 환경 변수로 받는다 (`VER`, `DATE`, `MODEL_BUCKET`). 비밀 값은 Taskfile 에 적지 않는다.
5. `task --list` 가 이 프로젝트의 사용 설명서다. 모든 태스크에 `desc` 를 단다.

### 3.3 태스크 목록

| 태스크 | 하는 일 | 도는 곳 |
|---|---|---|
| `setup` | `uv sync` | 로컬 · GitHub |
| `test` | pytest (특징 · API · 게이트 판정) | 로컬 · GitHub |
| `data:backfill` | 과거 헤드라인 · 주가를 한 번에 수집 | 로컬 (1회) |
| `data:daily` | 어제~오늘 헤드라인과 주가 수집 → `data/incoming/` | GitHub |
| `data:check` | 수집분 검사 (빈 날, 중복, 날짜 범위, 종목 누락) | GitHub |
| `data:store` | `data/incoming/` 을 버킷에 올린다 | 서버 |
| `data:fetch` | 버킷의 전체 데이터와 현재 모델을 받는다 | 서버 |
| `model:features` | 헤드라인 + 주가 → 학습표 | GitHub |
| `model:train` | 학습 → `artifacts/model.joblib` | GitHub |
| `model:gate` | 검증 게이트 (4.3) | GitHub |
| `model:export` | ONNX 변환 | GitHub |
| `model:parity` | scikit-learn 과 ONNX 의 답 비교 | GitHub |
| `model:card` | 버전 이름 · 지표 · 데이터 기간 · 특징 평균을 `model.json` 에 | GitHub |
| `model` | 위 여섯 개를 순서대로 | 로컬 · GitHub |
| `api:serve` | 로컬에서 API 실행 | 로컬 |
| `api:image` | 이미지 빌드 | 로컬 · GitHub |
| `api:smoke` | `/health` 와 `/predict` 한 번씩 | 로컬 · 서버 |
| `deploy:image` | 새 이미지 태그로 교체, 안 뜨면 이전 태그로 | 서버 |
| `deploy:promote` | 새 모델을 버킷에 올리고 띄운 뒤 포인터 변경 | 서버 |
| `deploy:rollback` | `VER` 의 모델로 되돌린다 | 서버 |
| `deploy:status` | 서버의 이미지 태그 · 모델 버전 · `/health` | 서버 |

## 4. 흐름

### 4.1 코드 배포 — `ci.yml`

```
PR · main 푸시 ─ test (GitHub) : task test
v* 태그 ─────── test → image (GitHub) : task api:image → GHCR
                     → deploy (서버)  : task deploy:image
```

### 4.2 모델 배포 — `model.yml`

평일 아침 1회 예약 실행 (미국 장 마감 뒤, 한국 시간 07시대) + 수동 실행.

```
collect (GitHub) : task data:daily → task data:check        새 데이터 수집
   │ artifact: incoming
store   (서버)   : task data:store → task data:fetch        버킷 적재 후 전체를 내려받음
   │ artifact: dataset + 현재 모델
train   (GitHub) : task model                               학습 → 게이트 → ONNX → parity → 카드
   │ artifact: model
promote (서버)   : task deploy:promote                      버킷에 새 버전 → 띄워서 확인 → 포인터
```

- 새 데이터는 게이트 결과와 상관없이 먼저 버킷에 쌓인다. 학습이 실패해도 데이터는 남는다.
- 버킷은 서버의 Job 만 만진다. GitHub 러너와는 artifact 로 주고받는다.
- 오늘 수집한 행은 정답이 아직 없다. 학습에는 정답이 생긴 행까지만 쓴다.

### 4.3 검증 게이트

`task model:gate` 는 아래 중 하나라도 어기면 종료 코드 1 이다.

1. **데이터**: 학습 행 수가 기준 이상이고, 다섯 종목이 모두 들어 있다.
2. **기준선**: 최근 60거래일(떼어 둔 구간)에서 정확도가 기준선보다 높다.
3. **현재 모델**: 같은 구간에서 지금 서비스 중인 모델보다 나쁘지 않다 (허용 오차 안).

기준 숫자는 과거 데이터로 한 번 돌려 본 뒤 정한다. 판정 이유는 `model.json` 과 Job 요약에 남긴다.

### 4.4 parity

- 고정 표본 200행에 대해 scikit-learn 과 ONNX 의 확률 차이가 허용 오차 이내.
- 같은 헤드라인 묶음에 대해 학습 쪽 특징과 API 쪽 특징이 같은지는 `task test` 에서 본다.

### 4.5 롤백 — `rollback.yml`

수동 실행, 입력은 모델 버전. `task deploy:rollback` 이 버킷에 이미 있는 버전을 받아 띄우고, `/health` 의 `model_version` 을 확인한 뒤 포인터를 바꾼다. 안 뜨면 서버는 이전 버전으로 돌아가고 포인터는 그대로다. 이미지는 건드리지 않는다.

## 5. 저장소와 서버

### 5.1 버킷

```
data/news/<종목>/<YYYY-MM>.jsonl     헤드라인 {date, title, source}
data/prices/<코드>.csv               종목 · 지수 일별 종가
models/<버전>/model.onnx            버전마다 폴더 하나, 올린 뒤 고치지 않는다
models/<버전>/model.json            모델 카드
models/current.json                 포인터 — 지금 서비스 중인 버전
```

버전 이름은 `m<날짜>-<실행 번호>` (예: `m20261121-3`).

### 5.2 서버 (Lightsail 인스턴스)

- Docker Compose 로 API 컨테이너 하나. 80 → 8080.
- GitHub self-hosted 러너. 서버에서 도는 Job 은 이 러너가 받는다.
- `/srv/news/` 에 `.env`(이미지 태그 · 모델 버전), `compose.yml`, `models/`.
- 저장소는 비공개로 둔다. 공개 저장소에 self-hosted 러너를 붙이면 남의 PR 이 내 서버에서 실행될 수 있다.

### 5.3 API

| 경로 | 내용 |
|---|---|
| `GET /health` | `{status, app_version, model_version}` |
| `POST /predict` | 입력 `{ticker, headlines[]}` → `{ticker, prob_up, model_version, features}` |
| `GET /tickers` | 지원 종목과 별칭 |

- 응답에 `model_version` 을 넣는다. 승격 · 롤백이 눈에 보인다.
- 응답에 `features` 를 넣는다. 어떤 언급이 잡혔는지 보여 준다.
- 모델 파일이 없으면 기준선(rule)으로 답한다.

### 5.4 폴더 구조

```
Taskfile.yml
config/tickers.yml  lexicon.yml
collect/            news.py  prices.py  check.py
features/           build.py            (학습 · API 공용)
training/           dataset.py  train.py  gate.py  export_onnx.py  parity.py  card.py
api/                app.py  predictors/  Dockerfile  tests/
deploy/lightsail/   compose.yml  server.sh  models.py  bootstrap.sh
.github/workflows/  ci.yml  model.yml  rollback.yml
```

## 6. 확인된 사실 (2026-11-18)

| 항목 | 결과 |
|---|---|
| 주가 (FinanceDataReader) | 다섯 종목과 지수 KS11 · KQ11 · IXIC 모두 2023-01 부터 받아짐. 한국 946거래일, 미국 973거래일 |
| 과거 헤드라인 (Google 뉴스 RSS, 하루 단위 조회) | 삼성전자 2~5건, 카카오 4~6건, SM 3~6건, 애플(영어) 1~3건, 엔비디아(영어) 1~8건 |
| 과거 기사의 시각 | 07:00 · 08:00 GMT 로 뭉개져 있다. 날짜만 믿는다 |
| 주 단위 조회 | 한 주에 10건 남짓만 나온다. 하루 단위로 조회해야 한다 |
| SM 검색어 | "에스엠" 은 다른 회사(에스엠투네트웍스 등)가 섞인다. 별칭으로 걸러야 한다 |
| 내 PC | Task · aws CLI 없음. uv · Docker · gh 있음 |

## 7. 위험과 대비

| 위험 | 대비 |
|---|---|
| 과거 수집이 대량 조회에서 막힌다 (다섯 종목 × 약 1,780일 = 약 8,900회, 2022-01 부터) | 로컬에서 4~6초 간격으로 수집, 끊겨도 이어받는다. 계속 막히면 기간을 2025-01 이후로 줄인다 |
| 미국 종목의 헤드라인이 하루 1건뿐인 날이 많다 | 건수가 0인 날도 행으로 둔다. 검색어를 넓혀 본다 |
| 모델이 기준선을 못 넘어 승격이 한 번도 안 된다 | 첫 버전은 과거 데이터로 로컬에서 게이트를 통과시켜 올린다. 탈락 시연은 학습을 일부러 덜 시켜 만든다 |
| Job 네 개가 서버와 GitHub 를 오가서 시간이 부족하다 | 버킷 접근 키를 Secrets 에 넣고 Job 두 개(train · promote)로 줄인다. 키 없는 원칙을 포기하는 대안이다 |
| 대표가 기간에 따라 바뀐다 | `tickers.yml` 에 재임 기간을 적고, 기사 날짜로 고른다 |

## 8. 일정

| 날짜 | 할 일 | 끝났다는 기준 |
|---|---|---|
| 11/18(수) | 저장소 · Taskfile 뼈대 · `tickers.yml`, 과거 수집 시작 | `task data:backfill` 이 돌고 있다 |
| 11/19(목) | 특징 · 학습 · 게이트 · ONNX · parity | 로컬에서 `task model` 통과 |
| 11/20(금) | API · Dockerfile · 테스트 · `ci.yml` | 태그를 밀면 GHCR 에 이미지가 생긴다 |
| 11/21(토) | Lightsail 인스턴스 · 버킷 · 러너, `deploy:*` | 서버 `/health` 응답, 첫 모델 승격 |
| 11/22(일) | `model.yml` 예약 실행, `rollback.yml`, 탈락 시연 | 승격 · 탈락 · 롤백을 한 번씩 실행 |
| 11/23(월) | 발표 자료 · 리허설 | 5분 안에 끝난다 |

## 9. 발표에 담을 것

- 설계 이유: 왜 다음 거래일인가, 왜 시장 대비인가 (카카오 사례 표).
- Flow: 코드의 길과 모델의 길, 버킷을 서버만 만지는 이유.
- 개선한 점: 태스크 러너로 로컬 = CI = 서버, 실제 새 데이터로 매일 재학습, 현재 모델과 비교하는 게이트.
- AI 에게 제공한다면: `/predict` 를 도구로 감싸 에이전트가 헤드라인을 넣고 확률을 받게 한다 (선택).
