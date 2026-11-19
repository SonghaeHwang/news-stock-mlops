"""학습한다. 마지막 60거래일은 떼어 두고 평가에만 쓴다.

    python -m training.train --art artifacts      → model.joblib, metrics.json

기준선: 학습 구간의 정답 비율로만 답하는 모델 (헤드라인을 보지 않는다).
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from training.common import load_gate, load_table, logloss, split, xy


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--art", default="artifacts")
    p.add_argument("--sample", type=float, default=1.0, help="학습 행의 일부만 쓴다 (게이트 탈락 시연용)")
    args = p.parse_args()
    art = Path(args.art)
    rows, meta = load_table(art)
    features = meta["features"]
    train, hold = split(rows, load_gate()["holdout_days"])
    if not train or not hold:
        raise SystemExit(f"행이 모자라다 (학습 {len(train)}, 평가 {len(hold)})")
    if args.sample < 1.0:
        train = train[: max(10, int(len(train) * args.sample))]
    xt, yt = xy(train, features)
    xh, yh = xy(hold, features)
    if len(set(yt)) < 2:
        raise SystemExit("학습 구간의 정답이 한 가지뿐이다")

    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
    model.fit(xt, yt)
    ph = model.predict_proba(xh)[:, 1]
    rate = float(yt.mean())
    metrics = {
        "rows": {"train": len(train), "holdout": len(hold),
                 "per_ticker": {s: sum(r["slug"] == s for r in train) for s in meta["slugs"]}},
        "period": {"train": [train[0]["date"], train[-1]["date"]], "holdout": [hold[0]["date"], hold[-1]["date"]]},
        "label_ratio": {"train": rate, "holdout": float(yh.mean())},
        "model": {"logloss": logloss(yh, ph), "accuracy": float(((ph > 0.5) == yh).mean()),
                  "auc": float(roc_auc_score(yh, ph)) if len(set(yh)) == 2 else None},
        "baseline": {"logloss": logloss(yh, np.full(len(yh), rate)), "accuracy": float(((rate > 0.5) == yh).mean())},
    }
    joblib.dump(model, art / "model.joblib")
    (art / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    m, b = metrics["model"], metrics["baseline"]
    print(f"학습 {len(train)}행 ({metrics['period']['train'][0]} ~ {metrics['period']['train'][1]}), "
          f"평가 {len(hold)}행 ({metrics['period']['holdout'][0]} ~ {metrics['period']['holdout'][1]})")
    print(f"모델   logloss {m['logloss']:.4f}  정확도 {m['accuracy']:.1%}  AUC {m['auc']}")
    print(f"기준선 logloss {b['logloss']:.4f}  정확도 {b['accuracy']:.1%}")


if __name__ == "__main__":
    main()
