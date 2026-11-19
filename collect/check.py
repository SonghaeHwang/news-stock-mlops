"""수집분 검사. 문제가 있으면 종료 코드 1.

    python -m collect.check --dir data
    python -m collect.check --dir data/incoming

보는 것
- 종목 누락: tickers.yml 의 종목마다 헤드라인이 한 건 이상 있는가
- 중복: 같은 기사가 두 번 들어 있지 않은가 (빅카인즈의 뉴스 식별자로 본다)
- 날짜: date 가 YYYY-MM-DD 이고 미래가 아닌가
- 주가: 종목 · 지수의 종가 파일이 있고, 마지막 날짜가 7일 안쪽인가
인정 비율과 기업명 · 대표 · 대표 상품 · 계열사 언급 건수는 참고로 보여 준다 (실패 조건은 아니다).
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

from collect.config import load_tickers, price_codes
from features.match import KINDS, classify

STALE_DAYS = 7


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="data")
    args = p.parse_args()
    root = Path(args.dir)
    today = dt.date.today()
    tickers = load_tickers()
    problems: list[str] = []

    print(f"{'종목':<10}{'헤드라인':>8}{'인정':>7}{'기업명':>7}{'대표':>6}{'상품':>6}{'계열사':>6}  기간")
    for slug, t in tickers.items():
        rows, seen, dup = [], set(), 0
        for f in sorted((root / "news" / slug).glob("*.jsonl")):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    key = r["id"]  # 빅카인즈의 뉴스 식별자
                    dup += key in seen
                    seen.add(key)
                    rows.append(r)
        if not rows:
            problems.append(f"{slug}: 헤드라인이 없다")
            print(f"{slug:<10}{0:>8}")
            continue
        dates = sorted(r["date"] for r in rows)
        bad = [d for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or d > (today + dt.timedelta(days=1)).isoformat()]
        if bad:
            problems.append(f"{slug}: 이상한 날짜 {bad[:3]}")
        if dup:
            problems.append(f"{slug}: 중복 {dup}건")
        kinds = [classify(r["title"], t) for r in rows]
        about = sum(any(k.values()) for k in kinds)
        n = {kind: sum(k[kind] for k in kinds) for kind in KINDS}
        print(
            f"{slug:<10}{len(rows):>8}{about / len(rows):>7.0%}{n['name']:>7}{n['people']:>6}{n['products']:>6}{n['affiliates']:>6}"
            f"  {dates[0]} ~ {dates[-1]}"
        )

    for code in price_codes(tickers):
        f = root / "prices" / f"{code}.csv"
        if not f.exists():
            problems.append(f"주가 {code}: 파일이 없다")
            continue
        with open(f, encoding="utf-8") as fh:
            last = list(csv.DictReader(fh))[-1]["date"]
        if (today - dt.date.fromisoformat(last)).days > STALE_DAYS:
            problems.append(f"주가 {code}: 마지막 날짜가 오래됐다 ({last})")

    if problems:
        sys.exit("검사 실패\n- " + "\n- ".join(problems))
    print("검사 통과")


if __name__ == "__main__":
    main()
