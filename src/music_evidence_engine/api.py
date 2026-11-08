# -*- coding: utf-8 -*-
"""过渡型 Python API。

这是**进程内包装**：调用 legacy.main()，捕获它写到 stdout 的报告，再解析成 dict。
它不是“原生 in-process API”，也没有新增第二条算法路径；算法仍然只有 legacy/analyze.py 一份。
开销与限制见 README。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from typing import Any, Dict, List, Optional, Union

from .paths import EnginePaths
from .runtime import load_legacy


class AnalysisError(RuntimeError):
    def __init__(self, message: str, *, exit_code: Optional[int] = None,
                 stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


def _parse_json_output(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兼容：缺可选组件时，引擎可能先往 stdout 打一行「[分轨] 未启用」，再输出 JSON。
    idx = text.find("{")
    while idx != -1:
        try:
            return json.loads(text[idx:])
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
    raise AnalysisError("engine stdout is not valid JSON", stdout=text)


def _build_argv(
    path: str,
    *,
    format: str,
    brief: bool,
    detail: bool,
    start: Optional[Union[int, float, str]],
    end: Optional[Union[int, float, str]],
    blocks: Optional[float],
    stems: Optional[str],
    asr: Optional[str],
    preview: Optional[Union[bool, int, float]],
    preview_asr: Optional[str],
    pitch: bool,
    chord_block: Optional[float],
    argv_extra: Optional[List[str]],
) -> List[str]:
    argv: List[str] = [path]
    if format == "json":
        argv.append("--json")
    if brief:
        argv.append("--brief")
    if detail:
        argv.append("--detail")
    if start is not None:
        argv += ["--start", str(start)]
    if end is not None:
        argv += ["--end", str(end)]
    if blocks is not None:
        argv += ["--blocks", str(blocks)]
    if chord_block is not None:
        argv += ["--chord-block", str(chord_block)]
    if stems:
        argv += ["--stems", str(stems)]
    if asr:
        argv += ["--asr", str(asr)]
    if preview_asr:
        argv += ["--preview-asr", str(preview_asr)]
    if pitch:
        argv.append("--pitch")
    if preview is True:
        argv.append("--preview")
    elif isinstance(preview, (int, float)) and not isinstance(preview, bool):
        # bool 是 int 的子类：preview=False 不能被当成数字 0 拼出 "--preview False"。
        argv += ["--preview", str(preview)]
    if argv_extra:
        argv += [str(x) for x in argv_extra]
    return argv


def analyze(
    path: str,
    *,
    format: str = "json",
    brief: bool = False,
    detail: bool = False,
    start: Optional[Union[int, float, str]] = None,
    end: Optional[Union[int, float, str]] = None,
    blocks: Optional[float] = None,
    stems: Optional[str] = None,
    asr: Optional[str] = None,
    preview: Optional[Union[bool, int, float]] = None,
    preview_asr: Optional[str] = None,
    pitch: bool = False,
    chord_block: Optional[float] = None,
    paths: Optional[EnginePaths] = None,
    argv_extra: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """分析一个本地音频文件。

    format="json"（默认）返回解析后的 dict；format="text" 返回 {"text": str}。
    失败时抛 AnalysisError（含 exit_code 与已产生的 stdout）。
    """
    if format not in ("json", "text"):
        raise ValueError("format must be 'json' or 'text'")

    legacy = load_legacy(paths)
    argv = _build_argv(
        str(path), format=format, brief=brief, detail=detail, start=start, end=end,
        blocks=blocks, stems=stems, asr=asr, preview=preview,
        preview_asr=preview_asr, pitch=pitch, chord_block=chord_block,
        argv_extra=argv_extra,
    )

    old_argv = sys.argv
    buf = io.StringIO()
    sys.argv = ["music-evidence-engine"] + argv
    try:
        with contextlib.redirect_stdout(buf):
            legacy.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            pass
        else:
            raise AnalysisError(f"engine exited with {code}", exit_code=code,
                                stdout=buf.getvalue()) from exc
    finally:
        sys.argv = old_argv

    text = buf.getvalue()
    if format == "json":
        return _parse_json_output(text)
    return {"text": text}
