#!/usr/bin/env python3
"""Synthetic, read-only tests for NetLink launch fingerprint handling."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch


class LaunchTests(unittest.TestCase):
    def test_plain_rom_sha1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.gb"
            path.write_bytes(b"\0" * 32768)
            self.assertEqual(launch.rom_sha1(path),
                             hashlib.sha1(b"\0" * 32768).hexdigest())

    def test_zip_hash_is_inner_rom_not_archive(self):
        payload = b"GB ROM DATA" * 200
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Tetris (World) (Rev A).gb", payload)
            self.assertEqual(launch.rom_sha1(path), hashlib.sha1(payload).hexdigest())
            self.assertNotEqual(launch.rom_sha1(path), launch.file_hash(path, "sha1"))

    def test_rejects_ambiguous_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("a.gb", b"a")
                z.writestr("b.gb", b"b")
            with self.assertRaisesRegex(ValueError, "exactly one"):
                launch.rom_sha1(path)


if __name__ == "__main__":
    unittest.main()
