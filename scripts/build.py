#!/usr/bin/env python3
"""fly-rule 构建入口：同步上游规则，转成 Surge 格式，并镜像上游原始格式。

产物布局 —— 以上游为最外层，新增上游互不干扰：

    release/<上游>/<数据集>/surge/*.conf       我们转换的 Surge 规则
    release/<上游>/<数据集>/mihomo/*.mrs|…     上游格式原样镜像
    release/custom/*.conf                      自定义规则

域名侧（kind: domain）优先读上游 classical/ 目录（带规则类型的完整版）：

    DOMAIN / DOMAIN-SUFFIX / DOMAIN-KEYWORD   原样保留
    DOMAIN-REGEX                              Surge 不支持，跳过并在文件头注明

classical 缺失时回退到 mihomo `behavior: domain` 格式。注意 domain 形态本身
就没有 KEYWORD 与 REGEX（mihomo domain behavior 表达不了），只用它转换会把
Surge 完全支持的 DOMAIN-KEYWORD 一起丢掉：

    +.example.com   ->  DOMAIN-SUFFIX,example.com
    example.com     ->  DOMAIN,example.com

IP 侧（kind: ip），上游是裸 CIDR：

    1.0.1.0/24      ->  IP-CIDR,1.0.1.0/24
    2001:250::/30   ->  IP-CIDR6,2001:250::/30

除 DOMAIN-REGEX 外转换无损：上游已在编译阶段把 include / 属性展开固化，
正则则保留为 DOMAIN-REGEX，Surge 没有对应规则类型。
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
import surge

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


# classical 里 KEYWORD 的值是子串，可以带首尾点（如 `.pinterest.`），不套 DOMAIN_RE
KEYWORD_RE = re.compile(r"^[^,\s]+$")


def convert_domain_classical(text: str) -> tuple[list[str], list[str], list[str]]:
    """classical 源 -> Surge。返回 (规则, 无法转换的行, 跳过的 DOMAIN-REGEX)。"""
    rules, bad, regex, seen = [], [], [], set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        kind, _, value = line.partition(",")
        if kind == "DOMAIN-REGEX":
            regex.append(line)
            continue
        if kind in ("DOMAIN", "DOMAIN-SUFFIX"):
            ok = bool(value) and DOMAIN_RE.fullmatch(value)
        elif kind == "DOMAIN-KEYWORD":
            ok = bool(KEYWORD_RE.fullmatch(value))
        else:
            ok = False
        if not ok:
            bad.append(line)
            continue
        if line not in seen:
            seen.add(line)
            rules.append(line)
    return rules, bad, regex


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


WILDCARD_KEYWORD = re.compile(r"^\*([^*]+)\*$")


def domain_index(classical_dir: Path) -> set[str]:
    """geosite classical 里全部 DOMAIN / DOMAIN-SUFFIX 的值，供展开关键字用。"""
    values: set[str] = set()
    for f in classical_dir.glob("*.list"):
        for raw in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            kind, _, value = raw.strip().partition(",")
            if kind in ("DOMAIN", "DOMAIN-SUFFIX") and DOMAIN_RE.fullmatch(value):
                values.add(value.lower())
    return values


def expand_keyword(keyword: str, index: set[str]) -> list[str]:
    """把关键字展开成已知的具体域名（+.形式）。

    mihomo 的 domain behavior 不做子串匹配，DOMAIN-KEYWORD 无法表达；这里在
    geosite 已收录的域名里找包含该关键字的，被其他后缀覆盖的子域不重复列出。
    """
    hits = {v for v in index if keyword.lower() in v}
    kept = [v for v in hits if not any(v.endswith("." + u) for u in hits if u != v)]
    return [f"+.{v}" for v in sorted(kept)]


def mihomo_tree(
    src_dir: Path,
    out_dir: Path,
    index: set[str],
    header: str,
    exclude: list[str] | None = None,
) -> dict:
    """镜像的 mihomo 专用版：domain 形态 yaml 里的 `*kw*` 展开成具体域名。

    上游把 DOMAIN-KEYWORD 写成 `*kw*` 塞进 domain 规则集，mihomo 只会当非法域名
    丢弃。改写过的 yaml 删掉上游的同名 mrs，由 mrs.py 重新编译；其余文件原样。
    """
    skip = set(exclude or [])
    stats: dict = {"files": 0, "adapted": [], "expanded": {}, "dropped": []}
    adapted_mrs: set[Path] = set()
    for f in sorted(src_dir.rglob("*")):
        rel = f.relative_to(src_dir)
        if not f.is_file() or (skip and rel.parts and rel.parts[0] in skip):
            continue
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = (
            f.read_text(encoding="utf-8", errors="ignore")
            if f.suffix == ".yaml"
            else ""
        )
        if f.suffix != ".yaml" or not re.search(r"^\s*- '?\*[^*]+\*'?\s*$", text, re.M):
            shutil.copy2(f, dest)
            stats["files"] += 1
            continue

        items, notes = [], []
        existing = {
            ln.strip()[2:].strip().strip("'\"")
            for ln in text.splitlines()
            if ln.strip().startswith("- ")
        }
        out_lines = []
        for ln in text.splitlines():
            item = (
                ln.strip()[2:].strip().strip("'\"")
                if ln.strip().startswith("- ")
                else None
            )
            m = WILDCARD_KEYWORD.fullmatch(item or "")
            if not m:
                out_lines.append(ln)
                if item is not None:
                    items.append(item)
                continue
            kw = m.group(1)
            known = expand_keyword(kw, index)
            doms = [d for d in known if d not in existing]
            existing.update(doms)
            indent = ln[: len(ln) - len(ln.lstrip())]
            out_lines += [f"{indent}- '{d}'" for d in doms]
            items += doms
            stats["expanded"][f"{rel.as_posix()}: {kw}"] = doms
            if doms:
                notes.append(f"DOMAIN-KEYWORD,{kw} -> 补 {len(doms)} 个域名")
            elif known:
                notes.append(f"DOMAIN-KEYWORD,{kw} 的已知域名本表已收录，无需补充")
            else:
                notes.append(f"DOMAIN-KEYWORD,{kw} 无已知域名可展开，已丢弃")
                stats["dropped"].append(f"{rel.as_posix()}: {kw}")
        body = "\n".join(
            re.sub(r"^# TOTAL: \d+$", f"# TOTAL: {len(items)}", ln) for ln in out_lines
        )
        head = header + f"# 上游: {rel.as_posix()}\n"
        head += "".join(f"# 关键字展开（取自 MetaCubeX geosite）: {n}\n" for n in notes)
        dest.write_text(head + body + "\n", encoding="utf-8")
        stats["files"] += 1
        stats["adapted"].append(rel.as_posix())
        adapted_mrs.add(rel.with_suffix(".mrs"))
    # 改写过的 yaml，上游 mrs 与之不一致，删掉由 mrs.py 重编
    for rel in adapted_mrs:
        (out_dir / rel).unlink(missing_ok=True)
    return stats


def surge_tree(
    src_dir: Path, out_dir: Path, header: str, exclude: list[str] | None = None
) -> dict:
    """镜像里的 classical .list 转一份 Surge 专用版，保留注释与目录结构。

    上游 .list 按 mihomo 写法（DST-PORT、IPv6 也写 IP-CIDR），Surge 加载时会
    静默跳过这些行。镜像本身必须与上游逐字节一致，所以另出一份改写后的。
    """
    skip = set(exclude or [])
    stats = {"files": 0, "rewritten": 0, "dropped": []}
    for f in sorted(src_dir.rglob("*.list")):
        rel = f.relative_to(src_dir)
        if skip and rel.parts and rel.parts[0] in skip:
            continue
        out, rewritten, dropped = [], 0, []
        for raw in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                out.append(raw)
                continue
            conv = surge.to_surge(line)
            if conv is None:
                dropped.append(line)
                continue
            rewritten += conv != line
            out.append(conv)
        head = header + f"# 上游: {rel.as_posix()}\n"
        if rewritten:
            head += f"# 改写为 Surge 写法 {rewritten} 行（DST-PORT -> DEST-PORT 等）\n"
        if dropped:
            head += f"# 跳过 Surge 表达不了的 {len(dropped)} 行，例: {dropped[0]!r}\n"
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(head + "\n".join(out) + "\n", encoding="utf-8")
        stats["files"] += 1
        stats["rewritten"] += rewritten
        stats["dropped"] += [f"{rel.as_posix()}: {d}" for d in dropped]
    return stats


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
        if ds.get("surge_out"):
            sout = dist / src["key"] / ds["surge_out"]
            st = surge_tree(
                src_dir,
                sout,
                f"# 由 fly-rule 自 {src['key']}@{rev} 转换（Surge 专用），"
                "请勿手工编辑\n",
                ds.get("exclude"),
            )
            print(
                f"  {ds['surge_out']:<18} Surge 转换 {st['files']} 个文件，"
                f"改写 {st['rewritten']} 行，跳过 {len(st['dropped'])} 行"
            )
            for d in st["dropped"][:10]:
                print(f"    - 跳过 {d}")
        if ds.get("mihomo_out"):
            index_dir = WORK / ds["keyword_index"]
            if not index_dir.is_dir():
                sys.exit(f"关键字展开需要 {index_dir}，先构建 metacubex")
            mt = mihomo_tree(
                src_dir,
                dist / src["key"] / ds["mihomo_out"],
                domain_index(index_dir),
                f"# 由 fly-rule 自 {src['key']}@{rev} 转换（mihomo 专用），"
                "请勿手工编辑\n",
                ds.get("exclude"),
            )
            print(
                f"  {ds['mihomo_out']:<18} mihomo 转换 {mt['files']} 个文件，"
                f"改写 {len(mt['adapted'])} 个"
            )
            for k, v in mt["expanded"].items():
                print(f"    - {k} -> {', '.join(v) or '（无需补充或无可展开）'}")
            for d in mt["dropped"]:
                print(f"    - 无已知域名可展开，已丢弃: {d}")
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

    rulesets, empty, bad_total, regex_total = [], [], 0, 0

    for f in sorted(src_dir.glob("*.list")):
        name = f.name[: -len(".list")]
        classical = src_dir / "classical" / f.name
        regex: list[str] = []
        if ds["kind"] == "domain" and classical.is_file():
            upstream = f"{ds['path']}/classical/{name}.list"
            rules, bad, regex = convert_domain_classical(
                classical.read_text(encoding="utf-8", errors="ignore")
            )
        else:
            upstream = f"{ds['path']}/{name}.list"
            convert = convert_domain if ds["kind"] == "domain" else convert_ip
            rules, bad = convert(f.read_text(encoding="utf-8", errors="ignore"))
        bad_total += len(bad)
        regex_total += len(regex)
        if not rules:
            empty.append(name)
            continue
        header = (
            f"# {name}\n"
            f"# 由 fly-rule 自 {src['key']}@{rev} 转换，请勿手工编辑\n"
            f"# 上游: {upstream} | 规则数: {len(rules)}\n"
        )
        if bad:
            header += f"# 跳过无法转换的 {len(bad)} 行，例: {bad[0]!r}\n"
        if regex:
            header += (
                f"# 跳过 Surge 不支持的 DOMAIN-REGEX {len(regex)} 条，"
                f"例: {regex[0]!r}\n"
            )
        (out_dir / f"{name}.conf").write_text(
            header + "\n".join(rules) + "\n", encoding="utf-8"
        )
        rulesets.append(
            {
                "category": name,
                "rules": len(rules),
                "skipped": len(bad),
                "regex_skipped": len(regex),
            }
        )

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
        + (f"，跳过 DOMAIN-REGEX {regex_total} 条" if regex_total else "")
        + (f"，镜像 {sum(mirror.values())} 个文件" if mirror else "")
    )
    return {
        "dataset": ds["name"],
        "path": ds["path"],
        "kind": ds["kind"],
        "categories": len(rulesets),
        "total_rules": total,
        "skipped_lines": bad_total,
        "regex_skipped": regex_total,
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
