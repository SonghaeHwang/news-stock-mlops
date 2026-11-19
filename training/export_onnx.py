"""학습한 모델을 ONNX 로 바꾼다. API 는 scikit-learn 없이 이 파일만 읽는다.

    python -m training.export_onnx --art artifacts      → model.onnx
"""
import argparse
from pathlib import Path

import joblib
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--art", default="artifacts")
    args = p.parse_args()
    art = Path(args.art)
    model = joblib.load(art / "model.joblib")
    n = model.steps[0][1].n_features_in_
    onx = convert_sklearn(model, initial_types=[("x", FloatTensorType([None, n]))],
                          options={id(model.steps[-1][1]): {"zipmap": False}})  # 확률을 배열로 받는다
    (art / "model.onnx").write_bytes(onx.SerializeToString())
    print(f"{art / 'model.onnx'}: 입력 {n}개")


if __name__ == "__main__":
    main()
