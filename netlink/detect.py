#!/usr/bin/env python3
"""Read-only NetLink game-capability scanner (standard-library Python only).

Exact CRC32 identifies known ROM revisions. Name matches are suggestions only:
a ROM header has no universal Game Link Cable capability bit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import zlib

EXTENSIONS = {"gb": {".gb", ".zip"}, "gbc": {".gbc", ".zip", ".gb"}, "gba": {".gba", ".zip"}}
INNER_EXTENSIONS = {".gb", ".gbc", ".gba"}
CHUNK_SIZE = 1024 * 1024


def rom_entries(path, system):
    """Yield (inner_name, bytes) without changing the source ROM."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [i for i in archive.infolist()
                       if not i.is_dir() and Path(i.filename).suffix.lower() in INNER_EXTENSIONS]
            for entry in members:
                with archive.open(entry) as stream:
                    yield entry.filename, stream.read()
    elif path.suffix.lower() in EXTENSIONS[system]:
        yield path.name, path.read_bytes()


def header_info(data, system):
    if system in {"gb", "gbc"} and len(data) >= 0x150:
        title = data[0x134:0x144].split(b"\0", 1)[0].decode("ascii", "replace").strip()
        return {"header_title": title, "gb_cgb_flag": data[0x143]}
    if system == "gba" and len(data) >= 0xC0:
        return {"header_title": data[0xA0:0xAC].split(b"\0", 1)[0].decode("ascii", "replace").strip(),
                "game_code": data[0xAC:0xB0].decode("ascii", "replace")}
    return {}


def classify(data, file_name, system, database):
    crc = format(zlib.crc32(data) & 0xffffffff, "08x")
    sha1 = hashlib.sha1(data).hexdigest()
    hdr = header_info(data, system)
    # Exact fingerprints only. Wildcard matches never produce an automatic eligible verdict.
    for record in database["games"]:
        if system not in record["systems"]:
            continue
        hashes = record.get("roms", [])
        if any((h.get("sha1") and h["sha1"].lower() == sha1) or
               (h.get("crc32") and h["crc32"].lower() == crc and
                (not h.get("size") or h["size"] == len(data))) for h in hashes):
            return {"status": "recognized", "confidence": "exact_hash",
                    "game_id": record["id"], "capabilities": record["capabilities"],
                    "netlink_core": record.get("netlink_core"), "compatibility": record.get("compatibility", "untested"),
                    **hdr, "crc32": crc, "sha1": sha1}
    normalized = (Path(file_name).stem + " " + hdr.get("header_title", "")).casefold()
    suggestions = [
        {"game_id": record["id"], "capabilities": record["capabilities"],
         "evidence": (
             "game_code" if system == "gba" and hdr.get("game_code") in record.get("game_codes", [])
             else "title_hint"
         )}
        for record in database["games"]
        if system in record["systems"] and (
            (system == "gba" and bool(hdr.get("game_code"))
             and hdr["game_code"] in record.get("game_codes", []))
            or any(
                re.search(r"(?<![a-z0-9])" + re.escape(alias.casefold()) + r"(?![a-z0-9])", normalized)
                for alias in record.get("aliases", []))
        )
    ]
    return {"status": "candidate" if suggestions else "unknown",
            "confidence": ("game_code" if any(s["evidence"] == "game_code" for s in suggestions)
                           else "title_hint") if suggestions else "none",
            "suggestions": suggestions, **hdr, "crc32": crc, "sha1": sha1}


def scan(rom_root, database):
    for system in ("gb", "gbc", "gba"):
        folder = rom_root / system
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS[system]:
                continue
            try:
                found = False
                for inner_name, data in rom_entries(path, system):
                    found = True
                    result = classify(data, inner_name, system, database)
                    yield {"system": system, "path": str(path), "rom_entry": inner_name,
                           "size": len(data), **result}
                if not found:
                    yield {"system": system, "path": str(path), "status": "error",
                           "error": "No recognized ROM entry"}
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                yield {"system": system, "path": str(path), "status": "error", "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description="Read-only Batocera NetLink ROM capability audit")
    parser.add_argument("--rom-root", type=Path, default=Path("/userdata/roms"))
    parser.add_argument("--database", type=Path,
                        default=Path(__file__).resolve().parent / "database" / "games.json")
    parser.add_argument("--recognized-only", action="store_true")
    args = parser.parse_args()
    with args.database.open(encoding="utf-8") as f:
        db = json.load(f)
    if db.get("schema_version") != 1:
        parser.error("Unsupported database schema")
    counts = {"recognized": 0, "candidate": 0, "unknown": 0, "error": 0}
    for row in scan(args.rom_root, db):
        counts[row["status"]] += 1
        if not args.recognized_only or row["status"] == "recognized":
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    print("NetLink scan totals: " + ", ".join(f"{k}={v}" for k, v in counts.items()), file=sys.stderr)


if __name__ == "__main__":
    main()
