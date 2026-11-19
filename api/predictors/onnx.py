"""ONNX 모델로 답한다. scikit-learn 없이 onnxruntime 만 쓴다.

model.json(모델 카드)에서 특징 목록 · 종목 순서 · 종목별 평소 건수를 읽는다.
카드의 특징 목록이 이 이미지의 features/build.py 와 다르면 띄우지 않는다
(학습과 서빙의 특징이 어긋난 모델을 서비스하지 않는다 → 서버는 health 실패로 보고 이전 버전으로 돌아간다).
"""
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

from features.build import names


class OnnxPredictor:
    def __init__(self, model_dir: Path):
        card = json.loads((model_dir / "model.json").read_text(encoding="utf-8"))
        if card["features"] != names(card["slugs"]):
            raise RuntimeError(f"모델 {card['version']} 의 특징 목록이 이 이미지의 특징 계산과 다르다")
        self.version: str = card["version"]
        self.slugs: list[str] = card["slugs"]
        self._base: dict[str, float] = card["base"]
        self._sess = ort.InferenceSession(str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
        self._input = self._sess.get_inputs()[0].name

    def base(self, slug: str, counts: dict[str, int]) -> float | None:
        """그 종목의 평소 건수 (학습 때 계산해 카드에 적어 둔 값). 모델이 배우지 않은 종목이면 None."""
        return self._base.get(slug)

    def prob_up(self, vector: list[float]) -> float:
        x = np.array([vector], dtype=np.float32)
        return float(self._sess.run(None, {self._input: x})[1][0, 1])
