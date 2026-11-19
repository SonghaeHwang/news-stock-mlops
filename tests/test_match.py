"""헤드라인 인정 규칙 (features/match.py). 실제로 수집된 제목에서 고른 사례들."""
import pytest

from collect.config import load_tickers
from features.match import classify, is_about

T = load_tickers()


@pytest.mark.parametrize(
    "slug, title, expected",
    [
        # 카카오 계열사만 나오면 뺀다. 카카오가 함께 나오면 인정한다
        ("kakao", "카카오뱅크, 3분기 순이익 역대 최대", False),
        ("kakao", "카카오게임즈 '도깨비의세계', 게임대상 '우수상'", False),
        ("kakao", "카카오페이 주가 급등", False),
        ("kakao", "카카오, 공공혁신 리포트 발간", True),
        ("kakao", "카카오·카카오뱅크, 금융 서비스 개편", True),
        ("kakao", "오프라인 공연장 간 네카오…年 1조 콘서트 시장 잡아라", True),
        ("kakao", "카카오닙스 건강 효과", False),
        # 삼성전자
        ("samsung", "삼전 사내대출 시작…'반도체 벨트' 후끈", True),
        ("samsung", "삼성생명, 배당 확대", False),
        # SM — 다른 회사는 빼고, 아티스트만 나온 기사는 인정한다
        ("sm", "에스엠투네트웍스와 양해각서", False),
        ("sm", "SM그룹, SM상선 매각 추진", False),
        ("sm", "레드벨벳, 새 앨범 '코스믹' 첫 티저 이미지 공개", True),
        # 영문 짧은 말은 단어로 떨어져 있을 때만
        ("apple", "Macron visits Berlin", False),
        ("apple", "New Mac lineup announced", True),
        ("apple", "Best apple pie recipes", False),
    ],
)
def test_is_about(slug, title, expected):
    assert is_about(title, T[slug]) is expected


def test_kinds_are_counted_separately():
    """기업명 · 대표 · 대표 상품은 서로 다른 특징이다."""
    assert classify("레드벨벳, 새 앨범 첫 티저 공개", T["sm"]) == {"name": False, "people": False, "products": True}
    assert classify("SM엔터 3분기 영업이익 증가", T["sm"]) == {"name": True, "people": False, "products": False}
    assert classify("이재용 회장, 갤럭시 신제품 직접 소개", T["samsung"]) == {"name": False, "people": True, "products": True}
