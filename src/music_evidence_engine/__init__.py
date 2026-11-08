# -*- coding: utf-8 -*-
"""Music Evidence Engine。

import 本包不会加载 librosa / onnxruntime，也不会扫描音频或联网；
只有调用 analyze() 或 CLI 时才会加载 legacy 引擎。
"""
from .api import AnalysisError, analyze
from .paths import EnginePaths, ResolvedPaths, resolve_paths

__version__ = "0.1.1"

__all__ = [
    "analyze",
    "AnalysisError",
    "EnginePaths",
    "ResolvedPaths",
    "resolve_paths",
    "__version__",
]
