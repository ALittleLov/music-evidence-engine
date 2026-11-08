# -*- coding: utf-8 -*-
"""加载 legacy 引擎并做资源适配。

legacy/analyze.py 保持原样，不修改任何算法、阈值或输出代码。
本模块只做两件事：
  1. 把解析出的目录写进旧引擎认识的环境变量（DSH_AUDIO_*）；
  2. 把模块级三个模型常量指向解析出的资源文件。
"""
from __future__ import annotations

import importlib
import os
from typing import Optional

from .paths import EnginePaths, ResolvedPaths

_legacy = None
_loaded_paths: Optional[ResolvedPaths] = None


def _apply_env(paths: ResolvedPaths, explicit_tmp: bool, explicit_hf: bool = False) -> None:
    os.environ["DSH_AUDIO_DATA_DIR"] = paths.data_dir
    os.environ["DSH_AUDIO_CACHE_DIR"] = paths.cache_dir
    os.environ["DSH_AUDIO_MODEL_DIR"] = paths.model_dir
    # 显式解析的 HF_HOME（MEE_HF_HOME / EnginePaths.hf_home）优先；
    # 只有没显式给的时候才尊重进程已有的 HF_HOME。
    if explicit_hf:
        os.environ["HF_HOME"] = paths.hf_home
    else:
        os.environ.setdefault("HF_HOME", paths.hf_home)
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    if explicit_tmp:
        os.environ["TEMP"] = paths.tmp_dir
        os.environ["TMP"] = paths.tmp_dir
        os.environ["TMPDIR"] = paths.tmp_dir
        os.makedirs(paths.tmp_dir, exist_ok=True)


def load_legacy(paths: Optional[EnginePaths] = None):
    """返回已适配资源的 legacy.analyze 模块（只 import 一次）。"""
    global _legacy, _loaded_paths

    resolved = (paths or EnginePaths()).resolve()
    explicit_tmp = bool((paths and paths.tmp_dir) or os.environ.get("MEE_TMP_DIR"))
    explicit_hf = bool((paths and paths.hf_home) or os.environ.get("MEE_HF_HOME"))
    _apply_env(resolved, explicit_tmp, explicit_hf)

    if _legacy is None:
        _legacy = importlib.import_module("music_evidence_engine.legacy.analyze")

    _legacy.YAMNET_MODEL = resolved.yamnet
    _legacy.YAMNET_CLASSES = resolved.class_map
    _legacy.MUSICNN_MODEL = resolved.musicnn
    _loaded_paths = resolved
    return _legacy


def loaded_paths() -> Optional[ResolvedPaths]:
    return _loaded_paths
