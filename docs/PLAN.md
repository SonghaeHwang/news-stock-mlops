# 진행 계획 — news-stock-mlops

무엇을 만드는지는 [DESIGN.md](../DESIGN.md), 어떤 순서로 만드는지는 이 문서가 맡는다.
진행 상황은 아래 체크박스로 관리한다. 단계를 끝내면 "끝났다는 기준"의 명령을 실제로 돌려 보고 체크한다.

발표: 2026-11-24(화) 15시. 작성: 2026-11-18.

## 진행 규칙

- 한 단계가 끝나기 전에 다음 단계의 코드를 만들지 않는다. 단, 0단계의 과거 수집은 뒤에서 계속 돌려 둔다.
- 새 실행 단계가 생기면 먼저 `Taskfile.yml` 에 태스크를 만들고, 그 태스크로만 실행한다.
- 단계를 끝낼 때마다 커밋한다. 서버에 올라가는 것은 `v*` 태그로만 올린다.
- 단계마다 "내가 정한 것 / AI 에게 맡긴 것 / AI 답을 고친 것"을 [DEVLOG.md](DEVLOG.md) 에 두세 줄 남긴다. 발표의 "AI 활용" 항목에 쓴다.
- 강의와 같은 구조를 쓰는 곳은 "왜 이렇게 하는지"를 내 말로 한 줄 적어 둔다. 발표 질의응답에 쓴다.
- 비밀 값(토큰 · 키 · 서버 IP)은 저장소 · 문서 · 로그에 적지 않는다.

`[직접]` 표시는 AWS 콘솔 · GitHub 설정처럼 내가 화면에서 직접 해야 하는 일이다.

## 0단계 — 준비 (11/18 수)

- [x] Task 설치 (`winget install Task.Task`), `task --version` 확인
- [x] `[직접]` GitHub 에 비공개 저장소 `news-stock-mlops` 만들기
- [x] `git init`, `uv init`, `.gitignore` (`data/`, `artifacts/`, `.env`)
- [x] `Taskfile.yml` 뼈대: `setup`, `test` 와 묶음 네 개(`data:` `model:` `api:` `deploy:`)의 빈 태스크에 `desc`
- [x] `config/tickers.yml` — 다섯 종목의 코드 · 시장 · 비교 지수 · 검색어 · 언어 · 별칭 · 대표(재임 기간) · 대표 상품
- [x] `[직접]` AWS 콘솔에 로그인되는지, Lightsail 을 쓸 수 있는지 확인

끝났다는 기준: `task --list` 에 태스크 목록이 설명과 함께 나온다.

## 1단계 — 데이터 수집 (11/18 수 ~ 11/19 목)

- [x] `collect/prices.py` — 다섯 종목과 지수 세 개의 일별 종가 → `data/prices/<코드>.csv`
- [x] `collect/news.py` — 종목 · 날짜 범위를 받아 하루 단위로 조회 → `data/news/<종목>/<YYYY-MM>.jsonl`. 이미 받은 날은 건너뛴다(끊겨도 이어서 받게)
- [x] 시험 수집: 한 종목 한 달치. 건수 · 중복 · 날짜를 눈으로 확인
- [ ] `task data:backfill` 로 전체 수집 (다섯 종목, 2022-01 ~ 어제) — **진행 중** (11/19 시작, 별도 창에서 `task data:news`). 속도와 이어받기는 [COLLECTION.md](COLLECTION.md) 3절
- [x] `collect/check.py` + `task data:check` — 빈 날 비율, 중복, 날짜 범위, 종목 누락
- [ ] `task data:daily` — 어제 ~ 오늘만 수집해 `data/incoming/` 에 둔다 (태스크는 있다. 과거 수집이 끝난 뒤 실행해 본다)

끝났다는 기준: `task data:check` 가 다섯 종목 모두 통과한다.

막혔을 때: 조회가 차단되면 간격을 늘리고, 그래도 안 되면 기간을 2025-01 이후로 줄인다. 이 결정은 11/19 오전까지 내린다.

## 2단계 — 학습표와 특징 (11/19 목)

