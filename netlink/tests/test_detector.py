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
import sys

DETECTOR = Path(__file__).resolve().parents[1] / "detect.py"
sys.path.insert(0, str(DETECTOR.parent))
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

    def test_guide_tetris_not_sequels(self):
        guide = {"games": [
            {"title": "Tetris", "system": "gb", "source_line": 1,
             "modes": [{"links": {"cable": True}, "no_link": False}]},
            {"title": "Tetris 2 / Tetris Flash", "system": "gb", "source_line": 2,
             "modes": [{"links": {"cable": True}, "no_link": False}]}]}
        base = self.rom + b"x"
        first = detector.classify(base, "Tetris (World).gb", "gb", self.db, guide)
        second = detector.classify(base, "Tetris 2 (World).gb", "gb", self.db, guide)
        self.assertEqual(first["reference_matches"][0]["title"], "Tetris")
        self.assertEqual(second["reference_matches"][0]["title"], "Tetris 2 / Tetris Flash")
        self.assertEqual(len(second["reference_matches"]), 1)
        self.assertFalse(second["suggestions"])

    def test_guide_sgb_only_not_link_candidate(self):
        guide = {"games": [{"title": "SGB Only", "system": "gb",
            "modes": [{"links": {"snes_controller": True}, "no_link": False}]}]}
        result = detector.classify(b"x" * 512, "SGB Only.gb", "gb", {"games": []}, guide)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reference_matches"][0]["hardware_link_capable"], False)

    def test_real_database_fingerprint_present(self):
        dbpath = DETECTOR.parent / "database" / "games.json"
        db = json.loads(dbpath.read_text(encoding="utf-8"))
        red = next(game for game in db["games"] if game["id"] == "gb-pokemon-red")
        self.assertTrue(any(r.get("sha1") == "ea9bcae617fdf159b045185467ae58b2e4a48b9a"
                            for r in red["roms"]))


if __name__ == "__main__":
    unittest.main()
