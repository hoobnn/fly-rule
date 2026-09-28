"""Surge 规则语法：哪些行 Surge 会跳过，mihomo 写法怎么改写成 Surge 写法。

Surge 加载规则集时遇到不认的行只打一行 warning 跳过，不报错，事后很难发现。
类型白名单以 surge-cli --check（Surge Mac 6.9.1）实测为准；Surge 升级后用
scripts/surgecheck.py 复核有没有漂移。build.py、custom.py、verify.py 共用这里。
"""

from __future__ import annotations

SURGE_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP",
    "PROCESS-NAME", "DEST-PORT", "SRC-PORT", "SRC-IP", "IN-PORT",
    "PROTOCOL", "USER-AGENT", "URL-REGEX", "HOSTNAME-TYPE",
    "AND", "OR", "NOT",
}  # fmt: skip

# 同义、只是类型名不同，可以直接改写
RENAME = {"DST-PORT": "DEST-PORT", "SRC-IP-CIDR": "SRC-IP"}

# mihomo 有而 Surge 没有（或写法不同）的类型，给出可操作的提示
HINT = {
    "DST-PORT": "Surge 写作 DEST-PORT",
    "SRC-IP-CIDR": "Surge 写作 SRC-IP",
    "DOMAIN-REGEX": "Surge 不支持",
    "PROCESS-PATH": "Surge 不支持",
    "NETWORK": "Surge 写作 PROTOCOL",
}


def line_problem(line: str) -> str | None:
    """Surge 会跳过这行时返回原因。DOMAIN-SET 的裸域名行（无逗号）不在此列。"""
    kind, sep, rest = line.partition(",")
    if not sep:
        return None
    if kind not in SURGE_TYPES:
        return HINT.get(kind, "Surge 不认的规则类型")
    value = rest.split(",", 1)[0]
    if kind == "IP-CIDR" and ":" in value:
        return "IPv6 须用 IP-CIDR6"
    if kind == "IP-CIDR6" and ":" not in value:
        return "IPv4 须用 IP-CIDR"
    return None


def problems(lines: list[str]) -> list[str]:
    return [f"{line}（{why}）" for line in lines if (why := line_problem(line))]


def to_surge(line: str) -> str | None:
    """mihomo / classical 写法 -> Surge 写法。Surge 表达不了的返回 None。

    改写：DST-PORT -> DEST-PORT、SRC-IP-CIDR -> SRC-IP，IP-CIDR 与 IP-CIDR6
    按地址族纠正（mihomo 两者都接受任一地址族，Surge 严格区分）。
    """
    kind, sep, rest = line.partition(",")
    if not sep:
        return line
    kind = RENAME.get(kind, kind)
    value = rest.split(",", 1)[0]
    if kind in ("IP-CIDR", "IP-CIDR6"):
        kind = "IP-CIDR6" if ":" in value else "IP-CIDR"
    out = f"{kind},{rest}"
    return None if line_problem(out) else out