- [ ] `config/lexicon.yml` — 호재 · 악재 단어, 한국어와 영어 각각 20~30개
- [x] `features/match.py` — 기업명 · 대표 · 대표 상품 · 계열사 언급 판정 (COLLECTION.md 4절), 테스트 20개
- [ ] `features/build.py` — 헤드라인 묶음 → 특징 (언급 유형, 건수, 어휘, 달력, 종목). 학습과 API 가 함께 쓴다
- [ ] `training/dataset.py` — 헤드라인을 거래일에 묶고(주말 · 공휴일은 직전 거래일), 시장 대비 다음 거래일 수익률로 정답을 붙인다
- [ ] 테스트: 토요일 기사가 금요일 행에 묶이는지, 정답이 비교 지수를 빼고 계산되는지, 정답이 없는 마지막 행이 학습에서 빠지는지
- [ ] `task model:features` → `artifacts/dataset.parquet`, 행 수와 정답 비율 출력

끝났다는 기준: `task test` 통과, 학습표의 종목별 행 수와 정답 비율(50% 근처)을 확인했다.

## 3단계 — 학습 · 게이트 · parity (11/19 목)

- [ ] `training/train.py` — 시간순으로 나눠 학습 (마지막 60거래일은 떼어 둔다)
- [ ] 기준선과 모델의 점수를 한 번 뽑아 보고, 게이트 기준 숫자를 정해 DESIGN.md 4.3 에 적는다
- [ ] `training/gate.py` — 데이터 · 기준선 · 현재 모델 세 가지 검사, 실패하면 종료 코드 1 과 이유 출력
- [ ] `training/export_onnx.py`, `training/parity.py` — 표본 200행에서 확률 차이 확인
- [ ] `training/card.py` — 버전 이름 · 지표 · 데이터 기간 · 종목별 평균 건수를 `model.json` 에
- [ ] `task model` 로 여섯 단계를 이어서 실행
- [ ] 탈락 확인: 학습을 일부러 망가뜨려(예: 데이터 5%만) `task model` 이 게이트에서 멈추는지 본다

끝났다는 기준: `task model` 이 통과해 `artifacts/model.onnx` · `model.json` 이 생기고, 망가뜨린 학습은 게이트에서 멈춘다.

## 4단계 — API 와 이미지 (11/20 금)

- [ ] `api/app.py` — `/health`, `/predict`, `/tickers`. 모델이 없으면 기준선으로 답한다
- [ ] `api/predictors/` — `rule`, `onnx`. `onnx` 는 `MODEL_DIR` 의 모델과 `model.json` 을 읽는다
- [ ] 테스트: 응답 모양, 모르는 종목, 빈 헤드라인, 학습 쪽 특징과 API 쪽 특징이 같은지
- [ ] `api/Dockerfile` (scikit-learn 없이), `task api:image`, `task api:smoke`

끝났다는 기준: 로컬 컨테이너에 `task api:smoke` 가 통과하고 응답에 `model_version` 이 나온다.

## 5단계 — 코드 CI/CD (11/20 금)

- [ ] `.github/workflows/ci.yml` — PR · main 은 `task test`, `v*` 태그는 `task api:image` 후 GHCR 푸시
- [ ] `[직접]` 저장소의 Actions 권한과 패키지 쓰기 권한 확인
- [ ] `v0.1.0` 태그를 밀어 이미지가 올라가는지 확인

끝났다는 기준: GHCR 에 `v0.1.0` 이미지가 있다. (서버 배포 Job 은 6단계에서 붙인다)

## 6단계 — 서버와 버킷 (11/21 토)

- [ ] `[직접]` Lightsail 인스턴스 만들기 (Amazon Linux 2023), 고정 IP, 80 포트 열기
- [ ] `[직접]` Lightsail 버킷 만들기, 인스턴스에 리소스 액세스 연결
- [ ] `deploy/lightsail/bootstrap.sh` — Docker · Compose · Task 설치, `/srv/news/` 만들기
- [ ] `[직접]` 서버에 GitHub self-hosted 러너 등록 (라벨 `lightsail`), 저장소 변수 `MODEL_BUCKET`
- [ ] `deploy/lightsail/compose.yml`, `server.sh` (image · model · status)
- [ ] `task deploy:image`, `task deploy:status` — `ci.yml` 에 서버 배포 Job 추가
- [ ] `v0.1.1` 태그로 서버까지 배포

