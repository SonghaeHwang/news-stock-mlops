# 진행 계획 — news-stock-mlops

무엇을 만드는지는 [DESIGN.md](../DESIGN.md), 어떤 순서로 만드는지는 이 문서가 맡는다.
내려받기가 끝난 뒤에 치는 명령의 순서는 [RUNBOOK.md](RUNBOOK.md) 에 있다.
진행 상황은 아래 체크박스로 관리한다. 단계를 끝내면 "끝났다는 기준"의 명령을 실제로 돌려 보고 체크한다.

발표: 2026-11-24(화) 15시. 작성: 2026-11-18.

## 진행 규칙

- **절대 규칙.** 과제 필수 기능 다섯 가지(Lightsail 인스턴스/버킷, GitHub CI/CD, 새 데이터 자동 학습 · 검증, 통과 모델 API 배포, 롤백)는 어떤 경우에도 빼거나 약화하지 않는다. 방법은 바꿔도 되지만 다섯 개 모두 시연할 수 있어야 한다. 설계 변경 · 범위 축소 · 일정 조정은 이 다섯 가지에 닿는지 먼저 확인한다. 목록과 증거는 아래 [요건 점검표](#요건-점검표).
- 한 단계가 끝나기 전에 다음 단계의 코드를 만들지 않는다. 단, 0단계의 과거 수집은 뒤에서 계속 돌려 둔다.
  - 예외 (11/19): 빅카인즈가 서버 점검으로 막혀 1단계의 전체 내려받기를 못 했다. 데이터가 없어도 되는 4 ~ 6단계와 7 · 8단계의 코드를 먼저 만들었다. 2 · 3단계의 체크는 전체 데이터를 받은 뒤에 한다.
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
- [x] ~~미국 종목(애플 · 엔비디아) 전체 수집~~ — 11/19 에 두 종목을 하이브 · SK하이닉스로 바꿨다 (받은 데이터는 지웠다). 아래는 그 전의 기록: `task data:news` (Google, 2022-01 ~ 어제) — 멈춰 있다 (11/19 기준 134일치, 2024-06 ~ 2026-11 일부). 다시 치면 이어서 받는다. 속도와 이어받기는 [COLLECTION.md](COLLECTION.md) 3절
- [x] `collect/check.py` + `task data:check` — 빈 날 비율, 중복, 날짜 범위, 종목 누락
- [x] ~~`task data:daily`~~ — 11/19 에 뺐다. 헤드라인은 Google 을 쓰지 않고 빅카인즈만 쓴다 (이유는 [TROUBLES.md](TROUBLES.md) 마지막 절). 그 전의 기록: 어제 ~ 오늘만 Google 에서 수집해 `data/incoming/` 에 둔다. 태스크(`data:daily` · `data:news`)와 `collect/news.py` 는 11/19 에 지웠다

다섯 종목(삼성전자 · 카카오 · SM · 하이브 · SK하이닉스) 모두 빅카인즈에서 받는다 (11/19 변경). 기준은 [COLLECTION.md](COLLECTION.md) 6절.

- [x] 검색어 조건 (기업명 · 줄임말 + 대표 + 대표 상품 · 아티스트) — `task data:bigkinds:query`
- [x] `collect/bigkinds.py` + `task data:bigkinds` — 엑셀 → `data/news/<종목>/<YYYY-MM>.jsonl`, 제목이 그 종목 기사인 것만 저장
- [x] 검색 건수 확인: OR · NOT · 긴 검색어가 되는지, 종목별 한 달 건수
- [x] `[직접]` 첫 내려받기 한 건(카카오 2022-10)으로 확인: 화면 검색 건수 10,093 = 파일 행 수 10,093, 한도는 20,000건 (11/19, Aside 로 내려받음)
- [ ] `[직접]` 전체 내려받기: 5종목 × 59개월 = 295개 파일 (하이브 · SK하이닉스는 11/19 추가) → `data/raw/bigkinds/<종목>_<시작일>-<끝일>.xlsx`
- [ ] `task data:bigkinds` 로 변환, `task data:check` 로 검사
- [x] 새 데이터를 넣는 방법 (11/19 정함): 엑셀을 `data/raw/bigkinds/` 에 넣으면 `task data:submit` 이 변환 → 주가 → 검사 → `dataset/`(날짜별 건수, 제목 없음) 커밋 · 푸시까지 한다. `dataset/` 이 바뀐 커밋이 올라오면 `model.yml` 이 시작된다. `task data:watch` 를 켜 두면 파일을 넣는 것만으로 `data:submit` 이 돈다
- [x] `collect/ingest.py`, `collect/watch.py`, `features/daily.py`, `features/build.py`, `training/*`, `config/lexicon.yml`(초안), `config/gate.yml`(초안), `.github/workflows/model.yml` · `ci.yml` — 가짜 건수 + 실제 주가로 `task model` 통과 · 탈락을 확인했다. 실제 데이터와 GitHub 에서의 실행은 아직이다

끝났다는 기준: `task data:check` 가 다섯 종목 모두 통과한다.

막혔을 때: 조회가 차단되면 간격을 늘리고, 그래도 안 되면 기간을 2025-01 이후로 줄인다. 이 결정은 11/19 오전까지 내린다.

## 2단계 — 학습표와 특징 (11/19 목)

- [ ] `config/lexicon.yml` — 호재 · 악재 단어, 한국어와 영어 각각 20~30개
- [x] `features/match.py` — 기업명 · 대표 · 대표 상품 · 계열사 언급 판정 (COLLECTION.md 4절), 테스트 20개
- [ ] `features/build.py` — 헤드라인 묶음 → 특징 (언급 유형, 건수, 어휘, 달력, 종목). 학습과 API 가 함께 쓴다
- [ ] `training/dataset.py` — 헤드라인을 거래일에 묶고(주말 · 공휴일은 직전 거래일), 시장 대비 다음 거래일 수익률로 정답을 붙인다
- [ ] 테스트: 토요일 기사가 금요일 행에 묶이는지, 정답이 비교 지수를 빼고 계산되는지, 정답이 없는 마지막 행이 학습에서 빠지는지
- [ ] `task model:features` → `artifacts/dataset.csv`, 행 수와 정답 비율 출력

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

- [x] `api/app.py` — `/health`, `/predict`, `/tickers`. 모델이 없으면 기준선으로 답한다
- [x] `api/predictors/` — `rule`, `onnx`. `onnx` 는 `MODEL_DIR` 의 모델과 `model.json` 을 읽는다. 카드의 특징 목록이 이미지의 특징 계산과 다르면 띄우지 않는다
- [x] 테스트: 응답 모양, 모르는 종목, 빈 헤드라인, 학습 쪽 특징과 API 쪽 특징이 같은지, ONNX 의 답이 scikit-learn 과 같은지 (`tests/test_api.py`)
- [x] `api/Dockerfile` (scikit-learn 없이), `task api:image`, `task api:run`, `task api:smoke`

끝났다는 기준: 로컬 컨테이너에 `task api:smoke` 가 통과하고 응답에 `model_version` 이 나온다.

## 5단계 — 코드 CI/CD (11/20 금)

- [x] `.github/workflows/ci.yml` — PR · main 은 `task test`, `v*` 태그는 `task api:image` · `task api:push` 로 GHCR 푸시
- [x] `[직접]` 저장소의 Actions 권한과 패키지 쓰기 권한 확인 — 따로 바꾸지 않아도 `v0.1.0` 이 올라갔다
- [x] `v0.1.0` 태그를 밀어 이미지가 올라가는지 확인 (11/19)

끝났다는 기준: GHCR 에 `v0.1.0` 이미지가 있다. (서버 배포 Job 은 6단계에서 붙인다)

## 6단계 — 서버와 버킷 (11/21 토)

- [x] `[직접]` Lightsail 인스턴스 (Amazon Linux 2023), 고정 IP, 80 포트 — 새로 만들지 않고 실습(eta)에 쓰던 인스턴스를 쓴다 (11/19). 2 vCPU · 메모리 1.9GB · 디스크 56GB 여유. eta 컨테이너는 내렸고 파일 · 이미지는 `/srv/eta` 에 그대로 있다
- [x] `[직접]` Lightsail 버킷 만들기, 인스턴스에 리소스 액세스 연결 — `shhwang-news-models` (시드니, 비공개, 접근 키 없음). 서버에서 목록 · 쓰기 · 읽기 · 지우기 확인 (11/20)
- [x] `deploy/lightsail/bootstrap.sh` — Docker · Compose · Task 설치, `/srv/news/` 만들기, 러너 등록. 여러 번 돌려도 된다
- [x] 서버에 GitHub self-hosted 러너 등록 (라벨 `lightsail`, 폴더 `~/actions-runner-news`. eta 의 러너와 따로다)
- [x] 저장소 변수 `MODEL_BUCKET` (11/20)
- [x] `deploy/lightsail/compose.yml`, `server.sh` (image · model · status)
- [x] `task deploy:image`, `task deploy:status` — `ci.yml` 에 서버 배포 Job 추가
- [x] 태그로 서버까지 배포 — `v0.1.0` 한 번에 테스트 → 이미지 → 서버까지 갔다 (11/19)

끝났다는 기준: 서버 주소의 `/health` 가 `app_version: v0.1.0` 으로 답한다. (요건 1 · 2) — 11/19 확인. 버킷은 11/20 에 붙였다

## 7단계 — 모델 배포 (11/21 토 ~ 11/22 일)

- [ ] `task data:store` 로 `dataset/` 을 버킷의 `data/dataset/` 에 올린다 (버킷은 서버만 만진다). `model.yml` 의 store Job 이 한다 — 서버에서 손으로 돌려 카카오 파일이 버킷에 올라가는 것을 확인했다 (11/20). `model.yml` 안에서 도는 것은 아직
- [ ] `deploy/lightsail/models.py` — `store`, `current`, `promote`, `rollback`, `list`. 띄워서 확인한 뒤에 포인터를 바꾼다 — 코드는 썼고 버킷을 붙인 뒤 확인한다
- [x] 모델 교체와 자동 복귀 (`server.sh model`): 정상 모델로 바뀌는 것, 특징 목록이 어긋난 모델은 뜨지 않고 이전 모델로 돌아가는 것을 서버에서 확인했다 (11/19, 시험 모델은 지웠다)
- [ ] `task data:store`, `task data:fetch`, `task deploy:promote`
- [ ] `.github/workflows/model.yml` — collect(새 빅카인즈 엑셀 변환 · 주가 · 검사) → store → train → promote, 수동 실행으로 먼저 확인. 시작 방법은 `dataset/` 이 바뀐 커밋 푸시 (47행, 11/19 정함)
- [ ] 첫 승격: `/health` 의 `model_version` 이 새 버전으로 바뀌는지 확인

끝났다는 기준: `model.yml` 을 수동 실행하면 버킷에 새 데이터와 새 모델 버전이 생기고 서버가 그 버전으로 답한다. (요건 3 · 4)

## 8단계 — 예약 재학습 · 롤백 · 시연 준비 (11/22 일)

- [ ] 새 엑셀을 `data/raw/bigkinds/` 에 넣으면 `task data:submit`(또는 `data:watch`)이 `dataset/` 을 푸시하고, 그 푸시로 `model.yml` 이 GitHub 에서 실제로 도는지 확인 (시작 방법은 47행, 11/19 정함). 그 전의 기록: 예약 실행(평일 아침 1회) — Google 매일 수집을 뺀 뒤로는 예약 실행이 받아 올 새 데이터가 없다
- [ ] `.github/workflows/rollback.yml` + `task deploy:rollback` — 코드는 썼고 첫 승격 뒤에 확인한다
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
