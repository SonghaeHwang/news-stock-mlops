"""버킷과 서버 사이의 일: 데이터 적재, 현재 모델 받기, 모델 승격 · 롤백. 서버의 러너만 부른다.

    python3 deploy/lightsail/models.py store <dataset 폴더>      날짜별 건수 요약을 버킷에 올린다
    python3 deploy/lightsail/models.py current <받을 폴더>       지금 서비스 중인 모델을 받는다 (게이트의 비교 대상)
    python3 deploy/lightsail/models.py promote <학습 결과 폴더>  새 버전을 올리고 서비스한다
    python3 deploy/lightsail/models.py rollback <버전>           버킷에 있는 버전으로 되돌린다
    python3 deploy/lightsail/models.py list                      버킷의 버전 목록과 포인터

버킷 구조 (s3://<MODEL_BUCKET>/)
    data/dataset/<종목>.csv        학습에 쓴 날짜별 건수 요약
    models/<버전>/model.onnx       버전마다 폴더 하나 — 한 번 올리면 고치지 않는다
    models/<버전>/model.json       모델 카드
    models/current.json            포인터 — 지금 서비스 중인 버전

접근 키는 없다. 서버는 버킷의 "리소스 액세스"로 aws 명령을 쓴다. GitHub 러너는 버킷에 닿지 않고 artifact 로 주고받는다.
환경 변수: MODEL_BUCKET (저장소 변수), GITHUB_RUN_ID (Actions 가 넣는다).
Amazon Linux 2023 의 python3(3.9)과 aws CLI 만으로 돈다.
"""
import datetime
import json
import os
import re
import subprocess
import sys

SRV = "/srv/news"
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("model.onnx", "model.json")
VERSION = re.compile(r"m[0-9]{8}-[0-9]+")  # m<날짜>-<실행 번호>


def s3(path: str = "") -> str:
    bucket = os.environ.get("MODEL_BUCKET")
    if not bucket:
        sys.exit("MODEL_BUCKET 이 없다 (저장소 변수)")
    return f"s3://{bucket}/{path}"


def aws(*args, stdin="", check=True):
    """`aws s3 <args>`. check=False 는 "없다"도 정상인 조회에 쓴다."""
    r = subprocess.run(["aws", "s3", *args], input=stdin, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"aws s3 {' '.join(args)} 실패\n{r.stderr}")
    return r


def check_version(ver: str) -> None:
    """버전 이름이 버킷 경로와 명령 인자에 들어가므로 모양부터 본다."""
    if not VERSION.fullmatch(ver):
        sys.exit(f"모델 버전 형식이 아니다: {ver!r} (예: m20261121-3)")


def pointer() -> dict:
    """포인터의 내용. 아직 없으면(첫 승격 전) 빈 dict."""
    r = aws("cp", s3("models/current.json"), "-", check=False)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def go_live(ver: str) -> None:
    """버킷의 버전을 서버로 받아 띄우고, 뜬 것을 확인한 뒤에 포인터를 바꾼다.

    server.sh 가 실패하면 서버는 이전 버전으로 돌아가 있고 포인터는 그대로다.
    """
    before = pointer().get("version")
    for f in FILES:
        aws("cp", s3(f"models/{ver}/{f}"), f"{SRV}/models/{ver}/{f}")
    if subprocess.run(["bash", os.path.join(HERE, "server.sh"), "model", ver]).returncode:
        sys.exit(f"{ver} 이 뜨지 않았다 — 서버는 이전 버전으로 돌아갔고 포인터는 그대로다")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = {"version": ver, "previous": before, "set_at": now, "run": os.environ.get("GITHUB_RUN_ID", "")}
    aws("cp", "-", s3("models/current.json"), stdin=json.dumps(new))
    print(f"포인터: {before or '(없음)'} → {ver}")


def store(src: str) -> None:
    aws("sync", src, s3("data/dataset/"), "--exclude", "*", "--include", "*.csv")
    n = len(aws("ls", s3("data/dataset/")).stdout.splitlines())
    print(f"{s3('data/dataset/')}: 파일 {n}개")


def current(out: str) -> None:
    ver = pointer().get("version")
    if not ver:
        print("현재 모델이 없다 (첫 승격 전) — 게이트는 현재 모델 검사를 건너뛴다")
        return
    check_version(ver)
    os.makedirs(out, exist_ok=True)
    for f in FILES:
        aws("cp", s3(f"models/{ver}/{f}"), os.path.join(out, f))
    print(f"현재 모델 {ver} → {out}")


def promote(src: str) -> None:
    """학습 결과를 새 버전으로 올리고 서비스한다. 아래 경우에는 아무것도 바꾸지 않고 멈춘다.

    - 카드에 게이트 통과 · parity 통과가 적혀 있지 않다 (앞 Job 이 멈췄어야 하지만 여기서 한 번 더 본다)
    - 이 실행보다 나중에 시작한 실행(예: 학습 중의 롤백)이 이미 포인터를 바꿨다
    - 그 버전이 버킷에 이미 있다
    """
    with open(os.path.join(src, "model.json"), encoding="utf-8") as f:
        card = json.load(f)
    ver = card["version"]
    check_version(ver)
    if not card.get("gate", {}).get("passed"):
        sys.exit(f"{ver}: 게이트를 통과하지 않은 모델이다 — 승격하지 않는다")
    parity = card.get("parity", {})
    if not parity or parity["max_diff"] > parity["limit"]:
        sys.exit(f"{ver}: parity 를 통과하지 않은 모델이다 — 승격하지 않는다")
    me = int(os.environ.get("GITHUB_RUN_ID") or 0)
    if me and int(pointer().get("run") or 0) > me:
        sys.exit("이 실행보다 나중에 시작한 실행이 포인터를 바꿨다 — 낡은 실행이라 승격하지 않는다")
    if aws("ls", s3(f"models/{ver}/"), check=False).returncode == 0:
        sys.exit(f"{ver} 은 이미 버킷에 있다 — 한 번 올린 버전은 고치지 않는다")
    for f in FILES:
        aws("cp", os.path.join(src, f), s3(f"models/{ver}/{f}"))
    go_live(ver)


def rollback(ver: str) -> None:
    """버킷에 이미 있는 버전으로 되돌린다. 학습 · 검사는 하지 않는다. 이미지는 건드리지 않는다."""
    check_version(ver)
    if aws("ls", s3(f"models/{ver}/model.onnx"), check=False).returncode:
        sys.exit(f"{ver} 이 버킷에 없다 — `task deploy:status` 로 버전 목록을 본다")
    go_live(ver)


def versions() -> None:
    if not os.environ.get("MODEL_BUCKET"):
        print("MODEL_BUCKET 이 없다 — 버킷의 버전 목록은 건너뛴다")
        return
    p = pointer()
    names = re.findall(r"PRE (m[0-9]{8}-[0-9]+)/", aws("ls", s3("models/"), check=False).stdout)
    print(f"포인터: {p.get('version') or '(없음)'}  이전: {p.get('previous') or '(없음)'}  바꾼 때: {p.get('set_at') or '-'}")
    for n in names:
        print(("* " if n == p.get("version") else "  ") + n)


COMMANDS = {"store": store, "current": current, "promote": promote, "rollback": rollback}

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv == ["list"]:
        versions()
    elif len(argv) == 2 and argv[0] in COMMANDS:
        COMMANDS[argv[0]](argv[1])
    else:
        sys.exit(__doc__)
