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
        # HBM · 파운드리는 기업명이 함께 있을 때만 대표 상품으로 센다
        ("samsung", "SK하이닉스, HBM 공급 확대", set()),
        ("samsung", "TSMC 파운드리 점유율 70% 돌파", set()),
        ("samsung", "삼성전자, HBM4 아닌 HBM 공급 확대", {"name", "products"}),
        ("samsung", "삼성 파운드리, 2나노 수주", {"name", "products"}),
        ("samsung", "이재용 회장, 파운드리 라인 점검", {"people"}),
        # SM — 다른 회사는 빼고, 아티스트만 나온 기사는 대표 상품 언급
        ("sm", "에스엠투네트웍스와 양해각서", set()),
        ("sm", "SM그룹, SM상선 매각 추진", set()),
        ("sm", "레드벨벳, 새 앨범 '코스믹' 첫 티저 이미지 공개", {"products"}),
        ("sm", "SM엔터 3분기 영업이익 증가", {"name"}),
        ("sm", "SM C&C, 광고 사업 확대", {"affiliates"}),
        # 줄임말 · 추가한 대표와 아티스트
        ("kakao", "카겜, 신작 출시 연기", {"affiliates"}),
        ("kakao", "남궁훈 대표 사퇴…'먹통 사태' 책임", {"people"}),
        ("samsung", "경계현 사장 \"메모리 감산 없다\"", {"people"}),
        ("sm", "슈퍼주니어, 데뷔 20주년 콘서트", {"products"}),
        ("sm", "하츠투하츠, 첫 미니앨범 발매", {"products"}),
        # 아티스트 이름이 다른 말 속에 들어 있는 경우는 인정하지 않는다
        ("sm", "3분기 어닝 서프라이즈 기록한 반도체주", set()),
        ("sm", "엑소좀 치료제 임상 진입", set()),
        # 하이브 — "하이브리드"는 빼고, 레이블은 계열사로 센다
        ("hybe", "하이브, 2분기 역대 최대 실적", {"name"}),
        ("hybe", "하이브리드 차량 판매 급증", set()),
        ("hybe", "방시혁 의장, BTS 완전체 컴백 예고", {"people", "products"}),
        ("hybe", "어도어, 뉴진스 전속계약 소송", {"products", "affiliates"}),
        ("hybe", "민희진 \"경영권 찬탈 계획 없었다\"", {"people"}),
        # 박지원 · 최태원은 기업명이 함께 있을 때만 대표로 센다
        ("hybe", "하이브 박지원 대표 사임", {"name", "people"}),
        ("hybe", "박지원 의원, 국정감사 발언", set()),
        ("skhynix", "최태원 회장, SK하이닉스 이천 캠퍼스 방문", {"name", "people"}),
        ("skhynix", "최태원 회장, 대한상의 신년 인사회 참석", set()),
        # 영문 짧은 말은 단어로 떨어져 있을 때만
        ("hybe", "TXT, 월드투어 개최", {"products"}),
        ("hybe", "CONTEXT 2026 콘퍼런스 개막", set()),
        # SK하이닉스 — HBM · D램은 기업명이 함께 있을 때만
        ("skhynix", "SK하이닉스, HBM 공급 확대", {"name", "products"}),
        ("skhynix", "삼성전자, HBM 공급 확대", set()),
        ("skhynix", "'하닉' 주가 사상 최고가", {"name"}),
        ("skhynix", "곽노정 사장 \"AI 수요는 상수\"", {"people"}),
        ("skhynix", "솔리다임, 기업용 SSD 신제품 공개", {"affiliates"}),
    ],
)
def test_classify(slug, title, expected):
    assert kinds(slug, title) == expected
    assert is_about(title, T[slug]) is bool(expected)
