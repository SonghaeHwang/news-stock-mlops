"""헤드라인을 Google 뉴스 RSS 에서 하루 단위로 받는다.

    python -m collect.news --start 2023-01-01                 과거 전체 (어제까지)
    python -m collect.news --start 2026-10-01 --end 2026-10-31 --ticker kakao
    python -m collect.news --days 3 --out data/incoming       최근 3일만 (매일 도는 수집)

저장: <out>/news/<슬러그>/<YYYY-MM>.jsonl   한 줄에 {date, published, title, source}
      <out>/news/<슬러그>/_done.txt         조회를 끝낸 날 — 다시 치면 이 날들은 건너뛴다

- 최근 날짜부터 과거로 내려간다. 중간에 막혀도 최근 구간은 다섯 종목이 다 채워져 있다.
- 걸러내지 않고 그대로 저장한다. 이 종목 기사인지는 특징 단계가 tickers.yml 로 판단한다.
- date 는 그 시장의 현지 날짜다 (한국 종목은 KST, 미국 종목은 미국 동부).
- 429 · 503 을 받으면 기다렸다 다시 하고, 세 번 실패하면 멈춘다 (종료 코드 1).
"""
import argparse
import datetime as dt
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect.config import load_tickers

RSS = "https://news.google.com/rss/search"
PAUSE = (1.0, 2.0)  # 조회 사이에 쉬는 시간(초) 범위
BACKOFF = (60, 180, 420)  # 막혔을 때 기다리는 시간(초)


class Blocked(Exception):
    """기다려도 계속 막힌다."""


def fetch(query: str, hl: str, gl: str) -> bytes:
    """RSS 한 번 조회. 막히면 기다렸다 다시 하고, 끝까지 안 되면 Blocked."""
    url = RSS + "?" + urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl}"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for wait in (*BACKOFF, None):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
            reason = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            reason = repr(e)
        if wait is None:
            raise Blocked(reason)
        print(f"  {reason} — {wait}초 기다린다", flush=True)
        time.sleep(wait)
    raise Blocked("unreachable")


def parse(xml: bytes, tz: ZoneInfo) -> list[dict]:
    """RSS → [{date, published, title, source}]. 제목 끝의 ' - 매체' 는 떼어 낸다."""
    rows = []
    for item in ET.fromstring(xml).iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        pub = item.findtext("pubDate")
        if not title or not pub:
            continue
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        when = parsedate_to_datetime(pub)
        rows.append(
            {
                "date": when.astimezone(tz).strftime("%Y-%m-%d"),
                "published": when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": title,
                "source": source,
            }
        )
    return rows


class Store:
    """한 종목의 저장 폴더. 같은 (제목, 매체)는 한 번만 쓴다."""

    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.done_file = folder / "_done.txt"
        self.done = set(self.done_file.read_text(encoding="utf-8").split()) if self.done_file.exists() else set()
        self.seen: set[tuple[str, str]] = set()
        for f in folder.glob("*.jsonl"):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    self.seen.add((r["title"], r["source"]))

    def add(self, rows: list[dict]) -> int:
        new = 0
        for r in rows:
            key = (r["title"], r["source"])
            if key in self.seen:
                continue
            self.seen.add(key)
            with open(self.folder / f"{r['date'][:7]}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            new += 1
        return new

    def mark_done(self, day: str) -> None:
        self.done.add(day)
        with open(self.done_file, "a", encoding="utf-8") as fh:
            fh.write(day + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", help="YYYY-MM-DD")
    p.add_argument("--end", help="YYYY-MM-DD (기본: 어제)")
    p.add_argument("--days", type=int, help="오늘부터 거슬러 며칠 (start · end 대신, 이미 받은 날도 다시 조회)")
    p.add_argument("--ticker", help="한 종목만 (tickers.yml 의 슬러그)")
    p.add_argument("--out", default="data")
    args = p.parse_args()

    today = dt.date.today()
    if args.days:
        end, start, redo = today, today - dt.timedelta(days=args.days - 1), True
    elif args.start:
        start = dt.date.fromisoformat(args.start)
        end = dt.date.fromisoformat(args.end) if args.end else today - dt.timedelta(days=1)
        redo = False
    else:
        p.error("--start 또는 --days 가 필요하다")

    tickers = load_tickers()
    if args.ticker:
        if args.ticker not in tickers:
            sys.exit(f"모르는 종목: {args.ticker} (가능: {', '.join(tickers)})")
        tickers = {args.ticker: tickers[args.ticker]}
    stores = {slug: Store(Path(args.out) / "news" / slug) for slug in tickers}

    days = [end - dt.timedelta(days=i) for i in range((end - start).days + 1)]  # 최근 → 과거
    todo = sum(1 for d in days for s in stores.values() if redo or d.isoformat() not in s.done)
    print(f"{start} ~ {end}, 종목 {len(tickers)}개, 조회 {todo}회 예정", flush=True)

    queries = added = 0
    try:
        for day in days:
            for slug, t in tickers.items():
                store = stores[slug]
                if not redo and day.isoformat() in store.done:
                    continue
                q = f"{t['news']['query']} after:{day} before:{day + dt.timedelta(days=1)}"
                rows = parse(fetch(q, t["news"]["hl"], t["news"]["gl"]), ZoneInfo(t["timezone"]))
                added += store.add(rows)
                store.mark_done(day.isoformat())
                queries += 1
                if queries % 50 == 0:
                    print(f"  {queries}/{todo}회, 새 헤드라인 {added}건, 지금 {day}", flush=True)
                time.sleep(random.uniform(*PAUSE))
    except Blocked as e:
        sys.exit(f"막혔다 ({e}). {queries}/{todo}회에서 멈춤 — 나중에 같은 명령을 다시 치면 이어서 받는다")
    print(f"끝: 조회 {queries}회, 새 헤드라인 {added}건", flush=True)


if __name__ == "__main__":
    main()
