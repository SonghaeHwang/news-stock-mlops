"""학습 · 게이트 · parity 가 함께 쓰는 것: 학습표 읽기, 학습 / 평가 구간 나누기, 게이트 기준 읽기."""
import csv
import json
from pathlib import Path

import numpy as np
import yaml

GATE_FILE = Path(__file__).resolve().parent.parent / "config" / "gate.yml"


def load_gate(path: Path = GATE_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_table(art: Path) -> tuple[list[dict], dict]:
    """(정답이 있는 행, 메타). 정답이 없는 마지막 날의 행은 학습 · 평가에 쓰지 않는다."""
    meta = json.loads((art / "dataset_meta.json").read_text(encoding="utf-8"))
    with open(art / "dataset.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["label"] != ""]
    return rows, meta


def split(rows: list[dict], holdout_days: int) -> tuple[list[dict], list[dict]]:
    """시간순으로 나눈다. 마지막 holdout_days 개의 거래일이 평가 구간이다."""
    days = sorted({r["date"] for r in rows})
    cut = set(days[-holdout_days:])
    return [r for r in rows if r["date"] not in cut], [r for r in rows if r["date"] in cut]


def xy(rows: list[dict], features: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[float(r[f]) for f in features] for r in rows], dtype=np.float64).reshape(len(rows), len(features))
    y = np.array([int(r["label"]) for r in rows], dtype=np.int64)
    return x, y


def logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def onnx_proba(model: Path, x: np.ndarray) -> np.ndarray:
    """ONNX 모델이 답한 '오른다' 확률."""
    import onnxruntime as ort

    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    return sess.run(None, {sess.get_inputs()[0].name: x.astype(np.float32)})[1][:, 1]
