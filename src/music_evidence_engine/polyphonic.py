"""Optional local polyphonic note evidence (experimental).

The decoder and overlap-add inference adapt dettato's transcriber.
Upstream: https://github.com/kobimusic/dettato (Apache-2.0).
No automatic downloads, audio uploads, instrument or voice assignments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version, PackageNotFoundError
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SR = 16000
N_KEYS = 88
PITCH_LO = 21
HEADS = ("onset", "frame", "offset", "onset2", "frame2", "offset2")
SCHEMA = "polyphonic-notes/v1"
ALGORITHM = "dettato-static8-hann-v1"
MODEL_HASHES = {
    "hcqt.onnx": "de5cab8ae9f7b0f7a27be2eca8ca0da76f067d9b719c8af1b67d3d3d04048de5",
    "lanenet_body.onnx": "11da0b203b78e3061ee4ba4a1b86304747f376a1e2fc217f7060d206eec4c626",
}
NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

class PolyphonicError(RuntimeError):
    pass

def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _verify_models(directory):
    root = Path(directory)
    for name, expected in MODEL_HASHES.items():
        p = root / name
        if not p.is_file():
            raise PolyphonicError(f"Optional model missing: {name}")
        if _sha(p) != expected:
            raise PolyphonicError(f"Model checksum mismatch: {name}")
    return dict(MODEL_HASHES)

def _validate(start, end, threads, timeout):
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("Expected 0 <= start < end (seconds)")
    if type(threads) is not int or not 1 <= threads <= 32:
        raise ValueError("threads must be an integer from 1 to 32")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")

def _peaks(p, th):
    import numpy as np
    left = np.vstack([np.full((1, p.shape[1]), -1.0), p[:-1]])
    right = np.vstack([p[1:], np.full((1, p.shape[1]), -1.0)])
    return (p >= th) & (p > left) & (p >= right)


def _refine(p, t, l):
    import numpy as np
    T = p.shape[0]
    C = p[t, l]
    A = p[t - 1, l] if t > 0 else C
    Bv = p[t + 1, l] if t + 1 < T else C
    den = 2 * (C - min(A, Bv))
    if den <= 1e-6:
        return 0.0
    return float(np.clip((Bv - A) / den, -0.5, 0.5))


def decode(onset, frame, offset, hop, on_th, off_th, fr_th, fr_low_frames, on_nms, min_dur=0.02, off_min_frames=2):
    import numpy as np
    on, fr, off = onset, frame, offset
    T, L = on.shape
    pk_on = _peaks(on, on_th)
    pk_off = _peaks(off, off_th)
    low = fr < fr_th
    run = low.copy()
    for k in range(1, fr_low_frames):
        run[:T - k] &= low[k:]
    notes = []
    for l in range(L):
        ons = np.nonzero(pk_on[:, l])[0]
        if len(ons) == 0:
            continue
        if on_nms > 0 and len(ons) > 1:
            keep = np.ones(len(ons), bool)
            for oi in np.argsort(-on[ons, l]):
                if not keep[oi]:
                    continue
                close = np.abs(ons - ons[oi]) <= on_nms
                close[oi] = False
                keep &= ~close
            ons = ons[keep]
        offs = np.nonzero(pk_off[:, l])[0]
        lows = np.nonzero(run[:, l])[0]
        for i, t0 in enumerate(ons):
            u0 = t0 + _refine(on, t0, l)
            nxt = ons[i + 1] if i + 1 < len(ons) else T
            j = np.searchsorted(lows, t0 + 1)
            e_fr = lows[j] if j < len(lows) else T
            j = np.searchsorted(offs, t0 + off_min_frames)
            e_off = offs[j] if j < len(offs) else T
            if e_off < T and e_off <= min(e_fr, nxt):
                u1 = e_off + _refine(off, e_off, l)
            elif e_fr <= nxt:
                u1 = e_fr - 0.5
            else:
                u1 = nxt + (_refine(on, nxt, l) if nxt < T else 0.0)
            on_s, off_s = u0 * hop, max(u1 * hop, u0 * hop + min_dur)
            notes.append((on_s, off_s, PITCH_LO + l))
    notes.sort()
    return notes


def _run(audio, models, start, end, threads):
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    _verify_models(models)
    with sf.SoundFile(audio) as f:
        rate = f.samplerate
        begin = round(start * rate)
        finish = min(len(f), round(end * rate)) if end is not None else len(f)
        if begin >= finish:
            raise PolyphonicError("Selected interval is empty or outside audio")
        f.seek(begin)
        x = f.read(finish - begin, dtype="float32", always_2d=True).mean(1)
    if rate != SR:
        try:
            import soxr
        except ImportError as exc:
            raise PolyphonicError("Install soxr for non-16 kHz audio") from exc
        x = soxr.resample(x, rate, SR, quality="HQ").astype(np.float32)
    if not len(x) or not np.isfinite(x).all():
        raise PolyphonicError("Empty or non-finite audio")
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    hcqt = ort.InferenceSession(str(Path(models) / "hcqt.onnx"), options, providers=["CPUExecutionProvider"])
    body = ort.InferenceSession(str(Path(models) / "lanenet_body.onnx"), options, providers=["CPUExecutionProvider"])
    W, Fw, step, pad = 128000, 400, 32000, 64000
    n = len(x)
    T = math.ceil(n / 320)
    w = np.hanning(Fw + 2)[1:-1].astype(np.float32)
    padded = np.pad(x, (pad, pad + W))
    P = np.zeros((6, T, N_KEYS), np.float32)
    wsum = np.zeros(T, np.float32)
    for s0 in range(0, n + pad, step):
        g0 = s0 // 320 - 200
        a, b = max(0, g0), min(T, g0 + Fw)
        if b <= a:
            continue
        spec = hcqt.run(None, {"audio": padded[s0:s0 + W][None, :]})[0]
        # oqlofc16
        outputs = body.run(list(HEADS), {"spectrogram": spec})
        wt = w[a-g0:b-g0]
        for k, output in enumerate(outputs):
            if output.shape != (1, Fw, N_KEYS) or not np.isfinite(output).all():
                raise PolyphonicError("Unexpected or non-finite ONNX head")
            with np.errstate(over="ignore"):
                P[k, a:b] += (1.0 / (1.0 + np.exp(-output[0, a-g0:b-g0]))) * wt[:, None]
        wsum[a:b] += wt
    P /= np.maximum(wsum, 1e-6)[None, :, None]
    rows = []
    origin = begin / rate
    for slot, k, th in ((1, 0, .25), (2, 3, .3)):
        for u0, u1, pitch in decode(P[k], P[k+1], P[k+2], .02, th, .3, .4, 2, 3):
            t = min(max(round(u0 / .02), 0), T-1)
            rows.append(dict(onset=float(u0 + origin), offset=float(u1 + origin), pitch=int(pitch),
                             conf=float(P[k,t,pitch-PITCH_LO]), slot=slot))
    rows.sort(key=lambda r: (r["onset"], r["offset"], r["pitch"]))
    return {"schema": SCHEMA, "algorithm": ALGORITHM, "interval": [origin, finish/rate],
            "boundary_note": "Interval inference has independent padding; edge notes and durations may differ from full-file inference.",
            "notes_json": rows, "diagnostics": summarize(rows)}


def _ordered(rows):
    clean = []
    for r in rows:
        a, b, p = r["onset"], r["offset"], r["pitch"]
        if not (math.isfinite(a) and math.isfinite(b) and b > a and type(p) is int and 0 <= p <= 127):
            raise ValueError("Invalid note event")
        clean.append(dict(r))
    return sorted(clean, key=lambda r: (r["onset"], r["offset"], r["pitch"]))


def summarize(rows):
    rows = _ordered(rows)
    groups = duplicates = octaves = 0
    anchor = -math.inf
    for i, a in enumerate(rows):
        if a["onset"] - anchor > .03:
            groups += 1
            anchor = a["onset"]
        for j in range(i+1, len(rows)):
            b = rows[j]
            dt = b["onset"] - a["onset"]
            if dt > .12:
                break
            dp = abs(a["pitch"]-b["pitch"])
            duplicates += int(dp == 0 and dt <= .03)
            octaves += int(dp == 12)
    return {"detected_note_events": len(rows), "onset_groups_30ms": groups,
            "suspected_duplicate_pairs_30ms": duplicates, "octave_candidate_pairs_120ms": octaves,
            "pitch_range": [min(r["pitch"] for r in rows), max(r["pitch"] for r in rows)] if rows else None,
            "limitations": ["Detection count is not a performed-note count.",
                            "Pairs are candidates, not verified errors or octave doubling; no events deleted.",
                            "Slot is not voice or instrument identity; no chord-function inference."]}


def query(result, start, end):
    _validate(start, end, 1, 1)
    if end is None:
        raise ValueError("query requires end")
    lo, hi = result["interval"]
    if start < lo or end > hi:
        raise ValueError("Query lies outside analyzed interval")
    rows = _ordered(result["notes_json"])
    return [dict(r, id=f"N{i+1:06d}", name=NAMES[r["pitch"]%12]+str(r["pitch"]//12-1),
                 duration=r["offset"]-r["onset"])
            for i,r in enumerate(rows) if r["onset"] < end and r["offset"] > start]


def _cache_key(audio_hash, model_hashes, start, end, threads):
    versions = {}
    for name in ("numpy", "onnxruntime", "soundfile", "soxr"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    config = [SCHEMA, ALGORITHM, audio_hash, model_hashes, start, end, threads, versions]
    return hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".notes-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def analyze_notes(audio, model_dir, *, start=0.0, end=None, threads=4, timeout=900.0, cache_dir=None):
    """Opt-in CPU analysis with isolated inference and explicit local models.

    No persistent cache unless cache_dir is supplied. It contains note data,
    not raw audio or audio filenames. The timeout covers the worker process.
    """
    start = float(start)
    end = float(end) if end is not None else None
    _validate(start, end, threads, timeout)
    audio, model_dir = Path(audio).resolve(), Path(model_dir).resolve()
    hashes = _verify_models(model_dir)
    key = _cache_key(_sha(audio), hashes, start, end, threads)
    cached = Path(cache_dir) / (key + ".json") if cache_dir is not None else None
    if cached is not None and cached.is_file():
        try:
            result = json.loads(cached.read_text(encoding="utf-8"))
            if result.get("cache_key") == key and result.get("schema") == SCHEMA:
                _ordered(result["notes_json"])
                return dict(result, cache_hit=True)
        except (ValueError, KeyError, TypeError, OSError):
            pass
    args = [sys.executable, "-m", __name__ if __name__ != "__main__" else "music_evidence_engine.polyphonic",
            str(audio), "--models", str(model_dir), "--start", str(start), "--threads", str(threads), "--worker"]
    if end is not None:
        args.extend(["--end", str(end)])
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise PolyphonicError("Polyphonic inference timed out") from exc
    if proc.returncode:
        raise PolyphonicError("Polyphonic worker failed (check model/runtime availability and input format)")
    try:
        result = json.loads(proc.stdout)
        if result.get("schema") != SCHEMA:
            raise ValueError("schema mismatch")
        _ordered(result["notes_json"])
    except (ValueError, KeyError, TypeError) as exc:
        raise PolyphonicError("Invalid worker output") from exc
    # 77ql3hsw
    if key != _cache_key(_sha(audio), _verify_models(model_dir), start, end, threads):
        raise PolyphonicError("Input or models changed during inference")
    result.update(cache_key=key, cache_hit=False)
    if cached is not None:
        _atomic_json(cached, result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Optional local polyphonic note evidence")
    p.add_argument("audio")
    p.add_argument("--models", required=True)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--timeout", type=float, default=900)
    p.add_argument("--cache-dir")
    p.add_argument("--query", nargs=2, type=float)
    p.add_argument("--check", action="store_true")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    try:
        _validate(a.start, a.end, a.threads, a.timeout)
        if a.worker:
            result = _run(a.audio, a.models, a.start, a.end, a.threads)
        else:
            result = analyze_notes(a.audio, a.models, start=a.start, end=a.end, threads=a.threads,
                                   timeout=a.timeout, cache_dir=a.cache_dir)
        if a.query:
            result = {"interval": result["interval"], "notes": query(result,*a.query)}
        elif a.check:
            result = {"interval": result["interval"], "diagnostics": result["diagnostics"]}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, ImportError, PolyphonicError) as exc:
        # 99492p0d
        print(str(exc) if isinstance(exc, PolyphonicError) else type(exc).__name__, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
