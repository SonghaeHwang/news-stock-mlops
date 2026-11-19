"""건수 요약 → 모델 입력. 학습(training/dataset.py)과 API 가 같은 함수를 쓴다.

건수를 그대로 쓰지 않는다 (기사 수는 시기 · 종목마다 기준이 다르다).
    vol      서로 다른 제목 수가 그 종목의 평소(직전 20거래일 중앙값 base)의 몇 배인가, 로그
    repeat   제목 하나가 평균 몇 번 실렸는가 (n / n_titles)
    share_*  인정된 제목 중 기업명 · 대표 · 대표 상품 · 계열사가 언급된 비율
    share_pos, share_neg   서로 다른 제목 중 호재 / 악재 낱말이 든 비율
    none     기사가 한 건도 없는 날
    dow_*    요일 (월 0 ~ 금 4),  ticker_*  종목
"""
import math

from features.match import KINDS


def names(slugs: list[str]) -> list[str]:
    return ["vol", "repeat", *(f"share_{k}" for k in KINDS), "share_pos", "share_neg", "none",
            *(f"dow_{i}" for i in range(5)), *(f"ticker_{s}" for s in slugs)]


def vector(c: dict[str, int], base: float, weekday: int, slug: str, slugs: list[str]) -> list[float]:
    n, u = c["n"], c["n_titles"]
    return [
        math.log((u + 1) / (base + 1)),
        n / u if u else 1.0,
        *(c[f"n_{k}"] / n if n else 0.0 for k in KINDS),
        c["n_pos"] / u if u else 0.0,
        c["n_neg"] / u if u else 0.0,
        float(n == 0),
        *(float(weekday == i) for i in range(5)),
        *(float(slug == s) for s in slugs),
    ]
