#!/usr/bin/env python3
"""Regression tests for the read-only NetLink detector. No copyrighted ROM data."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import zlib
import hashlib

DETECTOR = Path(__file__).resolve().parents[1] / "detect.py"
spec = importlib.util.spec_from_file_location("netlink_detector", DETECTOR)
detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detector)


class NetLinkDetectorTests(unittest.TestCase):
    def setUp(self):
        self.rom = bytearray(0x150)
        self.rom[0x134:0x13A] = b"TETRIS"
        self.rom = bytes(self.rom)
        self.sha1 = hashlib.sha1(self.rom).hexdigest()
        self.crc = f"{zlib.crc32(self.rom) & 0xffffffff:08x}"
        self.db = {"schema_version": 1, "games": [
            {"id": "fixture-tetris", "systems": ["gb"],
             "aliases": ["Tetris"], "roms": [{"sha1": self.sha1}],
             "capabilities": {"cable": True}, "compatibility": "untested",
             "netlink_core": "gambatte_link"}]}

    def test_exact_hash_recognized(self):
        result = detector.classify(self.rom, "test.gb", "gb", self.db)
        self.assertEqual(result["status"], "recognized")
        self.assertEqual(result["confidence"], "exact_hash")
        self.assertEqual(result["game_id"], "fixture-tetris")

    def test_title_only_is_candidate_not_recognized(self):
        modified = self.rom + b"extra"
        result = detector.classify(modified, "Tetris (unknown).gb", "gb", self.db)
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["confidence"], "title_hint")

    def test_unknown_is_not_incompatible(self):
        result = detector.classify(b"x" * 512, "Unlisted.gb", "gb", self.db)
        self.assertEqual(result["status"], "unknown")

    def test_zip_archive_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "gb").mkdir()
            with zipfile.ZipFile(root / "gb" / "fixture.zip", "w") as archive:
                archive.writestr("Tetris.gb", self.rom)
            rows = list(detector.scan(root, self.db))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "recognized")
            self.assertEqual(rows[0]["rom_entry"], "Tetris.gb")

    def test_gba_game_code_is_candidate_not_verified(self):
        rom = bytearray(0xC0)
        rom[0xA0:0xAC] = b"MARIO KART  "
        rom[0xAC:0xB0] = b"AMKE"
        database = {"schema_version": 1, "games": [{
            "id": "gba-mario-kart", "systems": ["gba"], "aliases": [],
            "game_codes": ["AMKE"], "roms": [],
            "capabilities": {"cable": True}
        }]}
        result = detector.classify(bytes(rom), "unidentified.gba", "gba", database)
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["confidence"], "game_code")
        self.assertEqual(result["suggestions"][0]["evidence"], "game_code")

    def test_real_database_fingerprint_present(self):
        dbpath = DETECTOR.parent / "database" / "games.json"
        db = json.loads(dbpath.read_text(encoding="utf-8"))
        red = next(game for game in db["games"] if game["id"] == "gb-pokemon-red")
        self.assertTrue(any(r.get("sha1") == "ea9bcae617fdf159b045185467ae58b2e4a48b9a"
                            for r in red["roms"]))


if __name__ == "__main__":
    unittest.main()
