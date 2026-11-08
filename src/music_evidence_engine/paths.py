# -*- coding: utf-8 -*-
"""宿主无关的路径解析。

优先级（从高到低）：
  1. 显式传入的 EnginePaths 字段
  2. 新环境变量 MEE_RESOURCE_DIR / MEE_DATA_DIR / MEE_CACHE_DIR /
     MEE_MODEL_DIR / MEE_HF_HOME / MEE_TMP_DIR
  3. 旧环境变量 DSH_AUDIO_DATA_DIR / DSH_AUDIO_CACHE_DIR / DSH_AUDIO_MODEL_DIR /
     HF_HOME（兼容 dsh-soundcheck 旧 Bridge）
  4. 旧布局探测（<data> 的同级 engine 目录）
  5. 用户目录 ~/.music-evidence-engine
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

RESOURCE_FILES = ("yamnet.onnx", "yamnet_class_map.csv", "musicnn.onnx")


def _expand(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return os.path.abspath(os.path.expanduser(str(value)))


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def package_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _has_any_resource(path: str) -> bool:
    return any(os.path.exists(os.path.join(path, name)) for name in RESOURCE_FILES)


def _walk_for(start: str, target: str, max_up: int = 5) -> Optional[str]:
    """从 start 向上找名为 target 的目录。"""
    cur = os.path.abspath(start)
    for _ in range(max_up):
        candidate = os.path.join(cur, target)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _detect_data_dir() -> str:
    found = _walk_for(package_dir(), "dsh-soundcheck-data")
    if found:
        return found
    return os.path.join(os.path.expanduser("~"), ".music-evidence-engine", "data")


def _candidate_resource_dirs(data_dir: str) -> List[str]:
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(package_dir(), "resources"),
        os.path.join(data_dir, "..", "dsh-soundcheck-plugin", "engine"),
        os.path.join(data_dir, "..", "engine"),
        os.path.join(data_dir, "models"),
        os.path.join(home, ".music-evidence-engine", "models"),
    ]
    # 开发机：从包目录向上找 engine/（例如 <repo>/engine）
    cur = package_dir()
    for _ in range(5):
        candidates.append(os.path.join(cur, "engine"))
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return candidates


def _detect_resource_dir(data_dir: str) -> Optional[str]:
    for candidate in _candidate_resource_dirs(data_dir):
        candidate = _expand(candidate)
        if candidate and _has_any_resource(candidate):
            return candidate
    return None


@dataclass
class EnginePaths:
    """显式目录配置；None 表示按环境变量/旧布局探测。"""

    resource_dir: Optional[str] = None
    data_dir: Optional[str] = None
    cache_dir: Optional[str] = None
    model_dir: Optional[str] = None
    hf_home: Optional[str] = None
    tmp_dir: Optional[str] = None

    def resolve(self) -> "ResolvedPaths":
        data_dir = (
            _expand(self.data_dir)
            or _expand(_first_env("MEE_DATA_DIR", "DSH_AUDIO_DATA_DIR"))
            or _detect_data_dir()
        )
        cache_dir = (
            _expand(self.cache_dir)
            or _expand(_first_env("MEE_CACHE_DIR", "DSH_AUDIO_CACHE_DIR"))
            or os.path.join(data_dir, "cache", "stems")
        )
        model_dir = (
            _expand(self.model_dir)
            or _expand(_first_env("MEE_MODEL_DIR", "DSH_AUDIO_MODEL_DIR"))
            or os.path.join(data_dir, "models", "stems")
        )
        hf_home = (
            _expand(self.hf_home)
            or _expand(_first_env("MEE_HF_HOME", "HF_HOME"))
            or os.path.join(data_dir, "hf_home")
        )
        tmp_dir = (
            _expand(self.tmp_dir)
            or _expand(_first_env("MEE_TMP_DIR"))
            or os.path.join(data_dir, "tmp")
        )
        resource_dir = (
            _expand(self.resource_dir)
            or _expand(_first_env("MEE_RESOURCE_DIR"))
            or _detect_resource_dir(data_dir)
        )

        def pick(name: str) -> str:
            if resource_dir:
                candidate = os.path.join(resource_dir, name)
                if os.path.exists(candidate):
                    return candidate
            # 兼容：模型被放在 data/models 或 data 根
            for base in (os.path.join(data_dir, "models"), data_dir):
                candidate = os.path.join(base, name)
                if os.path.exists(candidate):
                    return candidate
            # 随包的小型资源（如 musicnn.onnx），避免依赖外部下载
            builtin = os.path.join(package_dir(), "builtin", name)
            if os.path.exists(builtin):
                return builtin
            return os.path.join(resource_dir or data_dir, name)

        return ResolvedPaths(
            resource_dir=resource_dir,
            data_dir=data_dir,
            cache_dir=cache_dir,
            model_dir=model_dir,
            hf_home=hf_home,
            tmp_dir=tmp_dir,
            yamnet=pick("yamnet.onnx"),
            class_map=pick("yamnet_class_map.csv"),
            musicnn=pick("musicnn.onnx"),
        )


@dataclass
class ResolvedPaths:
    resource_dir: Optional[str]
    data_dir: str
    cache_dir: str
    model_dir: str
    hf_home: str
    tmp_dir: str
    yamnet: str
    class_map: str
    musicnn: str

    def missing_resources(self) -> List[str]:
        return [name for name in RESOURCE_FILES
                if not os.path.exists(os.path.join(self.resource_dir or "", name))]

    def describe(self) -> Dict[str, object]:
        return {
            "resource_dir": self.resource_dir,
            "data_dir": self.data_dir,
            "cache_dir": self.cache_dir,
            "model_dir": self.model_dir,
            "hf_home": self.hf_home,
            "tmp_dir": self.tmp_dir,
            "yamnet": self.yamnet,
            "class_map": self.class_map,
            "musicnn": self.musicnn,
            "missing_resources": self.missing_resources(),
        }


def resolve_paths(paths: Optional[EnginePaths] = None) -> ResolvedPaths:
    return (paths or EnginePaths()).resolve()
