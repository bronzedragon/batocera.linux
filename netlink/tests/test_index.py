#!/usr/bin/env python3
"""Synthetic-ROM tests for the NetLink incremental index."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import index

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "gb").mkdir()
        self.db = self.root / "games.json"
        self.db.write_text(json.dumps({"schema_version": 1, "games": [
            {"id": "fixture", "systems": ["gb"], "aliases": ["LINK TEST"],
             "roms": [], "capabilities": {"cable": True}, "netlink_core": "gambatte_link"}]}))
        self.rom = self.root / "gb" / "LINK TEST.gb"
        self.rom.write_bytes(b"fixture data")

    def test_reuse_and_change(self):
        first, counts = index.build_index(self.root, self.db)
        self.assertEqual(counts["scanned_files"], 1)
        second, counts = index.build_index(self.root, self.db, first)
        self.assertEqual(counts["cached_files"], 1)
        self.rom.write_bytes(b"different size of fixture data")
        _, counts = index.build_index(self.root, self.db, second)
        self.assertEqual(counts["scanned_files"], 1)

    def test_database_invalidates(self):
        previous, _ = index.build_index(self.root, self.db)
        self.db.write_text(self.db.read_text() + " ")
        _, counts = index.build_index(self.root, self.db, previous)
        self.assertEqual(counts["scanned_files"], 1)

    def test_deletion_is_reflected(self):
        previous, _ = index.build_index(self.root, self.db)
        self.rom.unlink()
        fresh, _ = index.build_index(self.root, self.db, previous)
        self.assertEqual(fresh["files"], {})

    def test_zip_scan(self):
        self.rom.unlink()
        with zipfile.ZipFile(self.root / "gb" / "sample.zip", "w") as archive:
            archive.writestr("LINK TEST.gb", b"fixture data")
        result, counts = index.build_index(self.root, self.db)
        self.assertEqual(counts["candidate"], 1)
        self.assertEqual(len(result["files"]), 1)

    def test_atomic_write(self):
        destination = self.root / "cache" / "index.json"
        index.save_atomic(destination, {"ok": True})
        self.assertEqual(json.loads(destination.read_text()), {"ok": True})

if __name__ == "__main__":
    unittest.main()
