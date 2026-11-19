"""예측기를 고른다. MODEL_DIR 에 model.onnx 와 model.json 이 있으면 onnx, 없으면 rule.

모델은 이미지에 굽지 않는다. 서버는 /srv/news/models/<버전>/ 을 컨테이너에 붙이고 MODEL_DIR 로 그 폴더를 가리킨다.
"""
import os
from pathlib import Path

from api.predictors.rule import RulePredictor


def load(model_dir: str | Path | None = None):
    d = Path(model_dir or os.environ.get("MODEL_DIR", "artifacts"))
    if (d / "model.onnx").exists() and (d / "model.json").exists():
        from api.predictors.onnx import OnnxPredictor

        return OnnxPredictor(d)
    return RulePredictor()
