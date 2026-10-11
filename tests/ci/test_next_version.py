"""The script that decides the next version, through its command line.

The expectations come from its contract: a file that holds `MAJOR.MINOR.PATCH`, three numbers
with no leading zero, and a line break; the patch number raised by one on standard output;
status 2 and one line on standard error for any other text, and when the tag of the next
version is among the arguments.

The tests need `python3` on PATH.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "ci" / "next_version.py"


class NextVersion(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def script(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(SCRIPT), *arguments]
        return subprocess.run(command, capture_output=True, text=True, timeout=60)

    def next_version(self, text: str, *tags: str) -> subprocess.CompletedProcess[str]:
        file = self.scratch / "version"
        file.write_bytes(text.encode())
        return self.script(str(file), *tags)

    def test_the_patch_number_is_raised_by_one(self):
        cases = (
            ("0.0.0\n", (), "0.0.1\n"),
            ("0.1.9\n", ("0.1.9",), "0.1.10\n"),
            ("1.0.0\n", ("0.9.4",), "1.0.1\n"),
            ("0.0.0\n", ("0.0.10",), "0.0.1\n"),
        )
        for text, tags, expected in cases:
            with self.subTest(text=text, tags=tags):
                result = self.next_version(text, *tags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_a_text_of_another_form_is_refused(self):
        cases = (
            "",
            "1.0\n",
            "v1.0.0\n",
            "1.0.0-rc1\n",
            "01.0.0\n",
            "1.00.0\n",
            "1.0.01\n",
            " 1.0.0\n",
            "1.0.0\n1.0.1\n",
            "1.0.0",
        )
        for text in cases:
            with self.subTest(text=text):
                result = self.next_version(text)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(result.stdout, "")
                self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)

    def test_the_tag_of_the_next_version_is_refused(self):
        result = self.next_version("0.1.9\n", "0.1.10")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)

    def test_a_file_that_cannot_be_read_is_refused(self):
        result = self.script(str(self.scratch / "missing"))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)

    def test_a_call_that_names_no_file_is_refused(self):
        result = self.script()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
