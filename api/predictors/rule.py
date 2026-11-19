"""기준선. 모델 파일이 없을 때 쓴다 — 헤드라인을 보지 않고 늘 0.5 로 답한다."""


class RulePredictor:
    version = "rule"
    slugs = None  # 종목 순서를 정해 둔 모델이 없다 → API 가 tickers.yml 의 순서를 쓴다

    def base(self, slug: str, counts: dict[str, int]) -> float | None:
        """평소 건수를 모른다 → 오늘 건수를 평소로 본다 (vol 특징이 0 이 된다)."""
        return float(counts["n_titles"])

    def prob_up(self, vector: list[float]) -> float:
        return 0.5
