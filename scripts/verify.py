#!/usr/bin/env python3
"""产物校验门禁。语法非法、重复、与上游不一致都会让构建失败。

校验三件事：
1. Surge 产物语法合法、无重复
2. Surge 产物条数与上游去重后逐个文件一致（转换无损）
3. 镜像与上游逐字节一致（兜底副本不能漂移）

自定义规则的校验独立成 check_custom()：custom.yml 只构建 custom/，
产物里没有上游目录，用 --only-custom 跳过上面三项。
另外校验 mihomo 产物的 payload 形态与文件名隐含的 behavior 相符 ——
behavior 配错时 mihomo 只会静默丢表，不报错，事后很难发现。
mrs 产物同时校验存在性与魔数：引用方按 format: mrs 拉到 404 或坏文件时，
mihomo 会整表加载失败。
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".work"

DOMAIN_RULE = re.compile(r"^(DOMAIN|DOMAIN-SUFFIX),[A-Za-z0-9.*_-]+$")
IP_RULE = re.compile(r"^(IP-CIDR|IP-CIDR6),[0-9A-Fa-f.:]+/\d{1,3}$")
# 自定义规则用 classical 语法：域名、IP、进程、端口都允许
CLASSICAL_RULE = re.compile(
    r"^(DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN-WILDCARD"
    r"|IP-CIDR|IP-CIDR6|IP-ASN"
    r"|PROCESS-NAME|DST-PORT|SRC-PORT|SRC-IP-CIDR),.+$"
)
PAYLOAD_ITEM = re.compile(r"  - '[^']+'")

# mihomo 三种 behavior 各自的 payload 形态。配错 behavior 时 mihomo 会逐行
# 解析失败、静默丢弃整表且不中断加载，所以这里按文件名后缀反查形态是否相符。
PAYLOAD_CLASSICAL = re.compile(r"^[A-Z][A-Z0-9-]*,")  # RULE-TYPE,value
PAYLOAD_IPCIDR = re.compile(r"^[0-9A-Fa-f.:]+/\d{1,3}$")  # 裸 CIDR


def rule_lines(path: Path) -> list[str]:
    return [
        l
        for l in path.read_text(encoding="utf-8").splitlines()
        if l and not l.startswith("#")
    ]


def upstream_count(f: Path, kind: str) -> int:
    """按 build.py 的口径重算上游去重后的条数。"""
    seen = set()
    for raw in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if kind == "domain":
            key = (
                ("DOMAIN-SUFFIX", line[2:])
                if line.startswith("+.")
                else ("DOMAIN-SUFFIX", line[1:])
                if line.startswith(".")
                else ("DOMAIN", line)
            )
        else:
            key = ("IP", line)
        seen.add(key)
    return len(seen)


def check_custom(dist: Path, require_mrs: bool = False) -> tuple[list[str], int]:
    """自定义规则：Surge 侧是 classical，mihomo 侧是 payload YAML。

    require_mrs 为真时，缺 mrs 算错误。本地开发未必装了 mihomo，默认只在
    mrs 存在时校验它合法；CI 用 --require-mrs 要求必须齐全。
    """
    errors: list[str] = []
    total_rules = 0

    cdir = dist / "custom"
    if not cdir.is_dir():
        return errors, total_rules

    for f in sorted((cdir / "surge").glob("*.conf")):
        lines = rule_lines(f)
        bad = [l for l in lines if not CLASSICAL_RULE.match(l)]
        if bad:
            errors.append(
                f"custom/surge/{f.name} 语法非法 {len(bad)} 行，例: {bad[0]!r}"
            )
        if len(set(lines)) != len(lines):
            errors.append(f"custom/surge/{f.name} 有重复行")
        total_rules += len(lines)

    for f in sorted((cdir / "mihomo").glob("*.yaml")):
        lines = rule_lines(f)
        if not lines or lines[0] != "payload:":
            errors.append(f"custom/mihomo/{f.name} 缺少 payload: 头")
            continue
        bad = [l for l in lines[1:] if not PAYLOAD_ITEM.fullmatch(l)]
        if bad:
            errors.append(
                f"custom/mihomo/{f.name} payload 项格式非法 "
                f"{len(bad)} 行，例: {bad[0]!r}"
            )
            continue

        errors += check_behavior(f, lines[1:])

    errors += check_mrs(cdir / "mihomo", require_mrs)

    return errors, total_rules


# mrs 的 zstd 帧头。mihomo 写 mrs 时整体走 zstd，magic 在解压后才是 MRS，
# 所以这里只能校验外层 zstd 魔数，内容一致性由 mrs.py 编译期保证。
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def check_mrs(mihomo_dir: Path, require: bool = False) -> list[str]:
    """mrs 产物：存在的必须合法；require 时还必须齐全。

    只有 -domain / -ip 能编译成 mrs（classical 不支持，见 scripts/mrs.py）。
    缺失说明编译那步没跑或悄悄失败了，而引用方按 format: mrs 拉到 404 时
    mihomo 会整表加载失败 —— 所以 CI 里必须拦住。本地没装 mihomo 时 mrs.py
    会跳过生成，这时不该让 verify 失败，故缺失与否由 require 决定。
    """
    errors: list[str] = []
    if not mihomo_dir.is_dir():
        return errors

    for y in sorted(mihomo_dir.glob("*.yaml")):
        stem = y.stem
        if not (stem.endswith("-domain") or stem.endswith("-ip")):
            # classical：不该有 mrs
            if y.with_suffix(".mrs").exists():
                errors.append(
                    f"custom/mihomo/{stem}.mrs 不该存在（classical 无法编译成 mrs）"
                )
            continue

        m = y.with_suffix(".mrs")
        if not m.is_file():
            if require:
                errors.append(f"custom/mihomo/{stem}.mrs 缺失（yaml 有但 mrs 没生成）")
            continue
        if m.stat().st_size == 0:
            errors.append(f"custom/mihomo/{stem}.mrs 为空")
            continue
        if m.read_bytes()[:4] != ZSTD_MAGIC:
            errors.append(f"custom/mihomo/{stem}.mrs 不是合法 mrs（zstd 魔数不符）")

    return errors


def check_behavior(f: Path, items: list[str]) -> list[str]:
    """payload 形态必须与文件名隐含的 behavior 一致。

    三份产物文件名相近、内容形态不同，配错 behavior 不会报错只会静默丢表，
    所以在构建期就把形态钉死：-ip 必须是裸 CIDR，-domain 不能带规则类型前缀，
    不带后缀的 classical 必须每行都有前缀。
    """
    values = [i.strip()[3:].strip("'") for i in items]
    if not values:
        return []

    stem = f.stem
    if stem.endswith("-ip"):
        behavior = "ipcidr"
        bad = [v for v in values if not PAYLOAD_IPCIDR.fullmatch(v)]
    elif stem.endswith("-domain"):
        behavior = "domain"
        bad = [v for v in values if PAYLOAD_CLASSICAL.match(v)]
    else:
        behavior = "classical"
        bad = [v for v in values if not PAYLOAD_CLASSICAL.match(v)]

    if bad:
        return [
            f"custom/mihomo/{f.name} 内容形态与 behavior: {behavior} 不符 "
            f"{len(bad)} 项，例: {bad[0]!r}"
        ]

    # 头部的 behavior 标注也要与文件名一致，避免注释与内容脱节
    head = f.read_text(encoding="utf-8")
    marker = f"behavior: {behavior}"
    if marker not in head:
        return [f"custom/mihomo/{f.name} 头部缺少 `{marker}` 标注"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only-custom",
        action="store_true",
        help="只校验 custom/，用于不含上游产物的构建",
    )
    ap.add_argument(
        "--require-mrs",
        action="store_true",
        help="要求 mrs 产物齐全（CI 用；本地无 mihomo 时不要加）",
    )
    a = ap.parse_args()

    dist = ROOT / "dist"
    if not dist.is_dir():
        print("dist/ 不存在", file=sys.stderr)
        return 1

    if a.only_custom:
        cdir = dist / "custom"
        if not cdir.is_dir():
            print("dist/custom/ 不存在", file=sys.stderr)
            return 1
        errors, total_rules = check_custom(dist, a.require_mrs)
        if errors:
            print("校验失败:", file=sys.stderr)
            for e in errors[:40]:
                print(f"  - {e}", file=sys.stderr)
            return 1
        surge = len(list((cdir / "surge").glob("*.conf")))
        mihomo = len(list((cdir / "mihomo").glob("*.yaml")))
        mrs = len(list((cdir / "mihomo").glob("*.mrs")))
        print(
            f"校验通过：自定义规则 {surge + mihomo + mrs} 个文件 "
            f"/ {total_rules} 条规则（含 {mrs} 个 mrs）"
        )
        return 0

    cfg = tomllib.loads((ROOT / "sources.toml").read_text(encoding="utf-8"))
    errors: list[str] = []
    total_rules = total_files = mirrored = 0

    for src in cfg.get("sources", []):
        key = src["key"]
        for ds in src["datasets"]:
            base = dist / key / ds["name"]
            src_dir = WORK / key / ds["path"]
            label = f"{key}/{ds['name']}"

            # 纯镜像数据集：只核对与上游逐字节一致
            if ds["kind"] == "mirror":
                if not base.is_dir():
                    continue
                skip = set(ds.get("exclude") or [])
                for f in sorted(base.rglob("*")):
                    if not f.is_file():
                        continue
                    mirrored += 1
                    up = src_dir / f.relative_to(base)
                    if not up.is_file():
                        errors.append(f"{label}/{f.relative_to(base)} 上游已无此文件")
                    elif f.read_bytes() != up.read_bytes():
                        errors.append(f"{label}/{f.relative_to(base)} 与上游不一致")
                # 上游有但我们漏掉的（排除项除外）
                for up in sorted(src_dir.rglob("*")):
                    if not up.is_file():
                        continue
                    rel = up.relative_to(src_dir)
                    if skip and rel.parts and rel.parts[0] in skip:
                        continue
                    if not (base / rel).is_file():
                        errors.append(f"{label}/{rel} 上游有但产物缺失")
                continue

            rx = DOMAIN_RULE if ds["kind"] == "domain" else IP_RULE

            surge = base / "surge"
            if not surge.is_dir():
                errors.append(f"{label}/surge/ 不存在")
                continue

            files = sorted(surge.glob("*.conf"))
            if not files:
                errors.append(f"{label}/surge/ 为空")
                continue

            for f in files:
                lines = rule_lines(f)
                total_files += 1
                if not lines:
                    errors.append(f"{label}/surge/{f.name} 没有任何规则")
                    continue
                total_rules += len(lines)

                bad = [l for l in lines if not rx.match(l)]
                if bad:
                    errors.append(
                        f"{label}/surge/{f.name} 语法非法 {len(bad)} 行，例: {bad[0]!r}"
                    )
                if len(set(lines)) != len(lines):
                    errors.append(
                        f"{label}/surge/{f.name} 有 "
                        f"{len(lines) - len(set(lines))} 行重复"
                    )

                up = src_dir / f"{f.name[: -len('.conf')]}.list"
                if up.is_file():
                    want = upstream_count(up, ds["kind"])
                    if want != len(lines):
                        errors.append(
                            f"{label}/surge/{f.name} 条数与上游不符："
                            f"上游 {want}，产物 {len(lines)}"
                        )

            # 镜像逐字节比对
            for mdir, msrc in [
                (base / "mihomo", src_dir),
                *[
                    (base / e["out"], WORK / key / e["path"])
                    for e in ds.get("extra_mirror", [])
                ],
            ]:
                if not mdir.is_dir():
                    continue
                if not msrc.is_dir():
                    errors.append(f"{label}/{mdir.name}/ 上游副本缺失")
                    continue
                for f in sorted(mdir.iterdir()):
                    if not f.is_file():
                        continue
                    mirrored += 1
                    up = msrc / f.name
                    if not up.is_file():
                        errors.append(f"{label}/{mdir.name}/{f.name} 上游已无此文件")
                    elif f.read_bytes() != up.read_bytes():
                        errors.append(f"{label}/{mdir.name}/{f.name} 与上游不一致")

    custom_errors, custom_rules = check_custom(dist, a.require_mrs)
    errors += custom_errors
    total_rules += custom_rules

    if errors:
        print("校验失败:", file=sys.stderr)
        for e in errors[:40]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 40:
            print(f"  …另有 {len(errors) - 40} 条", file=sys.stderr)
        return 1

    print(
        f"校验通过：{total_files} 个规则集 / {total_rules} 条规则，与上游逐条一致"
        + (f"；镜像 {mirrored} 个文件逐字节一致" if mirrored else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
