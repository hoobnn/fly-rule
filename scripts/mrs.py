#!/usr/bin/env python3
"""把 mihomo 的 yaml 规则集编译成 mrs（预编译二进制）。

mrs 是 mihomo 自己的二进制格式：域名存成 succinct trie、IP 存成 CIDR 集合，
加载时不用逐行解析。只能由 `mihomo convert-ruleset` 生成，没有纯 Python 实现。

    mihomo convert-ruleset <behavior> <format> <source> <target>

**只有 domain 与 ipcidr 两种 behavior 能编译成 mrs。** classical 不能 ——
它是「规则类型 + 值」的混合列表，可以包含 PROCESS-NAME / DST-PORT 这类既非
域名也非 IP 的规则，没有对应的可编译结构。mihomo 源码里只有 domainStrategy
与 ipcidrStrategy 实现了 mrsRuleStrategy 接口，对 classical 调用转换会直接
panic（不是返回错误），所以这里按文件名后缀分派，绝不把 classical 送进去。

用法：

    python3 scripts/mrs.py            # 编译 dist/custom/mihomo 下的产物
    python3 scripts/mrs.py --check    # 只检查 mihomo 是否可用

找不到 mihomo 时默认跳过并提示（本地开发不必为此装二进制），CI 里用
--require 让缺失直接失败，避免发布出缺 mrs 的产物。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 文件名后缀 -> behavior。没列进来的（classical 的 <name>.yaml）不编译。
SUFFIX_BEHAVIOR = {"-domain": "domain", "-ip": "ipcidr"}


def find_mihomo() -> str | None:
    """定位 mihomo 可执行文件。"""
    return shutil.which("mihomo")


def behavior_of(path: Path) -> str | None:
    """按文件名后缀判断该用哪个 behavior，classical 返回 None。"""
    for suffix, behavior in SUFFIX_BEHAVIOR.items():
        if path.stem.endswith(suffix):
            return behavior
    return None


def convert(mihomo: str, src: Path, behavior: str) -> tuple[bool, str]:
    """编译单个 yaml -> mrs。返回 (是否成功, 说明)。"""
    dst = src.with_suffix(".mrs")
    proc = subprocess.run(
        [mihomo, "convert-ruleset", behavior, "yaml", str(src), str(dst)],
        capture_output=True,
        text=True,
        check=False,  # 失败要读 stderr 自己处理，不抛异常
    )
    if proc.returncode != 0:
        # convert-ruleset 失败时是 panic，堆栈在 stderr，取首行够定位了
        first = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, first[0] if first else f"退出码 {proc.returncode}"

    # mihomo 对无法表达的条目只打 warning 并跳过，整表照常写出。产物能用，
    # 但内容与 yaml 不一致 —— custom.py 已在构建期排除这类规则，所以这里
    # 出现 warning 说明有漏网的形态，当成失败让构建停下来。
    # 注意 mihomo 的日志走 stdout 而非 stderr，两个流都要看。
    log = (proc.stdout or "") + (proc.stderr or "")
    if "skip invalid" in log:
        detail = next(
            (ln for ln in log.splitlines() if "skip invalid" in ln), ""
        ).strip()
        return False, f"mihomo 跳过了部分条目，yaml 与 mrs 内容不一致：{detail}"

    if not dst.is_file() or dst.stat().st_size == 0:
        return False, "产物为空"
    return True, ""


def build(mihomo: str, mihomo_dir: Path) -> tuple[int, list[str]]:
    """编译目录下所有可编译的 yaml。返回 (成功数, 错误列表)。"""
    made = 0
    errors: list[str] = []

    for src in sorted(mihomo_dir.glob("*.yaml")):
        behavior = behavior_of(src)
        if behavior is None:
            continue  # classical，跳过
        ok, why = convert(mihomo, src, behavior)
        if ok:
            made += 1
        else:
            errors.append(f"{src.name}: {why}")
    return made, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--require",
        action="store_true",
        help="找不到 mihomo 时失败而非跳过（CI 用）",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="只检查 mihomo 是否可用，不编译",
    )
    a = ap.parse_args()

    mihomo = find_mihomo()
    if a.check:
        print(f"mihomo: {mihomo or '未找到'}")
        return 0 if mihomo else 1

    if not mihomo:
        msg = "未找到 mihomo，无法生成 mrs"
        if a.require:
            print(msg, file=sys.stderr)
            return 1
        print(f"{msg}（跳过；装上 mihomo 后重跑即可）")
        return 0

    mihomo_dir = ROOT / "dist" / "custom" / "mihomo"
    if not mihomo_dir.is_dir():
        print("dist/custom/mihomo 不存在，先跑 scripts/custom.py", file=sys.stderr)
        return 1

    made, errors = build(mihomo, mihomo_dir)
    if errors:
        print("mrs 编译失败:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"mrs：{made} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
