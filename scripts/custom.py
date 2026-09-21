#!/usr/bin/env python3
"""把自定义规则从单一 classical 源文件派生出各客户端格式。

源文件 `custom/*.list` 用 classical 语法，域名与 IP 混写：

    DOMAIN-SUFFIX,example.com
    DOMAIN-KEYWORD,tracker
    IP-CIDR,1.2.3.0/24

派生产物：

    custom/surge/<name>.conf           Surge RULE-SET，原样
    custom/mihomo/<name>.yaml          behavior: classical
    custom/mihomo/<name>-domain.yaml   behavior: domain（仅域名，+.x 形式）
    custom/mihomo/<name>-ip.yaml       behavior: ipcidr（仅 IP）

domain / ip 两种是 mihomo 官方优化过的 behavior，匹配更快；
classical 通用但没有优化。按需引用。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# classical 支持的规则类型。域名类会被派生进 -domain，IP 类进 -ip，
# 其余（PROCESS-NAME / DST-PORT 等）只出现在 classical 与 Surge 侧。
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP-ASN"}
OTHER_TYPES = {"PROCESS-NAME", "DST-PORT", "SRC-PORT", "SRC-IP-CIDR"}
ALL_TYPES = DOMAIN_TYPES | IP_TYPES | OTHER_TYPES

DOMAIN_VALUE = re.compile(r"^[A-Za-z0-9*]([A-Za-z0-9*._-]*)$")
V4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")
V6 = re.compile(r"^[0-9A-Fa-f:]+/\d{1,3}$")


def parse(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """读出 (类型, 值) 列表，以及无法识别的行。"""
    rules: list[tuple[str, str]] = []
    bad: list[str] = []
    seen: set[tuple[str, str]] = set()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "," not in line:
            bad.append(raw.strip())
            continue
        kind, _, value = line.partition(",")
        kind, value = kind.strip().upper(), value.strip()
        # 容忍 mihomo 侧常见的 ,no-resolve 后缀
        value = value.split(",", 1)[0].strip()

        if kind not in ALL_TYPES or not value:
            bad.append(raw.strip())
            continue
        if kind in DOMAIN_TYPES and not DOMAIN_VALUE.fullmatch(value):
            bad.append(raw.strip())
            continue
        if kind == "IP-CIDR" and not V4.fullmatch(value):
            bad.append(raw.strip())
            continue
        if kind == "IP-CIDR6" and not V6.fullmatch(value):
            bad.append(raw.strip())
            continue

        if (kind, value) not in seen:
            seen.add((kind, value))
            rules.append((kind, value))
    return rules, bad


def to_domain_value(kind: str, value: str) -> str | None:
    """域名规则 -> mihomo behavior: domain 的写法。"""
    if kind == "DOMAIN":
        return value
    if kind == "DOMAIN-SUFFIX":
        return f"+.{value}"
    if kind == "DOMAIN-KEYWORD":
        return f"*{value}*"
    if kind == "DOMAIN-WILDCARD":
        return value
    return None


def yaml_payload(items: list[str], header: str) -> str:
    body = "\n".join(f"  - '{i}'" for i in items)
    return f"{header}payload:\n{body}\n"


def build(src_dir: Path, out_dir: Path) -> dict:
    surge_dir = out_dir / "surge"
    mihomo_dir = out_dir / "mihomo"
    stats = {"files": 0, "rules": 0, "bad": []}

    files = sorted(src_dir.glob("*.list"))
    if not files:
        return stats

    surge_dir.mkdir(parents=True, exist_ok=True)
    mihomo_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        name = f.stem
        rules, bad = parse(f)
        if bad:
            stats["bad"] += [f"{f.name}: {b!r}" for b in bad]
        if not rules:
            continue
        stats["files"] += 1
        stats["rules"] += len(rules)

        head = (
            f"# {name}\n"
            f"# 由 fly-rule 自 custom/{f.name} 生成，请勿手工编辑\n"
            f"# 规则数: {len(rules)}\n"
        )

        # Surge：classical 原样
        (surge_dir / f"{name}.conf").write_text(
            head + "\n".join(f"{k},{v}" for k, v in rules) + "\n",
            encoding="utf-8",
        )

        # mihomo classical
        (mihomo_dir / f"{name}.yaml").write_text(
            yaml_payload([f"{k},{v}" for k, v in rules], head),
            encoding="utf-8",
        )

        # mihomo domain
        doms = [d for k, v in rules if (d := to_domain_value(k, v)) is not None]
        if doms:
            (mihomo_dir / f"{name}-domain.yaml").write_text(
                yaml_payload(doms, head), encoding="utf-8"
            )

        # mihomo ipcidr
        ips = [v for k, v in rules if k in IP_TYPES]
        if ips:
            (mihomo_dir / f"{name}-ip.yaml").write_text(
                yaml_payload(ips, head), encoding="utf-8"
            )

    return stats


def main() -> int:
    src = ROOT / "custom"
    out = ROOT / "dist" / "custom"
    stats = build(src, out)
    if stats["bad"]:
        print("自定义规则有无法识别的行:", file=sys.stderr)
        for b in stats["bad"][:20]:
            print(f"  - {b}", file=sys.stderr)
        return 1
    print(f"自定义规则：{stats['files']} 个文件 / {stats['rules']} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
