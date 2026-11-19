"""헤드라인이 어떤 종목의 무엇을 언급하는지 가린다. 수집 검사 · 학습 · API 가 함께 쓴다.

규칙 (config/tickers.yml 의 한 종목 설정 t 에 대해)
1. 계열사(affiliates)가 제목에 있는지 본다.
2. affiliates 와 exclude 의 말을 제목에서 지운다. 긴 말부터 지운다.
   → "카카오뱅크" 만 있는 제목은 남는 "카카오" 가 없어 기업명 언급이 아니고 계열사 언급만 된다.
     "카카오·카카오뱅크" 처럼 둘 다 있는 제목은 기업명 언급이면서 계열사 언급이다.
3. 남은 제목에서 세 가지를 따로 본다.
   people    대표 · 창업자
   products  대표 상품 · 서비스 · 아티스트
   name      기업명 (match 의 정규식). 대표 상품의 말까지 지운 뒤에 본다
             → "카카오톡 개편" 은 대표 상품 언급이지 기업명 언급이 아니다.
4. 넷(name · people · products · affiliates) 중 하나라도 있으면 그 종목 기사로 인정한다.
   넷은 서로 다른 특징으로 센다.

영문 · 숫자로만 된 말(Mac, NCT, RTX)은 앞뒤가 영문 · 숫자가 아닐 때만 인정한다 (Macron, machine 을 막는다).
"""
import re

KINDS = ("name", "people", "products", "affiliates")


def _has(term: str, text: str) -> bool:
    if term.isascii():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return term.lower() in text.lower()


def _strip(title: str, terms: list[str]) -> str:
    for x in sorted(terms, key=len, reverse=True):
        title = re.sub(re.escape(x), " ", title, flags=re.IGNORECASE)
    return title


def strip_excluded(title: str, t: dict) -> str:
    """affiliates 와 exclude 의 말을 지운 제목."""
    return _strip(title, [*t.get("affiliates", []), *t.get("exclude", [])])


def classify(title: str, t: dict) -> dict[str, bool]:
    """{"name": 기업명, "people": 대표, "products": 대표 상품, "affiliates": 계열사} 언급 여부"""
    rest = strip_excluded(title, t)
    return {
        "name": any(re.search(pat, _strip(rest, t.get("products", [])), re.IGNORECASE) for pat in t["match"]),
        "people": any(_has(x, rest) for x in t.get("people", [])),
        "products": any(_has(x, rest) for x in t.get("products", [])),
        "affiliates": any(_has(x, title) for x in t.get("affiliates", [])),
    }


def is_about(title: str, t: dict) -> bool:
    """이 헤드라인을 그 종목 기사로 인정하는가."""
    return any(classify(title, t).values())
