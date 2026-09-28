#!/usr/bin/env python3
"""用 Surge 自己的解析器复核所有 Surge 会读的规则（仅限装了 Surge 的 Mac）。

Surge 加载规则集时遇到不认的行只打一行 warning 跳过，不报错。verify.py 的
surge_line_problem() 是按 surge-cli --check 实测结果写的白名单，Surge 升级后
可能漂移；这个脚本直接问 Surge：把每条规则展开成 profile 里的内联规则，
用 `surge-cli --check` 检查，出错就记下并剔除那一行，循环到全部通过。

    python3 scripts/surgecheck.py

CI 跑不了（Surge 只有 macOS 应用），改了转换逻辑或 Surge 升级后在本地跑一次。
自产文件（metacubex/*/surge、custom/surge、aethersailor/rule-surge）有问题
返回非零；镜像只列出来。
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
CLI = "/Applications/Surge.app/Contents/Applications/surge-cli"
CHUNK = 50000  # --check 只报第一处错误，分块让每轮重查的量小一些
LINE_NO = re.compile(r"第 (\d+) 行")
HEADER_LINES = 2  # [General] 与 [Rule]


def surge_files() -> tuple[list[Path], list[Path]]:
    """(RULE-SET 文件, DOMAIN-SET 文件)。"""
    rule = [
        *DIST.glob("metacubex/*/surge/*.conf"),
        *DIST.glob("custom/surge/*.conf"),
        *DIST.glob("sukkaw/surge/non_ip/*.conf"),
        *DIST.glob("sukkaw/surge/ip/*.conf"),
        # Aethersailor 的镜像 .list 按 mihomo 写法，Surge 引用的是转换后的 rule-surge/
        *DIST.glob("aethersailor/rule-surge/**/*.list"),
    ]
    domainset = list(DIST.glob("sukkaw/surge/domainset/*.conf"))
    return sorted(rule), sorted(domainset)


def inline(line: str) -> str:
    """规则集行 TYPE,VALUE[,参数] -> profile 行 TYPE,VALUE,DIRECT[,参数]。"""
    if line.startswith(("AND,", "OR,", "NOT,")):
        return f"{line},DIRECT"
    parts = line.split(",")
    return ",".join([*parts[:2], "DIRECT", *parts[2:]])


def collect() -> dict[str, set[str]]:
    src: dict[str, set[str]] = defaultdict(set)
    rule, domainset = surge_files()
    for f in rule:
        rel = str(f.relative_to(DIST))
        for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line and not line.startswith(("#", ";", "//")):
                src[inline(line)].add(rel)
    for f in domainset:
        rel = str(f.relative_to(DIST))
        for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("."):
                src[f"DOMAIN-SUFFIX,{line[1:]},DIRECT"].add(rel)
            else:
                src[f"DOMAIN,{line},DIRECT"].add(rel)
    return src


def check(rules: list[str], profile: Path) -> list[str]:
    """返回 Surge 拒绝的行（profile 内联形式，策略固定为 DIRECT）。"""
    bad = []
    for start in range(0, len(rules), CHUNK):
        alive = rules[start : start + CHUNK]
        while True:
            profile.write_text(
                "[General]\n[Rule]\n" + "\n".join(alive) + "\nFINAL,DIRECT\n",
                encoding="utf-8",
            )
            r = subprocess.run(
                [CLI, "--check", str(profile)],
                capture_output=True,
                text=True,
                check=False,
            )
            out = r.stdout + r.stderr  # 失败信息走 stderr
            if r.returncode == 0:
                break
            m = LINE_NO.search(out)
            if not m:
                sys.exit(f"surge-cli 输出无法解析: {out[:300]}")
            bad.append(alive.pop(int(m.group(1)) - HEADER_LINES - 1))
    return bad


def main() -> int:
    if not Path(CLI).is_file():
        print("未找到 surge-cli（需要装了 Surge 的 Mac）", file=sys.stderr)
        return 1
    if not DIST.is_dir():
        print("dist/ 不存在，先跑 build.py", file=sys.stderr)
        return 1

    src = collect()
    rules = sorted(src)
    with tempfile.TemporaryDirectory() as tmp:
        bad = check(rules, Path(tmp) / "check.conf")

    own = ("metacubex/", "custom/", "aethersailor/rule-surge/")
    failed = False
    for line in bad:
        files = sorted(src[line])
        mine = any(f.startswith(own) for f in files)
        failed |= mine
        tag = "错误" if mine else "镜像"
        print(f"[{tag}] {line}  <- {', '.join(files[:3])}")
    print(f"Surge 复核：{len(rules)} 条去重规则，{len(bad)} 条被 Surge 拒绝")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
