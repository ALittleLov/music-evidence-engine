# -*- coding: utf-8 -*-
import subprocess
import sys
import unittest


class ImportTest(unittest.TestCase):
    def test_import_is_light(self):
        code = (
            "import music_evidence_engine as m, sys;"
            "print(m.__version__);"
            "print('librosa' in sys.modules);"
            "print('onnxruntime' in sys.modules);"
            "print('numpy' in sys.modules)"
        )
        out = subprocess.check_output([sys.executable, "-B", "-c", code], text=True)
        lines = out.strip().splitlines()
        self.assertEqual(lines[0], "0.1.1")
        self.assertEqual(lines[1], "False")
        self.assertEqual(lines[2], "False")
        self.assertEqual(lines[3], "False")


if __name__ == "__main__":
    unittest.main()
