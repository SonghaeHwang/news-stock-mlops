"""헤드라인이 나온 날을 기준으로 전날 · 당일 · 다음 날의 주가를 비교한다 (모델과 따로 보는 분석).

    python -m analysis.event --dataset dataset --prices data/prices

- 한 건: (종목, 거래일 T). T 하루의 기사만 본다 (학습표와 달리 주말 기사를 묶지 않는다). 기사가 MIN_TITLES 건 이상인 날만.
- 수익률(D) = D 의 종가 / 직전 거래일 종가 − 1 에서 같은 기간 비교 지수의 수익률을 뺀 것.
- 방향 표: 평균 수익률과 오른 날의 비율.
- 크기 표: |수익률| 이 그 종목 평소(전체 기간 평균)의 몇 배인가. 종목마다 변동 폭이 달라서 배수로 본다.
- 휴장일 표: 주말 · 공휴일에 나온 기사를 묶어, 휴장 전 거래일 · 다음 거래일 · 그 다음을 본다.

호재 / 악재 낱말(config/lexicon.yml)에는 "급락 · 상승" 처럼 주가 움직임을 전하는 낱말이 들어 있다.
당일의 관계는 "뉴스가 주가를 움직였다" 가 아니라 "같이 움직였다" 까지만 말할 수 있다.
"""
import argparse
import datetime as dt
import statistics
from pathlib import Path

import numpy as np

from collect.config import load_tickers
from training.dataset import MIN_HISTORY, WINDOW, load_daily, load_prices

MIN_TITLES = 10
OFFSETS = (-2, -1, 0, 1, 2)
DAY_HEAD = ("이틀 전", "전날", "당일", "다음 날", "이틀 뒤")
GAP_HEAD = ("휴장 전 거래일", "다음 거래일", "그 다음")


def collect_events(dataset: Path, prices: Path) -> tuple[list[dict], list[dict]]:
    """(거래일 사건, 휴장일 사건). 사건마다 날짜별 수익률 r 과 그 종목의 평소 크기 scale."""
    days_ev, gap_ev = [], []
    for slug, t in load_tickers().items():
        px, bench = load_prices(prices, t["code"]), load_prices(prices, t["benchmark"])
        days = [d for d in sorted(px) if d in bench]
        ex = {days[i]: (px[days[i]] / px[days[i - 1]] - 1) - (bench[days[i]] / bench[days[i - 1]] - 1)
              for i in range(1, len(days))}
        scale = float(np.mean(np.abs(list(ex.values()))))
        daily = load_daily(dataset, slug)
        history = []
        for i, d in enumerate(days):
            c = daily.get(d)
            if c is None:
                continue
            around = [days[i + o] for o in OFFSETS] if 2 <= i < len(days) - 2 else []
            if around and all(x in ex for x in around) and len(history) >= MIN_HISTORY and c["n_titles"] >= MIN_TITLES:
                u, n = c["n_titles"], c["n"]
                days_ev.append({
                    "slug": slug, "date": d, "r": [ex[x] for x in around], "scale": scale,
                    "neg": c["n_neg"] / u, "pos": c["n_pos"] / u,
                    "vol": (u + 1) / (statistics.median(history[-WINDOW:]) + 1),
                    "name": c["n_name"] / n, "people": c["n_people"] / n, "products": c["n_products"] / n,
                })
            history.append(c["n_titles"])
            if 1 <= i < len(days) - 2:
                a, b = dt.date.fromisoformat(d), dt.date.fromisoformat(days[i + 1])
                gap = [(a + dt.timedelta(days=k)).isoformat() for k in range(1, (b - a).days)]
                if gap and all(g in daily for g in gap):
                    u = sum(daily[g]["n_titles"] for g in gap)
                    if u >= MIN_TITLES:
                        gap_ev.append({
                            "slug": slug, "date": gap[0], "r": [ex[d], ex[days[i + 1]], ex[days[i + 2]]],
                            "neg": sum(daily[g]["n_neg"] for g in gap) / u,
                            "pos": sum(daily[g]["n_pos"] for g in gap) / u,
                        })
    return days_ev, gap_ev


def header(cols: tuple[str, ...]) -> str:
    return " " * 36 + "".join(f"{c:>15}" for c in cols)


