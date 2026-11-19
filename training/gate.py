"""검증 게이트. 하나라도 걸리면 이유를 적고 종료 코드 1 — 그 뒤의 단계(ONNX · 배포)가 돌지 않는다.

    python -m training.gate --art artifacts [--current artifacts/current]

기준은 config/gate.yml.
1. 데이터: 종목마다 학습 행이 충분한가, 평가 행이 충분한가, 정답 비율이 한쪽으로 쏠리지 않았는가
2. 기준선: 평가 구간에서 모델의 logloss 가 기준선보다 나쁘지 않은가
3. 현재 모델: --current 폴더에 지금 서비스 중인 모델(model.onnx, model.json)이 있으면, 같은 평가 구간에서 그보다 나쁘지 않은가
   현재 모델이 없으면(첫 배포) 건너뛴다. 특징 목록이 달라졌으면 비교할 수 없으므로 건너뛰고 그 사실을 적는다.
"""
import argparse
import json
import sys
from pathlib import Path

from training.common import load_gate, load_table, logloss, onnx_proba, split, xy


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--art", default="artifacts")
    p.add_argument("--current", default="artifacts/current")
    args = p.parse_args()
    art, cur = Path(args.art), Path(args.current)
    gate = load_gate()
    metrics = json.loads((art / "metrics.json").read_text(encoding="utf-8"))
    problems, notes = [], []

    d = gate["data"]
    for slug, n in metrics["rows"]["per_ticker"].items():
        if n < d["min_rows_per_ticker"]:
            problems.append(f"데이터: {slug} 의 학습 행이 {n}개다 (기준 {d['min_rows_per_ticker']}개 이상)")
    if metrics["rows"]["holdout"] < d["min_holdout_rows"]:
        problems.append(f"데이터: 평가 행이 {metrics['rows']['holdout']}개다 (기준 {d['min_holdout_rows']}개 이상)")
    lo, hi = d["label_ratio"]
    for part, ratio in metrics["label_ratio"].items():
        if not lo <= ratio <= hi:
            problems.append(f"데이터: {part} 구간의 정답 1 비율이 {ratio:.0%} 다 (기준 {lo:.0%} ~ {hi:.0%})")

    m, b = metrics["model"]["logloss"], metrics["baseline"]["logloss"]
    limit = b + gate["baseline"]["max_logloss_over"]
    print(f"기준선 검사: 모델 {m:.4f}  기준선 {b:.4f}  (허용 {limit:.4f} 이하)")
    if m > limit:
        problems.append(f"기준선: 모델의 logloss {m:.4f} 가 기준선 {b:.4f} 보다 나쁘다")

    result = {"current": None}
    if (cur / "model.onnx").exists() and (cur / "model.json").exists():
        card = json.loads((cur / "model.json").read_text(encoding="utf-8"))
        rows, meta = load_table(art)
        if card["features"] != meta["features"]:
            notes.append(f"현재 모델({card['version']})과 특징 목록이 달라 비교하지 않았다")
        else:
            _, hold = split(rows, gate["holdout_days"])
            xh, yh = xy(hold, meta["features"])
            c = logloss(yh, onnx_proba(cur / "model.onnx", xh))
            limit = c + gate["current"]["max_logloss_over"]
            result["current"] = {"version": card["version"], "logloss": c}
            print(f"현재 모델 검사: 모델 {m:.4f}  현재({card['version']}) {c:.4f}  (허용 {limit:.4f} 이하)")
            if m > limit:
                problems.append(f"현재 모델: 새 모델의 logloss {m:.4f} 가 현재 모델 {card['version']} 의 {c:.4f} 보다 나쁘다")
    else:
        notes.append("현재 모델이 없다 (첫 배포) — 현재 모델 검사를 건너뛰었다")

    for n in notes:
        print("참고:", n)
    result.update(passed=not problems, problems=problems, notes=notes)
    (art / "gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if problems:
        sys.exit("게이트 탈락\n- " + "\n- ".join(problems))
    print("게이트 통과")


if __name__ == "__main__":
    main()
