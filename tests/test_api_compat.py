# -*- coding: utf-8 -*-
import os
import unittest

from music_evidence_engine import analyze

SAMPLE = os.environ.get("MEE_TEST_SAMPLE")


@unittest.skipUnless(SAMPLE and os.path.exists(SAMPLE), "MEE_TEST_SAMPLE not set")
class ApiCompatTest(unittest.TestCase):
    def test_brief_returns_dict(self):
        result = analyze(SAMPLE, brief=True)
        self.assertIsInstance(result, dict)
        for key in ("scope", "dur", "bpm", "key", "loud", "energy", "fit"):
            self.assertIn(key, result)

    def test_text_returns_text(self):
        result = analyze(SAMPLE, format="text")
        self.assertIn("text", result)
        self.assertIsInstance(result["text"], str)
        self.assertTrue(("[判断]" in result["text"]) or ("[预览]" in result["text"]))


if __name__ == "__main__":
    unittest.main()
