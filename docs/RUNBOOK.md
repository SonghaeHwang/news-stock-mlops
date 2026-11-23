# 실행 순서 — 내려받기가 끝난 뒤부터 시연 증거까지

빅카인즈 엑셀을 `data/raw/bigkinds/` 에 다 넣은 뒤에 무엇을 어떤 순서로 치는지 적는다.
내려받는 절차는 [COLLECTION.md](COLLECTION.md) 6.2절, 흐름의 설계는 [DESIGN.md](../DESIGN.md) 4절, 단계별 체크는 [PLAN.md](PLAN.md) 가 맡는다.

작성: 2026-11-20.

## 먼저 알아 둘 것

- **첫 실행은 로컬에서 먼저 본다.** `task data:submit` 은 `dataset/` 을 푸시하고, 그 푸시로 `model.yml` 이 store → train → promote 까지 간다. 저장소 변수 `MODEL_BUCKET` 이 있으므로 게이트를 통과하면 서버의 모델이 바로 바뀐다. `config/gate.yml` 의 기준은 11/21 에 정했다 (DESIGN.md 4.3).
- 두 번째부터는 엑셀을 넣고 `task data:submit` (또는 켜 둔 `task data:watch`) 하나면 된다. 이것이 요건 3 "새 데이터 자동 학습 · 검증"이다.
- 내려받는 중에는 1번을 돌리지 않는다. 옮기는 중인 파일을 읽을 수 있다.

## 1. 변환 (로컬, 푸시 없음)

```
task data:ingest
```

- 새로 넣은 엑셀만 `data/news/<종목>/<YYYY-MM>.jsonl` 로 바꾸고 `dataset/` (날짜별 건수) 을 다시 만든다.
- 파일마다 `새 파일 …: N행 중 M건 저장` 이 나온다. 제목이 그 종목 기사인 행이 5% 에 못 미치는 파일을 만나면 멈춘다 — 파일 이름에 종목을 잘못 붙인 것이다.
- 한 달을 반 달씩 나눠 받은 파일(삼성전자 2026-05 · 07)은 같은 달 파일에 이어 붙고, 기사 식별자로 중복을 거른다.

확인: `dataset/_files.csv` 의 행 수가 넣은 엑셀 수와 같고, `dataset/` 에 종목 다섯 개의 csv 가 있다.

## 2. 주가와 검사

```
task data:prices
task data:check
```

확인: `data:check` 가 다섯 종목 모두 통과한다. (PLAN 1단계의 끝났다는 기준)

## 3. 학습과 게이트 (로컬)

```
task model
```

학습표 → 학습 → 게이트 → ONNX → parity → 카드 순서다. 게이트에서 탈락하면 거기서 멈춘다.

볼 것:

| 파일 | 볼 값 |
|---|---|
| `artifacts/metrics.json` | 종목별 학습 행 수, 정답 비율(50% 근처), 모델과 기준선의 logloss |
| `artifacts/gate.json` | `passed`, 탈락했다면 `problems` 의 이유 |
| `artifacts/parity.json` | scikit-learn 과 ONNX 의 확률 차이 |

게이트의 세 검사 (`config/gate.yml`):

1. 데이터 — 종목마다 학습 행 200개 이상, 평가 행 100개 이상, 정답 비율 0.35 ~ 0.65
2. 기준선 — 모델의 logloss ≤ 기준선 + 0.01
3. 현재 모델 — 모델의 logloss ≤ 서비스 중인 모델 + 0.005 (첫 배포에서는 건너뛴다)

## 4. 기준을 정한다

- 통과했다면: 점수를 보고 `config/gate.yml` 의 숫자를 확정한다. DESIGN.md 4.3 에 숫자와 정한 이유를 적는다.
- 2번(기준선)에서 탈락했다면: `config/lexicon.yml` 의 어휘를 손보고 3번을 다시 돌린다. 기준 숫자를 통과에 맞춰 느슨하게 바꾸는 것은 마지막 수단이고, 바꿨다면 이유를 DEVLOG.md 에 적는다.
- PLAN.md 2 · 3단계를 체크하고, 바꾼 설정과 문서를 커밋한다 (`dataset/` 은 5번에서 올라간다).

## 5. 올린다 — 첫 승격

```
task data:submit
```

`dataset/` 이 커밋 · 푸시되고 GitHub 에서 `model.yml` 이 시작된다.

| Job | 어디서 | 하는 일 | 실패했을 때 볼 곳 |
|---|---|---|---|
| store | 서버 | `dataset/` 을 버킷에 올리고 현재 모델을 꺼낸다 | 버킷이 인스턴스에 리소스 액세스로 연결돼 있는지 |
| train | GitHub | `task test` → 주가 → `task model` | 실행의 artifact `model` 안의 `gate.json` |
| promote | 서버 | 버킷에 새 버전 → 띄워서 확인 → 포인터 변경 | 서버에서 `task deploy:status` |

확인: 서버 `/health` 의 `model_version` 이 새 버전(`m<날짜>-<실행 번호>`)이고, `task deploy:status` 의 버킷 목록에 그 버전이 있다. (요건 3 · 4, PLAN 7단계)

## 6. 두 번째 승격

롤백하려면 버킷에 버전이 둘 있어야 한다. 새 데이터가 없으면 `model.yml` 을 수동 실행해도 된다 (같은 데이터로 새 버전이 생긴다). 새 엑셀(예: 다음 달 파일, 또는 2024-11 이전의 과거 구간)을 `data/raw/bigkinds/` 에 넣고 다시 `task data:submit` 을 친다.

이번에는 게이트의 3번 검사가 돈다 — 새 모델이 서비스 중인 모델보다 나쁘면 탈락하고 promote 는 돌지 않는다.

## 7. 롤백

GitHub Actions 의 `rollback` 을 수동 실행하고, 입력에 되돌릴 버전(5번의 버전)을 넣는다.

확인: `/health` 의 `model_version` 이 이전 버전으로 바뀐다. (요건 5, PLAN 8단계)

## 8. 탈락 기록

게이트에서 멈춰 promote 가 돌지 않은 실행 기록이 하나 있어야 한다.

- 로컬에서는 `task model:features` → `task model:train SAMPLE=0.05` → `task model:gate` 로 탈락을 만들 수 있다.
- GitHub 의 실행 기록으로 남기려면 `model.yml` 을 수동 실행하면서 입력 `sample` 에 `0.05` 를 넣는다 (`gh workflow run model -f sample=0.05`). train 이 게이트에서 멈추고 promote 는 건너뛴다.

## 9. 증거

통과 · 탈락 · 롤백 세 실행의 화면과 링크, 승격 전후와 롤백 전후의 `/health` 응답을 모은다. 요건별로 무엇을 보여 줄지는 PLAN.md 의 요건 점검표에 있다.
