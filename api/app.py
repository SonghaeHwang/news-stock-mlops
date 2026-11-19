"""헤드라인을 받아 "다음 거래일에 그 종목이 시장보다 오를 확률"을 돌려준다.

    GET  /health    {status, app_version, model_version}
    POST /predict   {ticker, headlines[], date?} → {ticker, prob_up, model_version, counts, features}
    GET  /tickers   지원 종목과 별칭

특징은 학습과 같은 함수(features/daily.summarize → features/build.vector)로 만든다.
APP_VERSION 은 이미지를 만들 때, MODEL_DIR 은 서버가 띄울 때 정한다 — 코드와 모델은 따로 배포된다.
"""
import datetime as dt
import os
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api import predictors
from collect.config import load_tickers
from features.build import names, vector
from features.daily import load_lexicon, summarize


class PredictIn(BaseModel):
    ticker: str
    headlines: list[str]
    date: dt.date | None = None  # 헤드라인의 날짜. 없으면 그 시장의 오늘


def create_app(model_dir: str | None = None) -> FastAPI:
    tickers = load_tickers()
    lexicon = load_lexicon()
    predictor = predictors.load(model_dir)
    app = FastAPI(title="news-stock-mlops")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app_version": os.environ.get("APP_VERSION", "dev"), "model_version": predictor.version}

    @app.get("/tickers")
    def list_tickers() -> dict:
        return {slug: {"name": t["name"], "code": t["code"], "market": t["market"], "aliases": t["match"]}
                for slug, t in tickers.items()}

    @app.post("/predict")
    def predict(body: PredictIn) -> dict:
        t = tickers.get(body.ticker)
        if t is None:
            raise HTTPException(404, f"모르는 종목이다: {body.ticker} (지원: {', '.join(tickers)})")
        counts = summarize(body.headlines, t, lexicon)
        base = predictor.base(body.ticker, counts)
        if base is None:
            raise HTTPException(422, f"모델 {predictor.version} 은 {body.ticker} 를 배우지 않았다")
        day = body.date or dt.datetime.now(ZoneInfo(t["timezone"])).date()
        weekday = min(day.weekday(), 4)  # 토 · 일 기사는 직전 거래일(금요일) 행에 묶인다 (DESIGN 2.2)
        slugs = predictor.slugs or list(tickers)
        x = vector(counts, base, weekday, body.ticker, slugs)
        return {"ticker": body.ticker, "prob_up": predictor.prob_up(x), "model_version": predictor.version,
                "counts": counts, "features": dict(zip(names(slugs), x))}

    return app


app = create_app()
