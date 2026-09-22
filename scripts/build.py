#!/usr/bin/env python3
"""fly-rule 构建入口：同步上游规则，转成 Surge 格式，并镜像上游原始格式。

产物布局 —— 以上游为最外层，新增上游互不干扰：

    release/<上游>/<数据集>/surge/*.conf       我们转换的 Surge 规则
    release/<上游>/<数据集>/mihomo/*.mrs|…     上游格式原样镜像
    release/custom/*.conf                      自定义规则

域名侧（kind: domain），上游是 mihomo `behavior: domain` 格式：

    +.example.com   ->  DOMAIN-SUFFIX,example.com
    example.com     ->  DOMAIN,example.com

IP 侧（kind: ip），上游是裸 CIDR：

    1.0.1.0/24      ->  IP-CIDR,1.0.1.0/24
    2001:250::/30   ->  IP-CIDR6,2001:250::/30

转换无损 —— 上游已在编译阶段把 include / 属性 / 正则全部展开固化，
产物里不存在 Surge 表达不了的形态。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import custom

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".work"

DOMAIN_RE = re.compile(
    r"^[A-Za-z0-9*]([A-Za-z0-9*-]*[A-Za-z0-9*])?"
    r"(\.[A-Za-z0-9*]([A-Za-z0-9*-]*[A-Za-z0-9*])?)*$"
)
V4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")
V6_RE = re.compile(r"^[0-9A-Fa-f:]+/\d{1,3}$")


def run(cmd, *, check: bool = True, **kw):
    return subprocess.run(cmd, check=check, **kw)


def sync(src: dict, offline: bool) -> str:
    """稀疏克隆上游，只检出配置里声明的数据集路径。"""
    dest = WORK / src["key"]
    paths = sorted({d["path"] for d in src["datasets"]})
    for d in src["datasets"]:
        for e in d.get("extra_mirror", []):
            paths.append(e["path"])

    if offline:
        if not dest.exists():
            sys.exit(f"离线模式但本地无 {src['key']} 副本，先跑一次联网构建")
        print(f"[{src['key']}] 离线模式，跳过拉取")
    elif dest.exists():
        print(f"[{src['key']}] 更新上游…")
        run(
            ["git", "-C", str(dest), "sparse-checkout", "set", *paths],
            capture_output=True,
        )
        run(
            ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", src["branch"]],
            capture_output=True,
        )
        run(
            ["git", "-C", str(dest), "reset", "--hard", f"origin/{src['branch']}"],
            capture_output=True,
        )
    else:
        print(f"[{src['key']}] 克隆上游…")
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                src["branch"],
                "--filter=blob:none",
                "--no-checkout",
                src["repo"],
                str(dest),
            ],
            capture_output=True,
        )
        run(
            ["git", "-C", str(dest), "sparse-checkout", "set", *paths],
            capture_output=True,
        )
        run(["git", "-C", str(dest), "checkout", src["branch"]], capture_output=True)

    rev = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    print(f"[{src['key']}] commit: {rev}")
    return rev


def convert_domain(text: str) -> tuple[list[str], list[str]]:
    rules, bad, seen = [], [], set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("+."):
            kind, value = "DOMAIN-SUFFIX", line[2:]
        elif line.startswith("."):
            kind, value = "DOMAIN-SUFFIX", line[1:]
        else:
            kind, value = "DOMAIN", line
        if not value or not DOMAIN_RE.fullmatch(value):
            bad.append(line)
            continue
        rule = f"{kind},{value}"
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)
    return rules, bad


def convert_ip(text: str) -> tuple[list[str], list[str]]:
    rules, bad, seen = [], [], set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if V4_RE.fullmatch(line):
            rule = f"IP-CIDR,{line}"
        elif V6_RE.fullmatch(line):
            rule = f"IP-CIDR6,{line}"
        else:
            bad.append(line)
            continue
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)
    return rules, bad


def mirror_tree(src_dir: Path, out_dir: Path, exclude: list[str] | None = None) -> int:
    """整目录原样镜像，保留子目录结构。exclude 里的顶层子目录会跳过。"""
    skip = set(exclude or [])
    n = 0
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src_dir)
        if skip and rel.parts and rel.parts[0] in skip:
            continue
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        n += 1
    return n


def build_dataset(src: dict, ds: dict, rev: str, dist: Path, no_mirror: bool) -> dict:
    src_dir = WORK / src["key"] / ds["path"]
    if not src_dir.is_dir():
        sys.exit(f"上游目录不存在: {src_dir}")

    base = dist / src["key"] / ds["name"]

    # 上游已是成品（Surge / mihomo 最终格式），整目录镜像，不做转换
    if ds["kind"] == "mirror":
        if no_mirror:
            print(f"  {ds['name']:<18} 跳过（--no-mirror）")
            return {
                "dataset": ds["name"],
                "path": ds["path"],
                "kind": "mirror",
                "categories": 0,
                "total_rules": 0,
                "skipped_lines": 0,
                "empty_categories": [],
                "mirrored": {},
                "rulesets": [],
            }
        base.mkdir(parents=True, exist_ok=True)
        n = mirror_tree(src_dir, base, ds.get("exclude"))
        print(f"  {ds['name']:<18} 镜像 {n} 个文件")
        return {
            "dataset": ds["name"],
            "path": ds["path"],
            "kind": "mirror",
            "categories": 0,
            "total_rules": 0,
            "skipped_lines": 0,
            "empty_categories": [],
            "mirrored": {"files": n},
            "rulesets": [],
        }

    out_dir = base / "surge"
    out_dir.mkdir(parents=True, exist_ok=True)

    convert = convert_domain if ds["kind"] == "domain" else convert_ip
    rulesets, empty, bad_total = [], [], 0

    for f in sorted(src_dir.glob("*.list")):
        name = f.name[: -len(".list")]
        rules, bad = convert(f.read_text(encoding="utf-8", errors="ignore"))
        bad_total += len(bad)
        if not rules:
            empty.append(name)
            continue
        header = (
            f"# {name}\n"
            f"# 由 fly-rule 自 {src['key']}@{rev} 转换，请勿手工编辑\n"
            f"# 上游: {ds['path']}/{name}.list | 规则数: {len(rules)}\n"
        )
        if bad:
            header += f"# 跳过无法转换的 {len(bad)} 行，例: {bad[0]!r}\n"
        (out_dir / f"{name}.conf").write_text(
            header + "\n".join(rules) + "\n", encoding="utf-8"
        )
        rulesets.append({"category": name, "rules": len(rules), "skipped": len(bad)})

    mirror = {}
    if not no_mirror:
        mir = base / "mihomo"
        mir.mkdir(parents=True, exist_ok=True)
        for ext in ds.get("mirror", []):
            n = 0
            for f in sorted(src_dir.glob(f"*.{ext}")):
                shutil.copy2(f, mir / f.name)
                n += 1
            mirror[ext] = n
        for extra in ds.get("extra_mirror", []):
            esrc = WORK / src["key"] / extra["path"]
            if not esrc.is_dir():
                continue
            eout = base / extra["out"]
            eout.mkdir(parents=True, exist_ok=True)
            n = 0
            for f in sorted(esrc.iterdir()):
                if f.is_file():
                    shutil.copy2(f, eout / f.name)
                    n += 1
            mirror[extra["out"]] = n

    total = sum(r["rules"] for r in rulesets)
    print(
        f"  {ds['name']:<18} {len(rulesets):>5} 个规则集 / {total:>7} 条"
        + (f"，镜像 {sum(mirror.values())} 个文件" if mirror else "")
    )
    return {
        "dataset": ds["name"],
        "path": ds["path"],
        "kind": ds["kind"],
        "categories": len(rulesets),
        "total_rules": total,
        "skipped_lines": bad_total,
        "empty_categories": empty,
        "mirrored": mirror,
        "rulesets": rulesets,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "sources.toml")
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--offline", action="store_true", help="不拉取上游，用本地副本")
    ap.add_argument("--custom", type=Path, default=ROOT / "custom")
    ap.add_argument("--no-mirror", action="store_true", help="不镜像上游格式")
    ap.add_argument("--only", help="只构建指定上游 key")
    a = ap.parse_args()

    cfg = tomllib.loads(a.config.read_text(encoding="utf-8"))
    sources = cfg.get("sources") or []
    if a.only:
        sources = [s for s in sources if s["key"] == a.only]
        if not sources:
            sys.exit(f"配置里没有上游 {a.only}")
    if not sources:
        sys.exit("sources.toml 里没有 sources 条目")

    if a.dist.exists():
        shutil.rmtree(a.dist)
    a.dist.mkdir(parents=True)

    report_sources = []
    for src in sources:
        rev = sync(src, a.offline)
        datasets = [
            build_dataset(src, ds, rev, a.dist, a.no_mirror) for ds in src["datasets"]
        ]
        report_sources.append(
            {
                "key": src["key"],
                "repo": src["repo"],
                "branch": src["branch"],
                "rev": rev,
                "datasets": datasets,
            }
        )

    # 自定义规则：单一 classical 源文件派生出各客户端格式
    custom_stats = custom.build(a.custom, a.dist / "custom")
    if custom_stats["bad"]:
        print("!! 自定义规则有无法识别的行:", file=sys.stderr)
        for b in custom_stats["bad"][:20]:
            print(f"   - {b}", file=sys.stderr)
        return 1
    custom_count = custom_stats["files"]

    summary = {
        "sources": report_sources,
        "custom_files": custom_count,
        "total_rules": sum(
            d["total_rules"] for s in report_sources for d in s["datasets"]
        ),
        "total_categories": sum(
            d["categories"] for s in report_sources for d in s["datasets"]
        ),
    }
    (a.dist / "build-report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"\n完成：{len(report_sources)} 个上游，"
        f"{summary['total_categories']} 个规则集，"
        f"共 {summary['total_rules']} 条规则"
    )
    if custom_count:
        print(f"自定义规则 {custom_count} 个 / {custom_stats['rules']} 条")
        # mihomo 的 domain behavior 表达不了的规则（KEYWORD 等）已被排除，
        # 在 Surge 与 classical 侧仍生效。不是错误，但要让人看见。
        if custom_stats["domain_skipped"]:
            print(
                f"  其中 {len(custom_stats['domain_skipped'])} 条不进 "
                "mihomo -domain 产物（仅 Surge 与 classical 生效）"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
