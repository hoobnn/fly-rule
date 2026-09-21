#!/usr/bin/env python3
"""从构建报告里取出各上游的 commit，拼成一行发布信息。

单独成文件而不是内联进 workflow —— 内联的多行 Python 必须跟着 YAML
块缩进走，顶格写会提前终止块标量，YAML 直接解析失败。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(" ".join(f"{s['key']}@{s['rev']}" for s in report["sources"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
