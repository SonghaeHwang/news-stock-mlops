"""엑셀을 넣는 폴더를 지켜보다가 새 파일이 들어오면 `task data:submit` 을 실행한다.

    python -m collect.watch            (멈출 때는 Ctrl+C)

- 30초마다 폴더의 엑셀 목록(이름 · 크기 · 수정 시각)을 본다.
- 목록이 바뀌었고, 다음 번에 봤을 때도 그대로면(내려받기가 끝났으면) 실행한다.
- 실행이 실패해도 멈추지 않는다. 고친 뒤 파일을 다시 넣거나 `task data:submit` 을 직접 치면 된다.
"""
import argparse
import datetime as dt
import subprocess
import time
from pathlib import Path


def snapshot(raw: Path) -> dict[str, tuple[int, int]]:
    return {f.name: (f.stat().st_size, int(f.stat().st_mtime)) for f in raw.glob("*.xlsx")}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", default="data/raw/bigkinds")
    p.add_argument("--every", type=int, default=30)
    args = p.parse_args()
    raw = Path(args.raw)
    raw.mkdir(parents=True, exist_ok=True)
    done = snapshot(raw)  # 켤 때 이미 있던 파일은 건너뛴다 (그것들은 `task data:submit` 으로 직접 넣는다)
    last = done
    print(f"{raw} 를 지켜본다 ({args.every}초마다, 지금 {len(done)}개)", flush=True)
    while True:
        time.sleep(args.every)
        now = snapshot(raw)
        if now != done and now == last:
            changed = sorted(k for k in now if done.get(k) != now[k])
            print(f"[{dt.datetime.now():%H:%M:%S}] 새 파일 {changed} → task data:submit", flush=True)
            code = subprocess.run("task data:submit", shell=True).returncode
            print(f"[{dt.datetime.now():%H:%M:%S}] {'끝났다' if code == 0 else f'실패했다 (종료 코드 {code})'}", flush=True)
            done = now
        last = now


if __name__ == "__main__":
    main()