끝났다는 기준: 서버 주소의 `/health` 가 `app_version: v0.1.1` 로 답한다. (요건 1 · 2)

## 7단계 — 모델 배포 (11/21 토 ~ 11/22 일)

- [ ] 과거 수집분을 서버로 옮겨 `task data:store` 로 버킷에 올린다 (버킷은 서버만 만진다)
- [ ] `deploy/lightsail/models.py` — `promote`, `rollback`. 띄워서 확인한 뒤에 포인터를 바꾼다
- [ ] `task data:store`, `task data:fetch`, `task deploy:promote`
- [ ] `.github/workflows/model.yml` — collect → store → train → promote, 수동 실행으로 먼저 확인
- [ ] 첫 승격: `/health` 의 `model_version` 이 새 버전으로 바뀌는지 확인

끝났다는 기준: `model.yml` 을 수동 실행하면 버킷에 새 데이터와 새 모델 버전이 생기고 서버가 그 버전으로 답한다. (요건 3 · 4)

## 8단계 — 예약 재학습 · 롤백 · 시연 준비 (11/22 일)

- [ ] `model.yml` 에 예약 실행 추가 (평일 아침 1회), 다음 날 실제로 돌았는지 확인
- [ ] `.github/workflows/rollback.yml` + `task deploy:rollback`
- [ ] 롤백 실행: 이전 버전으로 되돌리고 `/health` 로 확인
- [ ] 탈락 실행: 게이트에서 멈춰 promote Job 이 돌지 않는 실행 기록을 하나 남긴다
- [ ] 증거 모으기: 통과 · 탈락 · 롤백 세 실행의 화면과 링크

끝났다는 기준: 승격 · 탈락 · 롤백 실행 기록이 각각 하나씩 있다. (요건 5)

## 9단계 — 발표 (11/23 월)

- [ ] 발표 자료: 설계 이유(카카오 사례 표) → Flow 그림 → 실행 기록 세 장면 → AI 활용 → 개선한 점
- [ ] 예상 질문 답 정리: 왜 버킷을 서버만 만지나, 왜 모델을 이미지에 굽지 않나, 게이트 기준은 어떻게 정했나, 왜 주가를 입력에서 뺐나
- [ ] 리허설 2회, 5분 안에 끝나는지 시간 재기
- [ ] 발표 당일 아침 `task deploy:status` 로 서버 상태 확인

끝났다는 기준: 자료 없이도 Flow 를 말로 설명할 수 있다.

## 밀렸을 때 줄이는 순서

위에서부터 버린다. 다섯 요건에 닿는 것은 버리지 않는다.

1. 그래디언트 부스팅 비교 — 로지스틱 회귀 하나만 쓴다
2. `/tickers` 경로
3. 영어 어휘 사전 — 미국 종목은 건수와 언급 유형만 쓴다
4. Job 네 개 구조 — 버킷 접근 키를 Secrets 에 넣고 train · promote 두 개로 줄인다
5. 과거 기간 — 2025-01 이후로 줄인다
6. 미국 두 종목 — 한국 세 종목만 남긴다

## 요건 점검표

| # | 요건 | 확인하는 단계 | 보여 줄 증거 |
|---|---|---|---|
| 1 | Lightsail 인스턴스/버킷 | 6 · 7 | 서버 `/health`, 버킷의 `data/` · `models/` |
| 2 | GitHub CI/CD | 5 · 6 | 태그 → 테스트 → 이미지 → 서버 실행 기록 |
| 3 | 새 데이터 자동 학습 · 검증 | 7 · 8 | 예약 실행 기록, 게이트 통과 · 탈락 로그, parity 결과 |
| 4 | 통과 모델을 API 로 배포 | 7 | 승격 전후 `/health` 의 `model_version` |
| 5 | 롤백 | 8 | 롤백 실행 기록과 `model_version` 변화 |
