#!/usr/bin/env python3
"""用真实的 mihomo 加载规则集，核对加载条数与文件条数一致。

mihomo 遇到解析不了的条目只打一行 warning 就跳过，整表照常加载、不报错：
`*kw*` 通配、写错 behavior 的裸 CIDR、没有 ASN 库的 IP-ASN 都是这样丢的。
静态校验只能覆盖已知的坑，这里直接问内核：起一个只挂规则集的 mihomo，
从 /providers/rules 读 ruleCount，少于文件去重条数就是被丢了。

查的范围：custom/mihomo（自产，丢条即失败），aethersailor/rule 与
sukkaw/mihomo（镜像，丢条只告警）。metacubex 的 mihomo 产物由上游用
mihomo 自己生成，不在此列。

    python3 scripts/loadcheck.py                  # 全部
    python3 scripts/loadcheck.py --only-custom    # 只查 custom/
    python3 scripts/loadcheck.py --require        # 找不到 mihomo 时失败（CI 用）

几处实现细节都是踩出来的：
- mihomo 对 file 规则集用 fsnotify 监听所在目录，同目录上千个文件会耗尽句柄，
  所以每个文件复制进单独目录再挂；路径还必须在 SAFE_PATHS 之内。
- behavior 按内容判断，不按路径猜：sukkaw 的 ip/cdn.txt 是 classical，
  ip/china_ip.txt 却是裸 CIDR。
- IP-ASN 要 ASN.mmdb，事先下载；下载失败时不把 IP-ASN 计入期望条数。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ASN_URL = (
    "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/"
    "GeoLite2-ASN.mmdb"
)

CIDR = re.compile(r"^[0-9A-Fa-f.:]+/\d{1,3}$")
TYPED = re.compile(r"^[A-Z][A-Z0-9-]*,")
FORMAT = {".yaml": "yaml", ".txt": "text", ".list": "text", ".mrs": "mrs"}


def entries(f: Path) -> list[str]:
    """文件里的条目（yaml 取 payload 项，text 取非注释行）。"""
    out = []
    for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if f.suffix == ".yaml":
            if not line.startswith("- "):
                continue
            line = line[2:].strip().strip("'\"")
        out.append(line)
    return out


def behavior_of(items: list[str]) -> str:
    if items and all(CIDR.fullmatch(i) for i in items):
        return "ipcidr"
    if items and all(TYPED.match(i) for i in items):
        return "classical"
    return "domain"


def targets(only_custom: bool) -> list[tuple[Path, bool]]:
    """(文件, 是否自产)。"""
    out = [(f, True) for f in sorted((DIST / "custom" / "mihomo").glob("*"))]
    if not only_custom:
        out += [(f, False) for f in sorted((DIST / "aethersailor" / "rule").rglob("*"))]
        out += [(f, False) for f in sorted((DIST / "sukkaw" / "mihomo").rglob("*"))]
    return [(f, own) for f, own in out if f.is_file() and f.suffix in FORMAT]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch_asn(home: Path) -> bool:
    try:
        with urllib.request.urlopen(ASN_URL, timeout=60) as r:
            (home / "ASN.mmdb").write_bytes(r.read())
        return True
    except Exception as e:  # 网络问题不应让整个检查失败
        print(f"  ASN.mmdb 下载失败，IP-ASN 不计入期望条数: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-custom", action="store_true")
    ap.add_argument("--require", action="store_true", help="找不到 mihomo 时失败")
    a = ap.parse_args()

    mihomo = shutil.which("mihomo")
    if not mihomo:
        print("未找到 mihomo，跳过加载检查", file=sys.stderr)
        return 1 if a.require else 0

    files = targets(a.only_custom)
    if not files:
        print("没有需要加载检查的文件")
        return 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        home, iso = tmp / "home", tmp / "iso"
        home.mkdir()
        has_asn = fetch_asn(home)

        provs: dict[str, tuple[Path, bool, str, int | None]] = {}
        for i, (f, own) in enumerate(files):
            rel = f.relative_to(DIST)
            if f.suffix == ".mrs":
                # mrs 读不出条目，与同名 yaml 比；behavior 也取自 yaml
                twin = f.with_suffix(".yaml")
                if not twin.is_file():
                    continue
                items = entries(twin)
            else:
                items = entries(f)
            beh = behavior_of(items)
            want = {i for i in items if has_asn or not i.startswith("IP-ASN,")}
            d = iso / str(i)
            d.mkdir(parents=True)
            shutil.copy(f, d / f.name)
            provs[f"p{i}"] = (rel, own, beh, len(want))

        port = free_port()
        cfg = [
            "mixed-port: 0",
            f"external-controller: 127.0.0.1:{port}",
            "log-level: warning",
            "rule-providers:",
        ]
        for k, (rel, _, beh, _) in provs.items():
            path = iso / k[1:] / rel.name
            fmt = FORMAT[rel.suffix]
            cfg.append(
                f"  {k}: {{type: file, behavior: {beh}, format: {fmt}, path: '{path}'}}"
            )
        cfg += ["rules:"] + [f"  - RULE-SET,{k},DIRECT" for k in provs]
        cfg.append("  - MATCH,DIRECT")
        (home / "config.yaml").write_text("\n".join(cfg) + "\n", encoding="utf-8")

        log_path = tmp / "mihomo.log"
        with log_path.open("w") as log:
            proc = subprocess.Popen(
                [mihomo, "-d", str(home)],
                stdout=log,
                stderr=subprocess.STDOUT,
                env=dict(os.environ, SAFE_PATHS=str(iso)),
            )
            try:
                got = wait_loaded(port, len(provs), proc)
            finally:
                proc.terminate()
                proc.wait()
        warns = [
            line
            for line in log_path.read_text(errors="replace").splitlines()
            if "level=warning" in line or "level=error" in line
        ]

    if got is None:
        print("mihomo 未能启动或加载超时:", file=sys.stderr)
        for w in warns[:10]:
            print(f"  {w}", file=sys.stderr)
        return 1

    errors, warnings = [], []
    for k, (rel, own, beh, want) in provs.items():
        n = got.get(k, {}).get("ruleCount", 0)
        # 多于去重条数是上游有重复行，不算问题
        if n < want:
            msg = f"{rel}（按 {beh} 加载）{want} 条只加载了 {n} 条"
            (errors if own else warnings).append(msg)

    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "警告: "
    for w in warnings:
        print(f"{prefix}{w}", file=sys.stderr)
    if errors:
        print("加载检查失败:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    if warnings or errors:
        print("mihomo 日志摘录:", file=sys.stderr)
        for w in warns[:10]:
            print(f"  {w}", file=sys.stderr)
    if errors:
        return 1
    print(f"加载检查通过：{len(provs)} 个规则集由 mihomo 实际加载，条数一致")
    return 0


def wait_loaded(port: int, total: int, proc: subprocess.Popen) -> dict | None:
    """轮询 /providers/rules 直到全部规则集都加载过。"""
    url = f"http://127.0.0.1:{port}/providers/rules"
    for _ in range(240):
        if proc.poll() is not None:
            return None
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                provs = json.load(r)["providers"]
        except Exception:
            continue
        if len(provs) >= total and all(
            not p.get("updatedAt", "").startswith("0001") for p in provs.values()
        ):
            return provs
    return None


if __name__ == "__main__":
    raise SystemExit(main())
