"""파일 이름의 종목과 내용이 어긋난 엑셀을 가려내는가 (collect/bigkinds.py)."""
from collect.bigkinds import wrong_ticker


def test_제목에_종목이_거의_없으면_잘못_붙인_이름으로_본다():
    assert wrong_ticker(3436, 135)       # 카카오 파일을 삼성전자로 읽었을 때 (3.9%)
    assert wrong_ticker(4311, 0)


def test_정상_파일은_통과한다():
    assert not wrong_ticker(4311, 1083)  # 카카오 2025-11 (25%)
    assert not wrong_ticker(3476, 654)   # 가장 낮았던 달 (19%)


def test_작은_파일은_검사하지_않는다():
    assert not wrong_ticker(99, 0)
    assert not wrong_ticker(0, 0)
