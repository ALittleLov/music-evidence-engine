import hashlib
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from music_evidence_engine import polyphonic as p


def row(a, b, pitch):
    return dict(onset=a, offset=b, pitch=pitch, conf=.8, slot=1)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / 'a.wav'
        self.audio.write_bytes(b'fake audio')
        self.models = self.root / 'models'
        self.models.mkdir()
        hashes = {}
        for name in p.MODEL_HASHES:
            f = self.models / name
            f.write_bytes(name.encode())
            hashes[name] = hashlib.sha256(name.encode()).hexdigest()
        self.addCleanup(patch.stopall)
        patch.object(p, 'MODEL_HASHES', hashes).start()
        self.result = dict(schema=p.SCHEMA, interval=[0, 2], notes_json=[row(.1,.8,60)], diagnostics={})

    def worker(self):
        return patch.object(p.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(self.result).encode()))

    def test_empty(self):
        self.assertEqual(p.summarize([])['detected_note_events'], 0)
        self.assertIsNone(p.summarize([])['pitch_range'])

    def test_pairs_retained(self):
        rows = [row(0,.5,60), row(.02,.5,60), row(.1,.4,72)]
        s = p.summarize(rows)
        self.assertEqual((s['detected_note_events'],s['onset_groups_30ms'],s['suspected_duplicate_pairs_30ms'],s['octave_candidate_pairs_120ms']), (3,2,1,2))

    def test_query_overlap_and_names(self):
        result = dict(interval=[0,2],notes_json=[row(0,.5,60),row(.5,1,56),row(1,2,72)])
        got = p.query(result,.5,1)
        self.assertEqual([r['name'] for r in got],['G#3'])
        self.assertEqual(got[0]['id'],'N000002')
        self.assertEqual(got[0]['duration'],.5)

    def test_query_bounds(self):
        with self.assertRaises(ValueError): p.query(self.result,1,3)

    def test_invalid(self):
        for start,end in [(float('nan'),1),(1,1),(-1,2),(0,float('inf'))]:
            with self.subTest(start=start,end=end), self.assertRaises(ValueError): p._validate(start,end,4,9)
        with self.assertRaises(ValueError): p.summarize([row(0,0,60)])

    def test_model_integrity(self):
        (self.models/'hcqt.onnx').write_bytes(b'bad')
        with self.assertRaisesRegex(p.PolyphonicError,'checksum'): p._verify_models(self.models)
        (self.models/'hcqt.onnx').unlink()
        with self.assertRaisesRegex(p.PolyphonicError,'missing'): p._verify_models(self.models)

    def test_opt_in_cache(self):
        cache = self.root/'cache'
        with self.worker() as run:
            a = p.analyze_notes(self.audio,self.models,cache_dir=cache)
            b = p.analyze_notes(self.audio,self.models,cache_dir=cache)
            self.assertFalse(a['cache_hit']); self.assertTrue(b['cache_hit'])
            self.assertEqual(run.call_count,1)
            self.assertEqual(a['notes_json'],b['notes_json'])
            self.assertNotIn(str(self.root), next(cache.glob('*.json')).read_text())

    def test_cache_invalidation(self):
        with self.worker() as run:
            opts = dict(cache_dir=self.root/'cache')
            p.analyze_notes(self.audio,self.models,**opts)
            p.analyze_notes(self.audio,self.models,end=1,**opts)
            p.analyze_notes(self.audio,self.models,threads=2,**opts)
            self.audio.write_bytes(b'changed')
            p.analyze_notes(self.audio,self.models,**opts)
            self.assertEqual(run.call_count,4)

    def test_cache_corruption(self):
        cache = self.root/'cache'
        with self.worker() as run:
            p.analyze_notes(self.audio,self.models,cache_dir=cache)
            next(cache.glob('*.json')).write_text('bad')
            p.analyze_notes(self.audio,self.models,cache_dir=cache)
            self.assertEqual(run.call_count,2)

    def test_no_default_cache(self):
        with self.worker() as run:
            p.analyze_notes(self.audio,self.models)
            p.analyze_notes(self.audio,self.models)
            self.assertEqual(run.call_count,2)
            self.assertFalse(list(self.root.rglob('*.json')))

    def test_timeout(self):
        with patch.object(p.subprocess,'run',side_effect=subprocess.TimeoutExpired('x',1)):
            with self.assertRaisesRegex(p.PolyphonicError,'timed out'): p.analyze_notes(self.audio,self.models,timeout=1)

    def test_worker_error(self):
        with patch.object(p.subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stderr=b'private path')):
            with self.assertRaisesRegex(p.PolyphonicError,'worker failed'): p.analyze_notes(self.audio,self.models)

    def test_decode(self):
        import numpy as np
        a=np.zeros((50,88),np.float32); f=a.copy(); o=a.copy()
        a[10,39]=.9; f[10:20,39]=.9; o[20,39]=.9
        got=p.decode(a,f,o,.02,.25,.3,.4,2,3)
        self.assertEqual(len(got),1); self.assertEqual(got[0][2],60)
        self.assertAlmostEqual(got[0][0],.2)

    def test_fake_inference_interval(self):
        import numpy as np
        import soundfile as sf
        sf.write(self.audio,np.zeros(16000*3),16000)
        calls=[]
        class Session:
            def __init__(self,path,options,providers):
                self.front=path.endswith('hcqt.onnx')
                self.providers=providers
            def run(self,names,inputs):
                if self.front:
                    self.assert_input(inputs['audio'].shape==(1,128000))
                    return [np.zeros((1,1),np.float32)]
                calls.append(names)
                return [np.full((1,400,88),-10,np.float32) for _ in names]
            @staticmethod
            def assert_input(ok):
                if not ok: raise AssertionError('bad input shape')
        fake=types.SimpleNamespace(SessionOptions=types.SimpleNamespace,GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL=1),InferenceSession=Session)
        with patch.dict(sys.modules,{'onnxruntime':fake}):
            got=p._run(self.audio,self.models,1,2,4)
        self.assertEqual(got['interval'],[1,2]); self.assertEqual(got['notes_json'],[])
        self.assertTrue(calls); self.assertTrue(all(c==list(p.HEADS) for c in calls))
        self.assertNotIn(str(self.root),json.dumps(got))

if __name__ == '__main__': unittest.main()
