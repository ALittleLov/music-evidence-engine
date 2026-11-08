# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import unittest

SAMPLE = os.environ.get("MEE_TEST_SAMPLE")
ARGS = ["--json", "--brief"]


class CliCompatTest(unittest.TestCase):
    def test_help_lists_legacy_flags(self):
        out = subprocess.check_output(
            [sys.executable, "-B", "-m", "music_evidence_engine", "--help"],
            encoding="utf-8", errors="replace", stderr=subprocess.STDOUT,
        )
        for flag in ("--blocks", "--chord-block", "--start", "--end", "--json",
                     "--brief", "--detail", "--stems", "--asr", "--preview-asr",
                     "--preview", "--bands", "--pitch"):
            self.assertIn(flag, out)

    @unittest.skipUnless(SAMPLE and os.path.exists(SAMPLE), "MEE_TEST_SAMPLE not set")
    def test_brief_json(self):
        out = subprocess.check_output(
            [sys.executable, "-B", "-m", "music_evidence_engine", SAMPLE] + ARGS,
            encoding="utf-8", errors="replace",
        )
        obj = json.loads(out)
        for key in ("scope", "dur", "bpm", "key", "loud", "energy", "fit"):
            self.assertIn(key, obj)


if __name__ == "__main__":
    unittest.main()
