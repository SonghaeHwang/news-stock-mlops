"""학습표를 만든다: 날짜별 건수(dataset/) + 주가(data/prices) → 한 행이 (종목, 거래일 T).

    python -m training.dataset --dataset dataset --prices data/prices --out artifacts

- 입력: 날짜가 T 이상이고 다음 거래일 미만인 날의 건수를 더한다 (토 · 일 · 공휴일 기사는 직전 거래일에 묶인다).
  그 사이에 받지 않은 날이 하루라도 있으면 그 행은 만들지 않는다.
- 평소 건수 base: 그 종목의 직전 20개 행의 n_titles 중앙값. 앞의 행이 5개가 안 되면 그 행은 만들지 않는다.
- 정답: (T+1 종가 / T 종가 − 1) − (비교 지수의 같은 기간 수익률) > 0 이면 1. 다음 거래일이 아직 없으면 빈칸이다.
- 주가는 정답에만 쓴다.
"""
import argparse
import csv
import datetime as dt
import json
import statistics
from pathlib import Path

from collect.config import load_tickers
from features.build import names, vector
from features.daily import COLUMNS, add

WINDOW, MIN_HISTORY = 20, 5
ZERO = dict.fromkeys(COLUMNS, 0)


def load_daily(folder: Path, slug: str) -> dict[str, dict[str, int]]:
    f = folder / f"{slug}.csv"
    if not f.exists():
        return {}
    with open(f, encoding="utf-8", newline="") as fh:
        return {r["date"]: {c: int(r[c]) for c in COLUMNS} for r in csv.DictReader(fh)}


def load_prices(folder: Path, code: str) -> dict[str, float]:
    with open(folder / f"{code}.csv", encoding="utf-8", newline="") as fh:
        return {r["date"]: float(r["close"]) for r in csv.DictReader(fh)}


def build_rows(slug: str, daily: dict, px: dict, bench: dict, slugs: list[str]) -> tuple[list[dict], float | None]:
    """(행 목록, 가장 최근의 평소 건수). 행: slug, date, label, base, 건수들, 특징들."""
    days = sorted(px)
    feature_names = names(slugs)
    rows, history = [], []
    for i, t0 in enumerate(days):
        t1 = days[i + 1] if i + 1 < len(days) else None
        d = dt.date.fromisoformat(t0)
        end = dt.date.fromisoformat(t1) if t1 else d + dt.timedelta(days=1)
        span = [(d + dt.timedelta(days=k)).isoformat() for k in range((end - d).days)]
        if any(x not in daily for x in span):
            continue
        c = ZERO
        for x in span:
            c = add(c, daily[x])
        if len(history) >= MIN_HISTORY:
            base = statistics.median(history[-WINDOW:])
            label = ""
            if t1 and t0 in bench and t1 in bench:
                label = int((px[t1] / px[t0] - 1) - (bench[t1] / bench[t0] - 1) > 0)
            rows.append({"slug": slug, "date": t0, "label": label, "base": base, **c,
                         **dict(zip(feature_names, vector(c, base, d.weekday(), slug, slugs)))})
        history.append(c["n_titles"])
    return rows, (statistics.median(history[-WINDOW:]) if len(history) >= MIN_HISTORY else None)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="dataset")
    p.add_argument("--prices", default="data/prices")
    p.add_argument("--out", default="artifacts")
    args = p.parse_args()
    tickers = load_tickers()
    slugs = list(tickers)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, base = [], {}
    print(f"{'종목':<10}{'행':>6}{'정답 있음':>8}{'정답 1':>8}{'평소 건수':>8}  기간")
    for slug, t in tickers.items():
        r, b = build_rows(slug, load_daily(Path(args.dataset), slug), load_prices(Path(args.prices), t["code"]),
                          load_prices(Path(args.prices), t["benchmark"]), slugs)
        labeled = [x for x in r if x["label"] != ""]
        ratio = f"{sum(x['label'] for x in labeled) / len(labeled):.0%}" if labeled else "-"
        period = f"{r[0]['date']} ~ {r[-1]['date']}" if r else "-"
        print(f"{slug:<10}{len(r):>6}{len(labeled):>8}{ratio:>8}{b if b is not None else '-':>8}  {period}")
        rows += r
        if b is not None:
            base[slug] = b
    rows.sort(key=lambda x: (x["date"], x["slug"]))
    fields = ["slug", "date", "label", "base", *COLUMNS, *names(slugs)]
    with open(out / "dataset.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    meta = {"slugs": slugs, "features": names(slugs), "base": base}
    (out / "dataset_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out / 'dataset.csv'}: {len(rows)}행")


if __name__ == "__main__":
    main()
