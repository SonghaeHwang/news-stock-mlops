"""빅카인즈에서 내려받은 엑셀을 헤드라인 파일로 바꾼다 (국내 종목). 기준은 docs/COLLECTION.md 6절.

    python -m collect.bigkinds query                    빅카인즈 검색창에 넣을 검색어를 보여 준다
    python -m collect.bigkinds convert                  data/raw/bigkinds/*.xlsx → data/news/<슬러그>/<YYYY-MM>.jsonl

원본: <raw>/<슬러그>_<시작일>-<끝일>.xlsx   빅카인즈가 준 그대로 둔다 (파일 이름의 앞부분이 종목이다)
저장: <out>/news/<슬러그>/<YYYY-MM>.jsonl   한 줄에 {date, published, title, source, id, flag}

- 검색은 제목 + 본문으로 한다. 그래서 본문이나 `기관` 항목에만 종목 이름이 있는 기사가 딸려 온다.
  변환할 때 **제목이 인정 규칙(features/match.py)을 통과한 행만** 저장한다. 나머지는 원본에만 남는다.
- 같은 기사인지는 뉴스 식별자(id)로만 본다. 같은 제목을 여러 매체가 실었거나 한 매체가 다시 올린 것은 모두 저장한다.
- 다시 돌려도 늘어나지 않는다 (이미 저장된 id 는 건너뛴다). 인정 규칙을 바꿨으면 data/news/<슬러그> 를 지우고 다시 돌린다.
"""
import argparse
import datetime as dt
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

from collect.config import load_tickers
from features.match import is_about

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
KST = ZoneInfo("Asia/Seoul")
NEEDED = ("뉴스 식별자", "일자", "언론사", "제목", "분석제외 여부")


def query(t: dict) -> str:
    """빅카인즈 검색어 — 기업명 낱말 + 대표 + 대표 상품을 OR 로 잇는다.

    bigkinds.unless 에 적은 낱말은 뒤의 말이 본문에 없을 때만 받는다: {카카오톡: 제보} → (…) OR (카카오톡 NOT 제보)
    """
    unless = t["bigkinds"].get("unless", {})
    terms = dict.fromkeys([*t["bigkinds"]["names"], *t.get("people", []), *t.get("products", [])])
    plain = " OR ".join(f'"{x}"' if " " in x else x for x in terms if x not in unless)
    if not unless:
        return plain
    return f"({plain})" + "".join(f" OR ({x} NOT {unless[x]})" for x in terms if x in unless)


def read_xlsx(path: Path) -> list[dict]:
    """첫 시트를 [{컬럼 이름: 값}] 으로 읽는다. 첫 행이 컬럼 이름이다."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.parse(z.open("xl/sharedStrings.xml")).getroot().findall(NS + "si"):
                shared.append("".join(x.text or "" for x in si.iter(NS + "t")))
        sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
        rows = []
        for row in ET.parse(z.open(sheet)).getroot().iter(NS + "row"):
            cells = {}
            for c in row.findall(NS + "c"):
                v = c.find(NS + "v")
                if c.get("t") == "s":
                    value = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    value = "".join(x.text or "" for x in c.iter(NS + "t"))
                else:
                    value = v.text if v is not None else ""
                cells[re.match(r"[A-Z]+", c.get("r")).group()] = value or ""
            rows.append(cells)
    if not rows:
        return []
    header = {col: name.strip() for col, name in rows[0].items()}
    missing = [n for n in NEEDED if n not in header.values()]
    if missing:
        sys.exit(f"{path.name}: 컬럼이 없다 {missing} — 빅카인즈 파일이 맞는가")
    return [{header[col]: v for col, v in r.items() if col in header} for r in rows[1:]]


def to_row(r: dict) -> dict:
    """빅카인즈 한 행 → 저장하는 한 줄."""
    news_id = r["뉴스 식별자"].strip()
    day = r["일자"].strip()
    when = dt.datetime.strptime(news_id.split(".")[1][:14], "%Y%m%d%H%M%S").replace(tzinfo=KST)
    return {
        "date": f"{day[:4]}-{day[4:6]}-{day[6:8]}",
        "published": when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title": " ".join(r["제목"].split()),
        "source": r["언론사"].strip(),
        "id": news_id,
        "flag": r.get("분석제외 여부", "").replace(" ", ""),
    }


def convert(raw: Path, out: Path, tickers: dict[str, dict]) -> None:
    files = sorted(raw.glob("*.xlsx"))
    if not files:
        sys.exit(f"{raw} 에 엑셀 파일이 없다")
    print(f"{'파일':<34}{'행':>7}{'저장':>7}{'이미 있음':>8}{'제목에 없음':>9}")
    for f in files:
        slug = f.stem.split("_")[0]
        if slug not in tickers or "bigkinds" not in tickers[slug]:
            sys.exit(f"{f.name}: 파일 이름이 <슬러그>_ 로 시작해야 한다 (빅카인즈로 받는 종목: "
                     f"{', '.join(s for s, t in tickers.items() if 'bigkinds' in t)})")
        folder = out / "news" / slug
        folder.mkdir(parents=True, exist_ok=True)
        seen = set()
        for j in folder.glob("*.jsonl"):
            with open(j, encoding="utf-8") as fh:
                seen.update(json.loads(line)["id"] for line in fh)
        rows = read_xlsx(f)
        saved = had = unrelated = 0
        for r in rows:
            row = to_row(r)
            if not is_about(row["title"], tickers[slug]):
                unrelated += 1  # 본문 · 기관 항목에만 종목 이름이 있는 기사
                continue
            if row["id"] in seen:
                had += 1
                continue
            seen.add(row["id"])
            with open(folder / f"{row['date'][:7]}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            saved += 1
        print(f"{f.name:<34}{len(rows):>7}{saved:>7}{had:>8}{unrelated:>9}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("query", help="빅카인즈 검색어를 보여 준다")
    c = sub.add_parser("convert", help="내려받은 엑셀을 헤드라인 파일로 바꾼다")
    c.add_argument("--raw", default="data/raw/bigkinds")
    c.add_argument("--out", default="data")
    args = p.parse_args()

    tickers = load_tickers()
    if args.cmd == "query":
        for slug, t in tickers.items():
            if "bigkinds" in t:
                print(f"[{slug}] {t['name']}\n{query(t)}\n")
    else:
        convert(Path(args.raw), Path(args.out), tickers)


if __name__ == "__main__":
    main()
