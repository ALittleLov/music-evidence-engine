# Music Evidence Engine

一个本地运行、不依赖宿主的音频证据引擎（Python 包）。输入一首本地音频，输出速度、调性、响度、结构变化、音色与乐器方向的证据报告。

音频不出本机。基础分析在本地完成；模型缺失时按降级规则处理，不会伪造证据。

## 特性

- 本地分析：BPM、调性、响度、能量走势、结构变化、标签、乐器方向、时间线
- 文本与 JSON 两种输出；结论、测量与推断分栏
- 可选组件：分轨（`demucs-onnx`）、歌词听写（`faster-whisper`）
- 可作为 CLI 使用，也可作为 Python 包调用
- 不依赖任何宿主运行时

## 安装

```sh
python -m pip install .
```

基础分析依赖 `numpy / librosa / scipy / onnxruntime`。可选组件：

```sh
python -m pip install "music-evidence-engine[stems]"   # demucs-onnx + soundfile + soxr
python -m pip install "music-evidence-engine[asr]"     # faster-whisper
```

要求 Python 3.10+；当前主要在 Windows 上验证。

## CLI

```sh
music-evidence-engine "a.flac" --json          # 完整 JSON
music-evidence-engine "a.flac" --json --brief  # 结论级 brief JSON
music-evidence-engine "a.flac"                 # 默认文本
music-evidence-engine "a.flac" --detail        # 详细文本
music-evidence-engine "a.flac" --bands         # 分频诊断
python -m music_evidence_engine "a.flac"       # 模块入口，效果相同
```

参数：`--blocks`、`--chord-block`、`--start`、`--end`、`--json`、`--brief`、
`--detail`、`--stems`、`--asr`、`--preview-asr`、`--preview`、`--bands`、`--pitch`。

## Python API

```python
from music_evidence_engine import analyze

result = analyze("a.flac", format="json")
print(result["summary"]["bpm"])

brief = analyze("a.flac", brief=True)
text = analyze("a.flac", format="text")["text"]
```

当前 API 是**进程内包装**：内部调用同一份分析脚本并解析其 stdout，不是原生
in-process 实现。错误通过 `AnalysisError`（带 `exit_code` / `stdout`）传播。

### 显式路径

```python
from music_evidence_engine import EnginePaths, analyze

paths = EnginePaths(
    resource_dir="models/yamnet",   # yamnet.onnx / musicnn.onnx / yamnet_class_map.csv
    data_dir="data",                # beat_this / whisper / hf_home
    cache_dir="cache/stems",
    model_dir="data/models/stems",  # htdemucs 权重
)
result = analyze("a.flac", paths=paths)
```

`EnginePaths` 中为 `None` 的字段按以下优先级补全：

1. 显式字段
2. `MEE_RESOURCE_DIR` / `MEE_DATA_DIR` / `MEE_CACHE_DIR` / `MEE_MODEL_DIR` / `MEE_HF_HOME` / `MEE_TMP_DIR`
3. 旧 `DSH_AUDIO_DATA_DIR` / `DSH_AUDIO_CACHE_DIR` / `DSH_AUDIO_MODEL_DIR` / `HF_HOME`
4. 旧布局探测
5. `~/.music-evidence-engine`

## 模型与数据

wheel **不包含**模型权重，也不包含音频样本。基础分析（不请求 `--stems` / `--asr`）
在本地完成：YAMNet/MusicNN 缺失时静默降级，Beat This 缺失时回退 librosa。

分轨/听写在本地找不到权重时，运行时可能尝试从 Hugging Face 下载（受
`HF_HUB_OFFLINE` 与网络影响）；下载失败时返回 `available=false`。
安装阶段（pip 拉依赖、获取模型/组件）需要网络；音频解码与基础分析本身在本地完成。

模型目录约定：

```
<resource_dir>/yamnet.onnx + musicnn.onnx + yamnet_class_map.csv
<data_dir>/models/beat_this/beat-this-final0.onnx + frontend.json
<data_dir>/models/stems/htdemucs_fp16weights.onnx / htdemucs_6s_fp16weights.onnx
<data_dir>/whisper/<tiny|base|small>/...
```

## 已知限制

- 96 kHz 长文件的结构切段属于既有行为，本版本不调整。
- ASR 人声缓存的读取在某些情况下不生效。
- 当前按 Windows 路径/进程语义验证；未做跨平台验证。
- 不提供异步/后台任务；由调用方负责。
- 输出 JSON 字段保持稳定，未新增契约。

## 许可

MIT，见 `LICENSE`。第三方依赖与模型的许可见 `src/music_evidence_engine/THIRD_PARTY_NOTICES.md`。
