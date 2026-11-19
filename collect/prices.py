"""종목 · 지수의 일별 종가를 받는다.

    python -m collect.prices --out data            → data/prices/<코드>.csv
    python -m collect.prices --out data --start 2022-01-01

매번 전체 기간을 다시 받아 덮어쓴다 (한 코드에 1천 행 남짓이라 가볍다).
"""
import argparse
import sys
from pathlib import Path

import FinanceDataReader as fdr

from collect.config import load_tickers, price_codes

DEFAULT_START = "2021-12-01"  # 헤드라인 시작(2022-01)보다 조금 앞에서 — 첫 거래일의 전일 종가가 필요하다


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data")
    p.add_argument("--start", default=DEFAULT_START)
    args = p.parse_args()

    out = Path(args.out) / "prices"
    out.mkdir(parents=True, exist_ok=True)
    failed = []
    for code in price_codes(load_tickers()):
        try:
            df = fdr.DataReader(code, args.start)
        except Exception as e:  # 받아오는 곳(거래소 · 포털)마다 오류 모양이 달라 넓게 잡는다
            print(f"{code}: 실패 — {e!r}")
            failed.append(code)
            continue
        if df.empty:
            print(f"{code}: 빈 결과")
            failed.append(code)
            continue
        df = df[["Close"]].rename_axis("date").rename(columns={"Close": "close"})
        df.index = df.index.strftime("%Y-%m-%d")
        df.to_csv(out / f"{code}.csv")
        print(f"{code}: {len(df)}행  {df.index[0]} ~ {df.index[-1]}")
    if failed:
        sys.exit(f"주가를 받지 못한 코드: {', '.join(failed)}")


if __name__ == "__main__":
    main()
