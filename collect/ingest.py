"""새로 들어온 빅카인즈 엑셀을 찾아 변환하고, 학습표 원본(dataset/)을 다시 만든다.

    python -m collect.ingest                 새 파일만 변환 → dataset/<슬러그>.csv 갱신
    python -m collect.ingest --rebuild       data/news 를 지우고 모든 엑셀을 다시 변환 (인정 규칙을 바꿨을 때)

넣는 곳: data/raw/bigkinds/<슬러그>_<시작일>-<끝일>.xlsx     (예: kakao_20261101-20261130.xlsx)
만드는 것
    data/news/<슬러그>/<YYYY-MM>.jsonl   제목 원문. 깃에 올리지 않는다 (한 종목 한 달이 1MB 남짓)
    dataset/<슬러그>.csv                 날짜별 건수 요약 (features/daily.py). 제목은 들어 있지 않다. 깃에 올린다
    dataset/_files.csv                   변환한 파일 목록. 무엇이 새 파일인지는 이 목록으로 가린다

- 새 파일: 목록에 없거나, 이름은 같은데 크기 · 수정 시각이 달라진 파일 (같은 달을 다시 내려받은 경우).
- 받은 기간: 파일 이름의 시작일 ~ 끝일. 단 끝일이 내려받은 날 이후면 내려받은 전날까지만 받은 것으로 본다.
  받은 기간 안에서 기사가 없는 날은 0건으로 적는다. 받지 않은 날은 적지 않는다 (0건과 구분한다).
- dataset/ 은 매번 data/news 전체에서 다시 만든다. 어휘 사전을 바꾸면 다음 실행에 반영된다.
"""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

from collect.bigkinds import convert_file
from collect.config import load_tickers
from features.daily import COLUMNS, load_lexicon, summarize

NAME = re.compile(r"(?P<slug>[a-z0-9]+)_(?P<start>\d{8})-(?P<end>\d{8})\.xlsx")
FIELDS = ("file", "slug", "start", "end", "size", "mtime", "rows", "saved")


def _day(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y%m%d").date()


def read_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["file"]: r for r in csv.DictReader(f)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", default="data/raw/bigkinds")
    p.add_argument("--data", default="data")
    p.add_argument("--dataset", default="dataset")
    p.add_argument("--rebuild", action="store_true")
    args = p.parse_args()
    raw, data, dataset = Path(args.raw), Path(args.data), Path(args.dataset)
    tickers = {s: t for s, t in load_tickers().items() if "bigkinds" in t}
    lexicon = load_lexicon()
    dataset.mkdir(parents=True, exist_ok=True)
    manifest = {} if args.rebuild else read_manifest(dataset / "_files.csv")
    if args.rebuild:
        for slug in tickers:
            shutil.rmtree(data / "news" / slug, ignore_errors=True)

    new = 0
    for f in sorted(raw.glob("*.xlsx")):
        m = NAME.fullmatch(f.name)
        if not m or m["slug"] not in tickers:
            sys.exit(f"{f.name}: 파일 이름은 <슬러그>_<시작일>-<끝일>.xlsx 여야 한다 (슬러그: {', '.join(tickers)})")
        st = f.stat()
        old = manifest.get(f.name)
        if old and int(old["size"]) == st.st_size and int(old["mtime"]) == int(st.st_mtime):
            continue
        rows, saved, had, unrelated = convert_file(f, data, tickers)
        # 내려받은 날의 기사는 아직 다 올라오지 않았다 → 전날까지만 받은 것으로 본다
        end = min(_day(m["end"]), dt.date.fromtimestamp(st.st_mtime) - dt.timedelta(days=1))
        manifest[f.name] = dict(file=f.name, slug=m["slug"], start=_day(m["start"]).isoformat(), end=end.isoformat(),
                                size=st.st_size, mtime=int(st.st_mtime), rows=rows, saved=saved)
        print(f"새 파일 {f.name}: {rows}행 중 {saved}건 저장 (이미 있음 {had}, 제목에 없음 {unrelated})")
        new += 1

    with open(dataset / "_files.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(manifest[k] for k in sorted(manifest))

    for slug, t in tickers.items():
        covered: set[dt.date] = set()
        for r in manifest.values():
            if r["slug"] == slug:
                d, end = dt.date.fromisoformat(r["start"]), dt.date.fromisoformat(r["end"])
                while d <= end:
                    covered.add(d)
                    d += dt.timedelta(days=1)
        titles: dict[str, list[str]] = {}
        for j in sorted((data / "news" / slug).glob("*.jsonl")):
            with open(j, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    titles.setdefault(r["date"], []).append(r["title"])
        out = dataset / f"{slug}.csv"
        if not covered:
            out.unlink(missing_ok=True)
            continue
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(("date", *COLUMNS))
            for d in sorted(covered):
                c = summarize(titles.get(d.isoformat(), []), t, lexicon)
                w.writerow((d.isoformat(), *(c[k] for k in COLUMNS)))
        print(f"{slug:<10}{len(covered):>6}일  {min(covered)} ~ {max(covered)}")
    print(f"새 파일 {new}개" if new else "새 파일이 없다")


if __name__ == "__main__":
    main()