def direction(label: str, r: np.ndarray, error_col: int | None = None) -> str:
    """평균 수익률(오른 날 비율). error_col 을 주면 그 열의 95% 오차 범위를 덧붙인다."""
    if len(r) < 2:
        return f"  {label:<26}{len(r):>6}건  (너무 적다)"
    cells = "".join(f"{f'{r[:, j].mean():+.2%} ({np.mean(r[:, j] > 0):.0%})':>15}" for j in range(r.shape[1]))
    tail = ""
    if error_col is not None:
        tail = f"   ±{1.96 * r[:, error_col].std(ddof=1) / np.sqrt(len(r)):.2%}"
    return f"  {label:<26}{len(r):>6}건{cells}{tail}"


def size(label: str, r: np.ndarray, scale: np.ndarray) -> str:
    """움직인 폭이 평소의 몇 배인가."""
    if len(r) < 2:
        return f"  {label:<26}{len(r):>6}건  (너무 적다)"
    cells = "".join(f"{f'{(np.abs(r[:, j]) / scale).mean():.2f}배':>15}" for j in range(r.shape[1]))
    return f"  {label:<26}{len(r):>6}건{cells}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="dataset")
    p.add_argument("--prices", default="data/prices")
    args = p.parse_args()
    ev, gaps = collect_events(Path(args.dataset), Path(args.prices))
    if not ev:
        raise SystemExit("사건이 없다 — dataset/ 과 data/prices 를 확인한다")

    r = np.array([e["r"] for e in ev])
    scale = np.array([e["scale"] for e in ev])
    col = {k: np.array([e[k] for e in ev]) for k in ("slug", "neg", "pos", "vol", "name", "people", "products")}
    everything = np.ones(len(ev), dtype=bool)

    def top(kind: str, q: float = 0.9) -> np.ndarray:
        """종목마다 그 언급 비율이 상위 10% 인 날."""
        m = np.zeros(len(ev), dtype=bool)
        for slug in set(col["slug"]):
            ms = col["slug"] == slug
            m |= ms & (col[kind] >= np.quantile(col[kind][ms], q)) & (col[kind] > 0)
        return m

    print(f"거래일 {len(ev)}건 (기사 {MIN_TITLES}건 이상인 날), {ev[0]['date'][:4]} ~ {max(e['date'] for e in ev)}")

    print("\n[방향] 호재 · 악재 낱말이 많았던 날 — 평균 지수 대비 수익률 (오른 날 비율)")
    print(header(DAY_HEAD))
    print(direction("전체", r))
    for th in (0.2, 0.3, 0.5):
        print(direction(f"악재 낱말 {th:.0%} 이상", r[col["neg"] >= th]))
    for th in (0.2, 0.3, 0.5):
        print(direction(f"호재 낱말 {th:.0%} 이상", r[col["pos"] >= th]))

    print("\n[방향] 언급 유형별 (그 종목에서 언급 비율이 상위 10% 인 날)")
    print(header(DAY_HEAD))
    for kind, name in (("name", "기업명"), ("people", "대표"), ("products", "대표 상품")):
        print(direction(f"{name} 언급 상위 10%", r[top(kind)]))

    print("\n[크기] 움직인 폭이 그 종목 평소의 몇 배인가 (방향 무시, 1.00 = 평소)")
    print(header(DAY_HEAD))
    print(size("전체", r, scale))
    for th in (1.5, 2, 3):
        m = col["vol"] >= th
        print(size(f"기사가 평소의 {th}배 이상", r[m], scale[m]))
    for kind, name in (("name", "기업명"), ("people", "대표"), ("products", "대표 상품")):
        m = top(kind)
        print(size(f"{name} 언급 상위 10%", r[m], scale[m]))
    for kind, name in (("people", "대표"), ("products", "대표 상품")):
        m = top(kind) & (col["vol"] >= 2)
        print(size(f"{name} 언급 + 기사 2배", r[m], scale[m]))

    g = np.array([e["r"] for e in gaps])
    gneg, gpos = np.array([e["neg"] for e in gaps]), np.array([e["pos"] for e in gaps])
    print(f"\n[휴장일] 주말 · 공휴일에 나온 기사 {len(gaps)}건 — 시장이 닫혀 있어 다음 거래일에야 반응할 수 있다")
    print(header(GAP_HEAD) + "   다음 거래일의 오차 범위")
    print(direction("전체", g, 1))
    for th in (0.2, 0.3, 0.5):
        print(direction(f"악재 낱말 {th:.0%} 이상", g[gneg >= th], 1))
    for th in (0.2, 0.3, 0.5):
        print(direction(f"호재 낱말 {th:.0%} 이상", g[gpos >= th], 1))


if __name__ == "__main__":
    main()
