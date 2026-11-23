#!/usr/bin/env python3
"""Tests for GB/GBC ROM header metadata matching without copyrighted ROMs."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rominfo
import detect

def make_rom():
    b = bytearray(32768)
    b[0x134:0x13a] = b"TETRIS"
    b[0x143] = 0
    b[0x14c] = 0
    b[0x14d] = (-sum(b[0x134:0x14d]) - 25) & 0xff
    total = sum(b) & 0xffff
    b[0x14e] = total >> 8
    b[0x14f] = total & 0xff
    return bytes(b)

class RomInfoTests(unittest.TestCase):
    def setUp(self):
        self.data = make_rom()
        self.sig = rominfo.header_signature(self.data)
        record = {
            "filename": "Example.gb", "system_hint": "gb",
            "title": self.sig["title"], "file_size": self.sig["size"],
            "cgb_flag": self.sig["cgb_flag"], "rom_version": self.sig["rom_version"],
            "header_checksum": {"value": self.sig["header_checksum"], "valid": True},
            "global_checksum": {"value": self.sig["global_checksum"], "valid": True}
        }
        self.lookup = rominfo.make_lookup({"records": [record]})

    def test_checksum_logic(self):
        self.assertTrue(self.sig["header_checksum_valid"])
        self.assertTrue(self.sig["global_checksum_valid"])

    def test_variant_metadata_match(self):
        matches = rominfo.candidates(self.data, "gb", self.lookup)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["confidence"], "advisory_metadata")

    def test_variant_mismatch(self):
        changed = bytearray(self.data)
        changed[0x14c] = 3
        self.assertFalse(rominfo.candidates(bytes(changed), "gb", self.lookup))

    def test_metadata_does_not_promote_to_recognized(self):
        classified = detect.classify(self.data, "Unlisted.gb", "gb",
                                     {"games": []}, rom_info_lookup=self.lookup)
        self.assertEqual(classified["status"], "unknown")
        self.assertEqual(classified["rom_info_matches"][0]["confidence"], "advisory_metadata")

    def test_no_match_on_gba(self):
        self.assertEqual(rominfo.candidates(self.data, "gba", self.lookup), [])

if __name__ == "__main__":
    unittest.main()
