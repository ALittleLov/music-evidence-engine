# -*- coding: utf-8 -*-
"""CLI：参数与 0.9.10 的 analyze.py 完全一致，由 legacy.main() 解析。"""
from __future__ import annotations

import sys
from typing import List, Optional

from .paths import EnginePaths
from .runtime import load_legacy


def main(argv: Optional[List[str]] = None) -> None:
    legacy = load_legacy(EnginePaths())
    if argv is not None:
        sys.argv = ["music-evidence-engine"] + [str(x) for x in argv]
    else:
        sys.argv[0] = "music-evidence-engine"
    legacy.main()
