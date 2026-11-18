"""config/tickers.yml 을 읽는다. 수집 · 특징 · API 가 함께 쓴다."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TICKERS_FILE = ROOT / "config" / "tickers.yml"


def load_tickers(path: Path = TICKERS_FILE) -> dict[str, dict]:
    """{슬러그: 설정} 을 돌려준다. 슬러그는 폴더 이름과 API 의 ticker 값으로 쓴다."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["tickers"]


def price_codes(tickers: dict[str, dict]) -> list[str]:
    """받아야 할 주가 코드 — 종목과 비교 지수, 중복 없이."""
    codes: list[str] = []
    for t in tickers.values():
        for code in (t["code"], t["benchmark"]):
            if code not in codes:
                codes.append(code)
    return codes
