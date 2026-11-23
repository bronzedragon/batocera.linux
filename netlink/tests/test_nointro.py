#!/usr/bin/env python3
"""No-Intro Logiqx XML matching tests; synthetic ROM metadata only."""
import hashlib
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nointro
import detect

SHA = "a" * 40
CRC = "1234abcd"
SIZE = 32768

def xml(sha=SHA, crc=CRC, game="Tetris (World)"):
    return ('<?xml version="1.0"?>\n<datafile>'
            '<header><name>Nintendo - Game Boy</name></header>'
            '<game name="' + game + '"><rom name="Tetris (World).gb"'
            ' size="32768" crc="' + crc + '" sha1="' + sha + '"/></game>'
            '</datafile>')

class NoIntroTests(unittest.TestCase):
    def test_sha1_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gb.dat").write_text(xml(), encoding="utf-8")
            idx = nointro.build_lookup(temp)
            matches = nointro.identify("gb", SHA, CRC, SIZE, idx)
            self.assertEqual(matches[0]["identification"], "exact_sha1")
            self.assertEqual(matches[0]["game"], "Tetris (World)")

    def test_wrong_sha1_not_accepted_via_crc(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gb.dat").write_text(xml(), encoding="utf-8")
            idx = nointro.build_lookup(temp)
            self.assertEqual(nointro.identify("gb", "b" * 40, CRC, SIZE, idx), [])

    def test_crc_only_fallback_advisory(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gb.dat").write_text(xml(sha=""), encoding="utf-8")
            idx = nointro.build_lookup(temp)
            matches = nointro.identify("gb", "b" * 40, CRC, SIZE, idx)
            self.assertEqual(matches[0]["identification"], "advisory_crc32_size")

    def test_system_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gb.dat").write_text(xml(), encoding="utf-8")
            idx = nointro.build_lookup(temp)
            self.assertEqual(nointro.identify("gba", SHA, CRC, SIZE, idx), [])

    def test_changes_invalidate_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp, "gb.dat")
            p.write_text(xml(), encoding="utf-8")
            first = nointro.dat_fingerprint(temp)
            p.write_text(xml(game="Tetris (Rev A)"), encoding="utf-8")
            self.assertNotEqual(first, nointro.dat_fingerprint(temp))

    def test_identification_does_not_create_netlink_eligibility(self):
        with tempfile.TemporaryDirectory() as temp:
            data = b"\x00" * SIZE
            sha = hashlib.sha1(data).hexdigest()
            crc = f"{__import__('zlib').crc32(data) & 0xffffffff:08x}"
            Path(temp, "gb.dat").write_text(xml(sha=sha, crc=crc), encoding="utf-8")
            result = detect.classify(data, "unknown.gb", "gb", {"games": []},
                                     nointro_indices=nointro.build_lookup(temp))
            self.assertEqual(result["status"], "unknown")
            self.assertEqual(result["no_intro_matches"][0]["identification"], "exact_sha1")

    def test_libretro_clrmamepro(self):
        sample = (
            'clrmamepro (\n\tname "Nintendo - Game Boy Advance"\n)\n'
            'game (\n'
            '\tname "Pokemon (USA) (Rev 1)"\n'
            '\tregion "USA"\n'
            '\trom ( name "Pokemon (USA) (Rev 1).gba" size 32768 '
            'crc 1234ABCD md5 ' + "a" * 32 + ' sha1 ' + SHA.upper() + ' serial "BPRE" )\n'
            ')\n'
        )
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gba.dat").write_text(sample, encoding="utf-8")
            indices = nointro.build_lookup(temp)
            found = nointro.identify("gba", SHA, CRC, SIZE, indices)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["game"], "Pokemon (USA) (Rev 1)")
            self.assertEqual(found[0]["identification"], "exact_sha1")

    def test_libretro_multiple_games_and_parentheses_in_titles(self):
        sample = (
            'clrmamepro ( name "Nintendo - Game Boy Advance" )\n'
            'game ( name "First (World)" rom ( name "First (World).gba" '
            'size 32768 crc 1234ABCD sha1 ' + SHA + ' ) )\n'
            'game ( name "Second" rom ( name "Second.gba" '
            'size 65536 crc ABCDEF12 sha1 ' + "b"*40 + ' ) )\n'
        )
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "gba.dat").write_text(sample, encoding="utf-8")
            idx = nointro.build_lookup(temp)
            self.assertEqual(nointro.identify("gba", SHA, CRC, SIZE, idx)[0]["game"],
                             "First (World)")
            self.assertEqual(nointro.identify("gba", "b"*40, "abcdef12", 65536, idx)[0]["game"],
                             "Second")

    def test_machine_element(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp, "gb.dat")
            p.write_text(xml().replace("<game ", "<machine ").replace("</game>", "</machine>"),
                         encoding="utf-8")
            self.assertEqual(len(nointro.identify("gb", SHA, CRC, SIZE,
                                                 nointro.build_lookup(temp))), 1)

if __name__ == "__main__":
    unittest.main()
