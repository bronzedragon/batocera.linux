#!/usr/bin/env python3
"""Synthetic evidence tests for the NetLink eligibility report."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import report

GUIDE = {"source": "https://example.invalid/guide", "games": [
    {"title": "Tetris", "system": "gb", "source_line": 1, "modes": [{
        "links": {"cable": True}, "no_link": False, "tags": ["2 Players", "Link Cable"]}]},
    {"title": "Tetris 2 / Tetris Flash", "system": "gb", "source_line": 2, "modes": [{
        "links": {"cable": True}, "no_link": False}]},
    {"title": "SGB Only", "system": "gb", "source_line": 3, "modes": [{
        "links": {"snes_controller": True}, "no_link": False}]}
]}
DB = {"games": [
    {"id": "gb-tetris", "systems": ["gb"], "capabilities": {"cable": True},
     "compatibility": "boot_tested_only", "netlink_core": "gambatte_link"},
    {"id": "gba-ruby", "systems": ["gba"], "capabilities": {"cable": True},
     "compatibility": "untested", "netlink_core": "mgba_dual"},
]}


class ReportTests(unittest.TestCase):
    def test_exact_dat_title_can_link_to_guide(self):
        row = {"system": "gb", "rom_entry": "unknown.gb", "status": "unknown",
               "no_intro_matches": [{"identification": "exact_sha1",
                                      "sha1": "a"*40, "game": "Tetris (World)"}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["rom_identity"], "exact")
        self.assertEqual(result["hardware_status"], "documented")
        self.assertEqual(result["guide_titles"], ["Tetris"])
        self.assertFalse(result["host_enabled"])
        self.assertFalse(result["join_enabled"])

    def test_tetris_2_not_tetris(self):
        row = {"system": "gb", "rom_entry": "Tetris 2 (World).gb",
               "status": "unknown", "no_intro_matches": [{
                   "identification": "exact_sha1", "sha1": "b"*40,
                   "game": "Tetris 2 (World)"}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["guide_titles"], ["Tetris 2 / Tetris Flash"])

    def test_sgb_only_not_link(self):
        row = {"system": "gb", "rom_entry": "SGB Only.gb", "status": "unknown",
               "reference_matches": [{
                   "title": "SGB Only", "modes": [{
                       "links": {"snes_controller": True}, "no_link": False}]}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["hardware_status"], "other_multiplayer")
        self.assertFalse(result["hardware"]["cable"])

    def test_curated_verified_hash_still_does_not_enable_network(self):
        row = {"system": "gb", "rom_entry": "Tetris.gb",
               "status": "recognized", "game_id": "gb-tetris"}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["rom_identity"], "exact")
        self.assertFalse(result["host_enabled"])
        self.assertEqual(result["compatibility_records"], ["boot_tested_only"])


    def test_manual_verified_requires_exact_tested_sha1(self):
        verified = {"games": [{
            "id": "gb-tetris", "systems": ["gb"],
            "capabilities": {"cable": True},
            "compatibility": "network_verified",
            "netlink_core": "gambatte_link",
            "network_tests": [{
                "result": "passed", "transport": "cable",
                "rom_sha1": "74591cc9501af93873f9a5d3eb12da12c0723bbc",
                "protocol": "gambatte-hb-link-6"
            }]
        }]}
        row = {
            "system": "gb", "status": "candidate",
            "suggestions": [{"game_id": "gb-tetris"}],
            "no_intro_matches": [{"identification": "exact_sha1",
                "sha1": "74591cc9501af93873f9a5d3eb12da12c0723bbc",
                "game": "Tetris (World) (Rev A)"}]
        }
        result = report.describe_row(row, verified, GUIDE)
        self.assertEqual(result["netlink_readiness"], "manual_verified")
        self.assertEqual(result["verified_transports"], ["cable"])
        self.assertFalse(result["host_enabled"])
        self.assertFalse(result["join_enabled"])
        row["no_intro_matches"][0]["sha1"] = "0" * 40
        other = report.describe_row(row, verified, GUIDE)
        self.assertEqual(other["netlink_readiness"], "not_implemented")
        self.assertEqual(other["verified_transports"], [])
        self.assertFalse(other["host_enabled"])

    def test_gba_game_code_candidate(self):
        row = {"system": "gba", "rom_entry": "unknown.gba",
               "status": "candidate", "suggestions": [{"game_id": "gba-ruby"}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["hardware_status"], "documented")
        self.assertEqual(result["rom_identity"], "unidentified")
        self.assertFalse(result["host_enabled"])

    def test_no_intro_only_not_link_capable(self):
        row = {"system": "gba", "rom_entry": "game.gba", "status": "unknown",
               "no_intro_matches": [{
                   "identification": "exact_sha1", "sha1": "a"*40,
                   "game": "Some GBA Game"}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["rom_identity"], "exact")
        self.assertEqual(result["hardware_status"], "unknown")
        self.assertFalse(result["join_enabled"])

    def test_crc_only_is_advisory(self):
        row = {"system": "gb", "rom_entry": "game.gb", "status": "unknown",
               "no_intro_matches": [{
                   "identification": "advisory_crc32_size", "game": "Tetris (World)"}]}
        result = report.describe_row(row, DB, GUIDE)
        self.assertEqual(result["rom_identity"], "advisory_metadata")
        self.assertEqual(result["guide_titles"], [])

    def test_error_row(self):
        result = report.describe_row({"status": "error", "path": "broken.zip",
                                      "error": "bad zip"}, DB, GUIDE)
        self.assertEqual(result["classification"], "error")
        self.assertFalse(result["host_enabled"])


if __name__ == "__main__":
    unittest.main()
