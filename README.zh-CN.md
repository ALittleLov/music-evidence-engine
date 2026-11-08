# Music Evidence Engine

[English](README.md) | [简体中文](README.zh-CN.md)

**独立于宿主、以 CPU 运行为主的本地音乐证据引擎。** 输入本地音频，输出可测量的声学特征、带时间位置的观察结果，以及便于 Agent 或其他程序使用的结构化报告。提供 Python CLI 与 API，**不依赖 DSH**。

音频在本机处理，不上传音频；首次安装依赖或获取缺失的可选模型时可能需要联网。

## 能做什么

- 速度/节拍估计、调性候选、响度、RMS 与能量走势
- 起音活动、频段特征、声学变化边界
- 人声活动、乐器候选、音乐标签与时间线观察
- 文本和 JSON 输出；区分直接测量与推断性观察
- 可选 Demucs 分轨及 Whisper 歌词听写

这些结果是**音乐证据**，不等同于乐器身份、严格曲式或音乐意义的确定答案。缺失模型时可能降级输出，而不是编造数据。

## 安装

包元数据要求 **Python 3.10+**；目前主要在 Windows 上开发和验证。不强制要求独立显卡。分析耗时与资源占用取决于 CPU、音频长度和所选功能。

从源码安装：

```bash
git clone https://github.com/ALittleLov/music-evidence-engine-public.git
cd music-evidence-engine-public
python -m pip install .
```

也可从 [最新 Engine Release](https://github.com/ALittleLov/music-evidence-engine-public/releases/latest) 下载 wheel，再用 pip 安装该文件。

按需安装可选依赖：

```bash
python -m pip install ".[stems]"
python -m pip install ".[asr]"
```

**Python 依赖不等于模型权重。** wheel 内置约 3.2 MB 的 MusicNN；YAMNet、Beat This、Demucs、Whisper 模型数据分别管理。来源、哈希与依赖参见 [`models.json`](src/music_evidence_engine/models.json)。单独安装基础 Python 包，不代表所有模型与扩展能力均已就绪。

## CLI

```bash
music-evidence-engine "track.flac"
music-evidence-engine "track.flac" --json
music-evidence-engine "track.flac" --json --brief
music-evidence-engine "track.flac" --bands
python -m music_evidence_engine "track.flac" --detail
```

还支持 `--start`、`--end`、`--blocks`、`--stems`、`--asr`、`--preview`、`--pitch` 等参数；分轨和听写需要对应依赖与模型。

## Python API

```python
from music_evidence_engine import analyze, EnginePaths, AnalysisError

result = analyze("track.flac", format="json")
print(result.keys())

paths = EnginePaths(
    resource_dir="models/yamnet",
    data_dir="data",
    cache_dir="cache/stems",
    model_dir="data/models/stems",
)
result = analyze("track.flac", paths=paths, brief=True)
```

`analyze()` 目前属于**过渡型进程内包装 API**：调用与 CLI 相同的 legacy 分析实现，捕获并解析 stdout，并非另一套原生分析算法。失败时抛出 `AnalysisError`。模型路径可显式指定，也支持 `MEE_*` 环境变量。

## 发行与接入

- [Engine 最新发行与制品](https://github.com/ALittleLov/music-evidence-engine-public/releases/latest)
- [dsh-soundcheck](https://github.com/ALittleLov/dsh-soundcheck)：独立维护的 DSH Bridge，负责插件安装、调用和界面
- [第三方许可说明](src/music_evidence_engine/THIRD_PARTY_NOTICES.md)

Engine 本身不提供 DSH UI 或长期运行的任务服务；调度、权限和展示由宿主实现。

## 限制与许可

声学变化切段不保证等同于正式曲式；乐器与和弦等结果具有候选性质。长时间高采样率音频的结构分析、部分可选 ASR 缓存仍有已知局限，Windows 以外的平台尚未充分验证。

MIT 许可；第三方模型与依赖许可见上述说明。
