"""헤드라인 인정 규칙 (features/match.py). 실제로 수집된 제목에서 고른 사례들."""
import pytest

from collect.config import load_tickers
from features.match import classify, is_about

T = load_tickers()


def kinds(slug: str, title: str) -> set[str]:
    """그 제목에서 잡힌 언급 종류."""
    return {k for k, v in classify(title, T[slug]).items() if v}


@pytest.mark.parametrize(
    "slug, title, expected",
    [
        # 카카오 — 계열사만 나오면 계열사 언급, 카카오가 함께 나오면 둘 다
        ("kakao", "카카오뱅크, 3분기 순이익 역대 최대", {"affiliates"}),
        ("kakao", "카카오게임즈 '도깨비의세계', 게임대상 '우수상'", {"affiliates"}),
        ("kakao", "카카오, 공공혁신 리포트 발간", {"name"}),
        ("kakao", "카카오·카카오뱅크, 금융 서비스 개편", {"name", "affiliates"}),
        ("kakao", "오프라인 공연장 간 네카오…年 1조 콘서트 시장 잡아라", {"name"}),
        ("kakao", "김범수 창업자, 카카오톡 개편 직접 챙긴다", {"people", "products"}),
        ("kakao", "카카오닙스 건강 효과", set()),
        # 삼성전자
        ("samsung", "삼전 사내대출 시작…'반도체 벨트' 후끈", {"name"}),
        ("samsung", "삼성생명, 배당 확대", {"affiliates"}),
        ("samsung", "이재용 회장, 갤럭시 신제품 직접 소개", {"people", "products"}),
        ("samsung", "삼성 라이온즈, 한국시리즈 진출", set()),
        # SM — 다른 회사는 빼고, 아티스트만 나온 기사는 대표 상품 언급
        ("sm", "에스엠투네트웍스와 양해각서", set()),
        ("sm", "SM그룹, SM상선 매각 추진", set()),
        ("sm", "레드벨벳, 새 앨범 '코스믹' 첫 티저 이미지 공개", {"products"}),
        ("sm", "SM엔터 3분기 영업이익 증가", {"name"}),
        ("sm", "SM C&C, 광고 사업 확대", {"affiliates"}),
        # 영문 짧은 말은 단어로 떨어져 있을 때만
        ("apple", "Macron visits Berlin", set()),
        ("apple", "New Mac lineup announced", {"products"}),
        ("apple", "Best apple pie recipes", set()),
        ("nvidia", "Jensen Huang unveils Rubin at Nvidia keynote", {"name", "people", "products"}),
    ],
)
def test_classify(slug, title, expected):
    assert kinds(slug, title) == expected
    assert is_about(title, T[slug]) is bool(expected)
