"""건수 요약(features/daily.py)과 학습표(training/dataset.py)."""
import datetime as dt

from collect.config import load_tickers
from features.build import names, vector
from features.daily import COLUMNS, load_lexicon, summarize
from training.dataset import build_rows

T = load_tickers()
LEX = load_lexicon()
SLUGS = list(T)


def counts(n: int) -> dict:
    return {**dict.fromkeys(COLUMNS, 0), "n": n, "n_name": n, "n_titles": n}


def calendar(start: str, days: int, n: int = 10) -> dict:
    d0 = dt.date.fromisoformat(start)
    return {(d0 + dt.timedelta(days=k)).isoformat(): counts(n) for k in range(days)}


def test_summarize_counts_same_title_once():
    c = summarize(
        ["카카오, 먹통 사태 사과", "카카오 먹통 사태 사과", "카카오뱅크 3분기 순이익 최대", "오늘의 날씨"],
        T["kakao"], LEX,
    )
    assert c["n"] == 3            # 날씨 기사는 인정하지 않는다
    assert c["n_titles"] == 2     # 쉼표만 다른 두 제목은 한 제목이다
    assert c["n_name"] == 2 and c["n_affiliates"] == 1
    assert c["n_neg"] == 1 and c["n_pos"] == 1   # 먹통 / 최대


def test_vector_matches_names():
    v = vector(counts(10), 5.0, 0, "kakao", SLUGS)
    assert len(v) == len(names(SLUGS))
    row = dict(zip(names(SLUGS), v))
    assert row["vol"] > 0 and row["ticker_kakao"] == 1.0 and row["dow_0"] == 1.0 and row["none"] == 0.0


def prices(days: list[str], step: float) -> dict:
    return {d: 100.0 * (1 + step) ** i for i, d in enumerate(days)}


# 2026-11-02(월) ~ 11-13(금), 평일만 거래일
TRADING = [d.isoformat() for d in (dt.date(2026, 11, 2) + dt.timedelta(days=k) for k in range(12)) if d.weekday() < 5]


def test_weekend_goes_to_friday_and_last_row_has_no_label():
    daily = calendar("2026-11-02", 12, n=10)
    daily["2026-11-07"] = counts(100)   # 토요일
    rows, base = build_rows("kakao", daily, prices(TRADING, 0.01), prices(TRADING, 0.0), SLUGS)
    by_date = {r["date"]: r for r in rows}
    assert "2026-11-07" not in by_date
    assert by_date["2026-11-09"]["n"] == 10               # 월요일 행에는 월요일 것만
    assert by_date["2026-11-13"]["label"] == ""           # 다음 거래일이 없으면 정답이 없다
    # 앞의 행이 5개 있어야 행을 만든다 → 11/2 ~ 11/6 은 평소 건수를 재는 데만 쓰인다
    assert min(by_date) == "2026-11-09" and base == 10


def test_friday_row_includes_weekend():
    daily = calendar("2026-10-26", 19, n=10)             # 한 주 더 앞에서 시작
    daily["2026-11-07"] = counts(100)
    days = [d.isoformat() for d in (dt.date(2026, 10, 26) + dt.timedelta(days=k) for k in range(19)) if d.weekday() < 5]
    rows, _ = build_rows("kakao", daily, prices(days, 0.01), prices(days, 0.0), SLUGS)
    friday = next(r for r in rows if r["date"] == "2026-11-06")
    assert friday["n"] == 10 + 100 + 10                   # 금 + 토 + 일


def test_label_is_relative_to_benchmark():
    daily = calendar("2026-10-26", 19)
    days = [d.isoformat() for d in (dt.date(2026, 10, 26) + dt.timedelta(days=k) for k in range(19)) if d.weekday() < 5]
    up, more = prices(days, 0.01), prices(days, 0.02)
    beat, _ = build_rows("kakao", daily, more, up, SLUGS)     # 종목이 지수보다 더 올랐다
    lose, _ = build_rows("kakao", daily, up, more, SLUGS)     # 종목도 올랐지만 지수가 더 올랐다
    assert {r["label"] for r in beat if r["label"] != ""} == {1}
    assert {r["label"] for r in lose if r["label"] != ""} == {0}


def test_uncovered_day_drops_the_row():
    daily = calendar("2026-10-26", 19)
    del daily["2026-11-08"]                               # 일요일을 받지 않았다 → 금요일(11/6) 행을 만들지 않는다
    days = [d.isoformat() for d in (dt.date(2026, 10, 26) + dt.timedelta(days=k) for k in range(19)) if d.weekday() < 5]
    rows, _ = build_rows("kakao", daily, prices(days, 0.01), prices(days, 0.0), SLUGS)
    assert "2026-11-06" not in {r["date"] for r in rows}
    assert "2026-11-09" in {r["date"] for r in rows}
