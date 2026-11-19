"""scikit-learn 모델과 ONNX 모델이 같은 답을 내는지 본다. 다르면 종료 코드 1.

    python -m training.parity --art artifacts

학습에 쓴 모델과 서버가 읽는 파일이 다른 형식이므로, 변환이 답을 바꾸지 않았는지 배포 전에 확인한다.
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

from training.common import load_gate, load_table, onnx_proba, xy


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--art", default="artifacts")
    args = p.parse_args()
    art = Path(args.art)
    cfg = load_gate()["parity"]
    rows, meta = load_table(art)
    pick = np.random.default_rng(0).choice(len(rows), size=min(cfg["rows"], len(rows)), replace=False)
    x, _ = xy([rows[i] for i in sorted(pick)], meta["features"])
    a = joblib.load(art / "model.joblib").predict_proba(x)[:, 1]
    b = onnx_proba(art / "model.onnx", x)
    diff = float(np.max(np.abs(a - b)))
    (art / "parity.json").write_text(json.dumps({"rows": len(x), "max_diff": diff, "limit": cfg["max_diff"]}), encoding="utf-8")
    print(f"parity: {len(x)}행, 확률 차이 최대 {diff:.2e} (기준 {cfg['max_diff']:.0e} 이하)")
    if diff > cfg["max_diff"]:
        sys.exit("parity 실패 — ONNX 의 답이 scikit-learn 과 다르다")


if __name__ == "__main__":
    main()
