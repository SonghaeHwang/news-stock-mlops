"""헤드라인 묶음 → 건수 요약. 학습표 원본(dataset/)을 만들 때와 API 가 함께 쓴다.

    n             그 종목 기사로 인정된 제목 수 (features/match.py)
    n_name ...    기업명 · 대표 · 대표 상품 · 계열사가 언급된 제목 수 (겹칠 수 있다)
    n_titles      서로 다른 제목 수. 띄어쓰기 · 문장 부호 · 대소문자를 지운 뒤 같으면 한 제목으로 본다
                  → n / n_titles 가 "같은 기사가 얼마나 퍼졌는가" 다
    n_pos, n_neg  호재 / 악재 낱말(config/lexicon.yml)이 들어 있는 서로 다른 제목 수
"""
import re
from pathlib import Path

import yaml

from features.match import KINDS, classify

COLUMNS = ("n", *(f"n_{k}" for k in KINDS), "n_titles", "n_pos", "n_neg")
LEXICON_FILE = Path(__file__).resolve().parent.parent / "config" / "lexicon.yml"


def load_lexicon(path: Path = LEXICON_FILE) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {k: [w.lower() for w in raw[k]] for k in ("positive", "negative")}


def norm_title(title: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", title.lower())


def summarize(titles: list[str], t: dict, lexicon: dict[str, list[str]]) -> dict[str, int]:
    out = dict.fromkeys(COLUMNS, 0)
    unique: dict[str, str] = {}
    for title in titles:
        kinds = classify(title, t)
        if not any(kinds.values()):
            continue
        out["n"] += 1
        for k in KINDS:
            out[f"n_{k}"] += kinds[k]
        unique.setdefault(norm_title(title), title.lower())
    out["n_titles"] = len(unique)
    for low in unique.values():
        out["n_pos"] += any(w in low for w in lexicon["positive"])
        out["n_neg"] += any(w in low for w in lexicon["negative"])
    return out


def add(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    return {c: a[c] + b[c] for c in COLUMNS}
