#!/usr/bin/env python3
"""上游回归门禁：拿本次构建和上一次发布的产物比，异常缩水就拦下。

我们忠实同步 MetaCubeX，上游出问题（类别被删、内容被清空、仓库被投毒）
会直接传导到产物。这个门禁在发布前拦一道：

- 类别整体消失
- 单个类别条数暴跌
- 总条数暴跌

误报时用 --allow-shrink 放行（上游确实做了大改动的情况）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 上一次发布的报告，从 release 分支取
BASELINE_URL = "https://raw.githubusercontent.com/{repo}/release/build-report.json"


def load_baseline(repo: str, path: Path | None) -> dict | None:
    if path:
        if not path.is_file():
            print(f"基线文件不存在: {path}", file=sys.stderr)
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    url = BASELINE_URL.format(repo=repo)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("release 分支还没有产物，跳过回归检查（首次发布）")
            return None
        print(f"拉取基线失败: {e}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"拉取基线失败: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--repo", default="", help="owner/name，用于拉取 release 基线")
    ap.add_argument("--baseline", type=Path, help="本地基线文件，优先于 --repo")
    ap.add_argument(
        "--max-drop",
        type=float,
        default=0.50,
        help="单类别 / 总量允许的最大缩水比例，默认 50%%",
    )
    ap.add_argument(
        "--min-rules",
        type=int,
        default=5,
        help="小于该条数的类别不做比例检查，避免噪声",
    )
    ap.add_argument("--allow-shrink", action="store_true", help="上游确有大改动时放行")
    a = ap.parse_args()

    report = json.loads((a.dist / "build-report.json").read_text(encoding="utf-8"))
    if not a.repo and not a.baseline:
        print("未指定 --repo / --baseline，跳过回归检查")
        return 0

    base = load_baseline(a.repo, a.baseline)
    if base is None:
        return 0

    def flatten(rep: dict) -> dict[str, int]:
        """展平成 {上游/数据集/类别: 条数}，兼顾多上游多数据集。"""
        out: dict[str, int] = {}
        for s in rep.get("sources", []):
            for d in s.get("datasets", []):
                prefix = f"{s['key']}/{d['dataset']}"
                for r in d.get("rulesets", []):
                    out[f"{prefix}/{r['category']}"] = r["rules"]
                # 纯镜像数据集按文件数计
                files = (d.get("mirrored") or {}).get("files")
                if files:
                    out[f"{prefix}/(mirror)"] = files
        return out

    now = flatten(report)
    old = flatten(base)

    problems: list[str] = []

    # 1. 整类消失
    gone = sorted(set(old) - set(now))
    if gone:
        problems.append(
            f"{len(gone)} 个类别消失: {', '.join(gone[:10])}"
            + (" …" if len(gone) > 10 else "")
        )

    # 2. 单类别暴跌
    shrunk = []
    for cat, was in old.items():
        if cat not in now or was < a.min_rules:
            continue
        drop = (was - now[cat]) / was
        if drop > a.max_drop:
            shrunk.append(f"{cat} {was}->{now[cat]} (-{drop * 100:.0f}%)")
    if shrunk:
        shrunk.sort()
        problems.append(
            f"{len(shrunk)} 个类别条数暴跌: {'; '.join(shrunk[:10])}"
            + (" …" if len(shrunk) > 10 else "")
        )

    # 3. 总量暴跌
    was_total = base.get("total_rules", 0)
    now_total = report.get("total_rules", 0)
    if was_total:
        drop = (was_total - now_total) / was_total
        if drop > a.max_drop:
            problems.append(f"总条数暴跌 {was_total}->{now_total} (-{drop * 100:.0f}%)")

    added = sorted(set(now) - set(old))
    print(
        f"回归检查：基线 {len(old)} 类 / {was_total} 条，"
        f"本次 {len(now)} 类 / {now_total} 条"
        + (f"，新增 {len(added)} 类" if added else "")
    )

    if not problems:
        print("通过：未发现异常缩水")
        return 0

    print("\n上游疑似异常:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)

    if a.allow_shrink:
        print("\n--allow-shrink 已指定，放行", file=sys.stderr)
        return 0
    print(
        "\n已拦截发布。确认上游确实做了这些改动后，重跑并加 --allow-shrink 放行。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
