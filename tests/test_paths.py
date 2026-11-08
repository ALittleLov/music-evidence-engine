# -*- coding: utf-8 -*-
import os
import unittest
from unittest import mock

from music_evidence_engine import EnginePaths


class PathsTest(unittest.TestCase):
    def test_explicit_overrides_env(self):
        with mock.patch.dict(os.environ, {
            "MEE_DATA_DIR": "/env/data",
            "MEE_CACHE_DIR": "/env/cache",
            "MEE_MODEL_DIR": "/env/model",
            "MEE_RESOURCE_DIR": "/env/res",
        }, clear=False):
            p = EnginePaths(
                resource_dir="/explicit/res",
                data_dir="/explicit/data",
                cache_dir="/explicit/cache",
                model_dir="/explicit/model",
                hf_home="/explicit/hf",
                tmp_dir="/explicit/tmp",
            ).resolve()
        self.assertEqual(p.resource_dir, os.path.abspath("/explicit/res"))
        self.assertEqual(p.data_dir, os.path.abspath("/explicit/data"))
        self.assertEqual(p.cache_dir, os.path.abspath("/explicit/cache"))
        self.assertEqual(p.model_dir, os.path.abspath("/explicit/model"))
        self.assertEqual(p.hf_home, os.path.abspath("/explicit/hf"))
        self.assertEqual(p.tmp_dir, os.path.abspath("/explicit/tmp"))

    def test_env_fallback(self):
        with mock.patch.dict(os.environ, {
            "MEE_DATA_DIR": "/env/data",
            "MEE_CACHE_DIR": "/env/cache",
            "MEE_MODEL_DIR": "/env/model",
            "MEE_RESOURCE_DIR": "/env/res",
        }, clear=False):
            p = EnginePaths().resolve()
        self.assertEqual(p.data_dir, os.path.abspath("/env/data"))
        self.assertEqual(p.cache_dir, os.path.abspath("/env/cache"))
        self.assertEqual(p.model_dir, os.path.abspath("/env/model"))
        self.assertEqual(p.resource_dir, os.path.abspath("/env/res"))


if __name__ == "__main__":
    unittest.main()
