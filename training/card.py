"""모델 카드 model.json 을 쓴다. 서버는 model.onnx 와 이 파일 두 개만 받는다.

    python -m training.card --art artifacts

버전 이름은 m<날짜>-<GitHub Actions 실행 번호> 다 (로컬에서는 m<날짜>-local). --version 으로 직접 줄 수도 있다.

API 가 특징을 만들 때 필요한 것(특징 목록, 종목 순서, 종목별 평소 건수 base)과
이 모델이 무엇으로 만들어졌는지(데이터 기간, 행 수, 점수, 게이트 · parity 결과, 데이터의 커밋)를 적는다.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--art", default="artifacts")
    p.add_argument("--version", default="")
    args = p.parse_args()
    art = Path(args.art)
    read = lambda name: json.loads((art / name).read_text(encoding="utf-8"))
    meta, metrics = read("dataset_meta.json"), read("metrics.json")
    now = dt.datetime.now(dt.timezone.utc)
    card = {
        "version": args.version or f"m{now:%Y%m%d}-{os.environ.get('GITHUB_RUN_NUMBER', 'local')}",
        "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": git_sha(),
        "features": meta["features"],
        "slugs": meta["slugs"],
        "base": meta["base"],
        "metrics": metrics,
        "gate": read("gate.json"),
        "parity": read("parity.json"),
    }
    (art / "model.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{art / 'model.json'}: {card['version']} (커밋 {card['commit']})")


if __name__ == "__main__":
    main()
