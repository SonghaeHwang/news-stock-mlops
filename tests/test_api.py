"""API: 응답 모양, 모르는 종목, 빈 헤드라인, 학습 쪽 특징과 API 쪽 특징이 같은지, ONNX 모델로 답하는지."""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

from api.app import create_app
from collect.config import load_tickers
from features.build import names, vector
from features.daily import load_lexicon, summarize

T = load_tickers()
LEX = load_lexicon()
SLUGS = list(T)
HEADLINES = ["카카오 먹통 사태, 김범수 국감 출석", "카카오톡 장애 복구 지연", "카카오뱅크 3분기 순이익 최대", "오늘의 날씨"]
BASE = 2.0


@pytest.fixture()
def rule(tmp_path):
    return TestClient(create_app(str(tmp_path)))  # 빈 폴더 → 모델이 없다


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """작은 모델을 학습해 서버가 받는 두 파일(model.onnx, model.json)을 만든다."""
    d = tmp_path_factory.mktemp("m")
    n = len(names(SLUGS))
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, n))
    y = (x[:, 0] + rng.normal(scale=0.5, size=200) > 0).astype(int)
    model = make_pipeline(StandardScaler(), LogisticRegression()).fit(x, y)
    onx = convert_sklearn(model, initial_types=[("x", FloatTensorType([None, n]))],
                          options={id(model.steps[-1][1]): {"zipmap": False}})
    (d / "model.onnx").write_bytes(onx.SerializeToString())
    card = {"version": "m20261119-1", "features": names(SLUGS), "slugs": SLUGS, "base": {"kakao": BASE}}
    (d / "model.json").write_text(json.dumps(card), encoding="utf-8")
    return d, model


def test_health_without_model_answers_as_rule(rule):
    body = rule.get("/health").json()
    assert body == {"status": "ok", "app_version": "dev", "model_version": "rule"}


def test_predict_shape_without_model(rule):
    r = rule.post("/predict", json={"ticker": "kakao", "headlines": HEADLINES, "date": "2022-10-17"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"ticker", "prob_up", "model_version", "counts", "features"}
    assert body["prob_up"] == 0.5 and body["model_version"] == "rule"
    assert body["counts"]["n"] == 3 and body["counts"]["n_affiliates"] == 1   # 날씨 기사는 세지 않는다


def test_unknown_ticker_is_404(rule):
    assert rule.post("/predict", json={"ticker": "apple", "headlines": ["애플 신제품"]}).status_code == 404


def test_empty_headlines(rule):
    body = rule.post("/predict", json={"ticker": "kakao", "headlines": []}).json()
    assert body["counts"]["n"] == 0 and body["features"]["none"] == 1.0


def test_tickers(rule):
    body = rule.get("/tickers").json()
    assert list(body) == SLUGS and body["kakao"]["code"] == "035720"


def test_features_match_training_side(trained):
    """같은 헤드라인 묶음 → 학습이 쓰는 함수로 만든 특징 = API 가 응답에 적은 특징."""
    d, _ = trained
    body = TestClient(create_app(str(d))).post(
        "/predict", json={"ticker": "kakao", "headlines": HEADLINES, "date": "2022-10-17"}).json()
    want = vector(summarize(HEADLINES, T["kakao"], LEX), BASE, 0, "kakao", SLUGS)   # 2022-10-17 은 월요일
    assert body["features"] == dict(zip(names(SLUGS), want))


def test_onnx_answer_equals_sklearn(trained):
    d, model = trained
    client = TestClient(create_app(str(d)))
    assert client.get("/health").json()["model_version"] == "m20261119-1"
    body = client.post("/predict", json={"ticker": "kakao", "headlines": HEADLINES, "date": "2022-10-17"}).json()
    want = model.predict_proba(np.array([list(body["features"].values())]))[0, 1]
    assert body["model_version"] == "m20261119-1"
    assert abs(body["prob_up"] - want) < 1e-4


def test_weekend_counts_as_friday(trained):
    d, _ = trained
    body = TestClient(create_app(str(d))).post(
        "/predict", json={"ticker": "kakao", "headlines": HEADLINES, "date": "2022-10-15"}).json()   # 토요일
    assert body["features"]["dow_4"] == 1.0


def test_ticker_the_model_did_not_learn_is_422(trained):
    d, _ = trained
    r = TestClient(create_app(str(d))).post("/predict", json={"ticker": "samsung", "headlines": ["삼성전자 실적"]})
    assert r.status_code == 422


def test_model_with_other_features_does_not_load(trained, tmp_path):
    d, _ = trained
    card = json.loads((d / "model.json").read_text(encoding="utf-8"))
    card["features"] = card["features"][1:]
    (tmp_path / "model.json").write_text(json.dumps(card), encoding="utf-8")
    (tmp_path / "model.onnx").write_bytes((d / "model.onnx").read_bytes())
    with pytest.raises(RuntimeError):
        create_app(str(tmp_path))
