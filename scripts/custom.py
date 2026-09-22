#!/usr/bin/env python3
"""把自定义规则从单一 classical 源文件派生出各客户端格式。

源文件 `custom/*.list` 用 classical 语法，域名与 IP 混写：

    DOMAIN-SUFFIX,example.com
    DOMAIN-KEYWORD,tracker
    IP-CIDR,1.2.3.0/24

派生产物：

    custom/surge/<name>.conf           Surge RULE-SET，域名与 IP 混写（原样）
    custom/surge/<name>-domain.conf    仅域名类
    custom/surge/<name>-ip.conf        仅 IP 类
    custom/mihomo/<name>.yaml          behavior: classical
    custom/mihomo/<name>-domain.yaml   behavior: domain（仅域名，+.x 形式）
    custom/mihomo/<name>-domain.mrs    同上，预编译二进制
    custom/mihomo/<name>-ip.yaml       behavior: ipcidr（仅 IP）
    custom/mihomo/<name>-ip.mrs        同上，预编译二进制

两端都拆出 domain / ip 两份，原因不同：

* mihomo 的 domain / ipcidr 是官方优化过的 behavior，匹配比 classical 快，
  且只有这两种能编译成 mrs。
* Surge 侧拆分是为了顺序与 no-resolve —— 域名规则必须全部排在 IP 规则之前，
  且 IP 规则要带 no-resolve 才不会触发 DNS 解析。混写文件只能整体引用一次，
  没法同时满足这两点；拆开后 -domain 放域名段、-ip 放 IP 段并加 no-resolve。

混写的 <name>.conf 仍然保留：只有域名或只有 IP 的规则集，用它更省事。

每份产物的头部都写明自己的规则数，mihomo 侧还写明该用哪个 behavior —— 三份
产物文件名相近而内容形态不同，配错 behavior 时 mihomo 会逐行解析失败、静默
丢弃整表且不中断加载，光看日志以外很难发现。

mrs 由 `mihomo convert-ruleset` 生成（见 mrs.py），只覆盖 domain / ipcidr：
classical 没有对应的可编译结构，mihomo 转换时会直接 panic，所以 <name>.yaml
不会有 mrs 版本。

mihomo 的 `domain` behavior 只接受整标签通配（`*.a.com`、`a.*` 可以），不做
子串匹配，所以 DOMAIN-KEYWORD 以及部分标签通配（`foo*.a.com`）无法表达 ——
mihomo 遇到它们只打一行 warning 就跳过，整表继续加载，事后极难发现。这里在
构建期就把它们从 -domain 产物里排除，并在头部写明跳过了几条，避免产物标称的
规则数与 mihomo 实际加载的条数不一致。它们在 Surge 与 classical 侧照常生效。
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


# mihomo 的 domain behavior 把域名切成标签后逐段匹配，`*` 只能整段占位。
# 形如 `foo*.a.com` 的部分标签通配会被 mihomo 跳过（只打 warning，不中断），
# 所以这里按标签校验，不合格的不进 -domain 产物。
DOMAIN_LABEL = re.compile(r"^(?:\*|[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?)$")


def mihomo_domain_ok(value: str) -> bool:
    """value 能否被 mihomo behavior: domain 接受。

    判据取自 mihomo 的 trie.ValidAndSplitDomain：每个标签要么是完整的 `*`，
    要么不含 `*`；开头的 `+.` / `.` 是后缀通配前缀，单独处理。
    """
    rest = value
    if rest.startswith("+."):
        rest = rest[2:]
    elif rest.startswith("."):
        rest = rest[1:]
    if not rest:
        return False
    return all(DOMAIN_LABEL.fullmatch(lbl) for lbl in rest.split("."))


def to_domain_value(kind: str, value: str) -> str | None:
    """域名规则 -> mihomo behavior: domain 的写法。

    返回 None 表示这条规则在 domain behavior 下无法表达，调用方须跳过它。
    DOMAIN-KEYWORD 是子串匹配，domain behavior 没有对应形态（`*kw*` 会被
    mihomo 静默跳过），只能留在 Surge 与 classical 侧。
    """
    if kind == "DOMAIN-KEYWORD":
        return None
    if kind == "DOMAIN-SUFFIX":
        out = f"+.{value}"
    elif kind in ("DOMAIN", "DOMAIN-WILDCARD"):
        out = value
    else:
        return None
    return out if mihomo_domain_ok(out) else None


def make_head(src_name: str, title: str, count: int, behavior: str = "") -> str:
    """产物头部。

    规则数按各自实际条数写，不能用源文件总数 —— 拆分产物只含子集。
    mihomo 侧标注 behavior：三份产物内容形态不同但文件名相近，引用方光看
    文件无从判断该配哪个，配错会整表静默丢弃且不报错。
    """
    h = (
        f"# {title}\n"
        f"# 由 fly-rule 自 custom/{src_name} 生成，请勿手工编辑\n"
        f"# 规则数: {count}\n"
    )
    if behavior:
        h += f"# mihomo 引用时须写 behavior: {behavior}，写错会整表静默丢弃\n"
    return h


def yaml_payload(items: list[str], header: str) -> str:
    body = "\n".join(f"  - '{i}'" for i in items)
    return f"{header}payload:\n{body}\n"


def build(src_dir: Path, out_dir: Path) -> dict:
    surge_dir = out_dir / "surge"
    mihomo_dir = out_dir / "mihomo"
    stats = {"files": 0, "rules": 0, "bad": [], "domain_skipped": []}

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

        # Surge：classical 原样（域名与 IP 混写）
        (surge_dir / f"{name}.conf").write_text(
            make_head(f.name, name, len(rules))
            + "\n".join(f"{k},{v}" for k, v in rules)
            + "\n",
            encoding="utf-8",
        )

        # Surge：按域名 / IP 拆两份，便于分别放进域名段与 IP 段。
        # OTHER_TYPES（PROCESS-NAME 等）既非域名也非 IP，归入 -domain：
        # 它们不参与 IP 匹配，放在域名段不会触发 DNS 解析。
        surge_dom = [(k, v) for k, v in rules if k in DOMAIN_TYPES or k in OTHER_TYPES]
        surge_ip = [(k, v) for k, v in rules if k in IP_TYPES]
        for suffix, subset in (("domain", surge_dom), ("ip", surge_ip)):
            if not subset:
                continue
            sub_head = make_head(f.name, f"{name}-{suffix}", len(subset))
            if suffix == "ip":
                sub_head += "# 引用时需加 no-resolve，且须排在所有域名规则之后\n"
            (surge_dir / f"{name}-{suffix}.conf").write_text(
                sub_head + "\n".join(f"{k},{v}" for k, v in subset) + "\n",
                encoding="utf-8",
            )

        # mihomo classical
        (mihomo_dir / f"{name}.yaml").write_text(
            yaml_payload(
                [f"{k},{v}" for k, v in rules],
                make_head(f.name, name, len(rules), "classical"),
            ),
            encoding="utf-8",
        )

        # mihomo domain
        # 跳过 domain behavior 表达不了的（KEYWORD、部分标签通配）：留在产物里
        # mihomo 只会 warning 后丢弃，头部规则数就会与实际加载数不符。
        doms: list[str] = []
        skipped: list[str] = []
        for k, v in rules:
            if k not in DOMAIN_TYPES:
                continue
            d = to_domain_value(k, v)
            if d is None:
                skipped.append(f"{k},{v}")
            else:
                doms.append(d)
        if skipped:
            stats["domain_skipped"] += [f"{f.name}: {x}" for x in skipped]
        if doms:
            head = make_head(f.name, f"{name}-domain", len(doms), "domain")
            if skipped:
                head += (
                    f"# 已排除 {len(skipped)} 条 domain behavior 无法表达的规则"
                    f"（如 {skipped[0]}），它们仅在 Surge 与 classical 产物中生效\n"
                )
            (mihomo_dir / f"{name}-domain.yaml").write_text(
                yaml_payload(doms, head), encoding="utf-8"
            )

        # mihomo ipcidr
        ips = [v for k, v in rules if k in IP_TYPES]
        if ips:
            (mihomo_dir / f"{name}-ip.yaml").write_text(
                yaml_payload(ips, make_head(f.name, f"{name}-ip", len(ips), "ipcidr")),
                encoding="utf-8",
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

    # 这些规则 mihomo 的 domain behavior 表达不了，已从 -domain 产物排除。
    # 不是错误（Surge 与 classical 侧照常生效），但要让人看见，否则会以为
    # 自己写的关键字规则在 mihomo 上也生效了。
    if stats["domain_skipped"]:
        print(
            f"  其中 {len(stats['domain_skipped'])} 条不进 mihomo -domain 产物"
            "（domain behavior 无此形态，仅 Surge 与 classical 生效）:"
        )
        for x in stats["domain_skipped"][:10]:
            print(f"    - {x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
