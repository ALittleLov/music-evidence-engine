# Music Evidence Engine

[English](README.md) | [简体中文](README.zh-CN.md)

**A host-independent, CPU-friendly audio evidence engine.** Analyze local music files and obtain measurable features, time-localized observations, and structured outputs that an Agent or another application can inspect. It is a Python package with a CLI and API; **DSH is not required**.

Audio is processed locally, with no audio upload. Installation and missing optional model weights may require network downloads.

## What it provides

- Tempo / beat estimates, key candidates, loudness, RMS and energy trends
- Onset activity, spectral bands and acoustic change boundaries
- Vocal activity, instrument candidates, music tags and time-based observations
- Text and JSON reports; explicit distinction between measurements and inferred observations
- Optional Demucs-based stem separation and Whisper-based lyric transcription

These are **pieces of evidence**, not ground-truth instrument identities, exact song form, or proof of musical meaning. Missing models may cause a reduced result rather than fabricated measurements.

## Installation

**Python 3.10+** is declared in package metadata; development and integration have primarily been validated on Windows. No dedicated GPU is required. CPU time and memory use depend on task and audio length.

Use the source repository:

```bash
git clone https://github.com/ALittleLov/music-evidence-engine.git
cd music-evidence-engine
python -m pip install .
```

Or obtain the built wheel from the [latest Engine release](https://github.com/ALittleLov/music-evidence-engine/releases/latest) and install that wheel with pip.

Optional Python dependencies, when needed:

```bash
python -m pip install ".[stems]"
python -m pip install ".[asr]"
```

**Model files are separate from Python dependencies.** The wheel bundles MusicNN (approximately 3.2 MB); YAMNet, Beat This, Demucs and Whisper model data are managed separately. Refer to [`models.json`](src/music_evidence_engine/models.json) for sources, checksums and requirements. Installing the bare Python package does not mean all analyses and optional models are ready.

## CLI

```bash
music-evidence-engine "track.flac"
music-evidence-engine "track.flac" --json
music-evidence-engine "track.flac" --json --brief
music-evidence-engine "track.flac" --bands
python -m music_evidence_engine "track.flac" --detail
```

Additional options include `--start`, `--end`, `--blocks`, `--stems`, `--asr`, `--preview` and `--pitch`. Use the appropriate model files and dependencies for the requested analysis.

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

`analyze()` is currently a **transitional in-process wrapper** around the same legacy analysis implementation used by the CLI; it captures and parses stdout. It is not a separate native API algorithm. Failures raise `AnalysisError`. Paths can be provided explicitly or via `MEE_*` environment variables.

## Time-resolved pitch contour (experimental, off by default)

Extracts a 0.5 s-resolution pyin F0 contour from a **single target track**. Disabled by default; requires an explicit `--pitch-track`.

```bash
music-evidence-engine track.flac --pitch-track --pitch-detail \
    --pitch-source isolated_track --pitch-role melody --json
```

| Flag | Values | Meaning |
|---|---|---|
| `--pitch-track` | switch | Treat the input file itself as one target voice and emit a time-resolved contour. **Do not use on a full mix** — that is "one strong line", not a melody. Cannot be combined with `--stems`. |
| `--pitch-detail` | switch | With `--pitch-track`: also emit the full 0.5 s contour series. |
| `--pitch-source` | `isolated_track` \| `mixture` \| `unknown` | Caller-declared input kind. `mixture` explicitly marks the result as not usable as a target melody. |
| `--pitch-role` | `melody` \| `vocal` \| `instrument` \| `bass` \| `accompaniment` \| `unknown` | Caller-declared role. **Metadata only**; the engine does not verify it. |

Output fields added inside a `pitch_track` object: `series` (relative, per-window normalised), `absolute_series` (`[time, Hz, MIDI]` triples with `--pitch-detail`; absolute pitch on the same axis and aggregation as `series`), plus `span`/`span_note`, `trend`/`trend_note`, `turns`, `voiced_ratio`, `voiced_gaps`, `octave_suspect_*`, `mixture_risk`, `source_declared`.

**Known limitations**

- `span` is the robust **P90−P10** spread, **not** the pitch range; it can be smaller than the peak-to-peak amplitude listed under `turns`.
- `trend` is a **net change**, not a claim of monotonic rise or fall.
- Relative `series` values **cannot be compared as absolute intervals across independent windows** (each window is normalised on its own).
- F0 on mixes, multi-voice or complex audio **may be unreliable**. Declaring `mixture` sets `mixture_risk=high` and `usable_as_target_melody=false`. **No claim of solved full melody transcription.**
- pyin may jump octaves or lose lock; `octave_suspect_at` / `voiced_gaps` flag candidates, not guarantees.
- The feature does **not** separate stems; the correct usage is to isolate the target voice first.

## Distribution and integration

- [Engine releases and versioned assets](https://github.com/ALittleLov/music-evidence-engine/releases/latest)
- [dsh-soundcheck](https://github.com/ALittleLov/dsh-soundcheck) — the separate DSH Bridge, with its own installation and update UI
- [Third-party notices](src/music_evidence_engine/THIRD_PARTY_NOTICES.md)

The Engine does not provide its own long-running job service or DSH interface. Host applications manage task scheduling, user permissions and presentation.

## Limitations and license

Acoustic segmentation does not guarantee formal song sections; instrument and chord outputs are candidates. Some known limitations remain in long high-sample-rate files and optional ASR caching. Cross-platform behavior beyond the Windows-focused validation is not guaranteed.

MIT license. Third-party model and dependency licenses are listed in the notices above.
