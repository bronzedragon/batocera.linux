#!/usr/bin/env python3
"""Incremental NetLink capability index. Does not modify ROMs or gamelists."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile

import detect

INDEX_VERSION = 2
DEFAULT_INDEX = Path("/userdata/system/configs/netlink/index.json")

def read_previous(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

def rom_files(root):
    for system in ("gb", "gbc", "gba"):
        folder = root / system
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path.suffix.lower() in detect.EXTENSIONS[system]:
                    yield system, path

def scan_one(system, path, database, guide=None):
    rows = []
    try:
        for name, payload in detect.rom_entries(path, system):
            result = detect.classify(payload, name, system, database, guide)
            rows.append({"system": system, "path": str(path),
                         "rom_entry": name, "size": len(payload), **result})
        if not rows:
            rows.append({"system": system, "path": str(path), "status": "error",
                         "error": "No recognized ROM entry"})
    except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile) as error:
        rows.append({"system": system, "path": str(path), "status": "error",
                     "error": str(error)})
    return rows

def build_index(root, database_path, previous=None, guide_path=None):
    database_bytes = database_path.read_bytes()
    database = json.loads(database_bytes)
    if database.get("schema_version") != 1:
        raise ValueError("Unsupported database schema")
    if guide_path is None:
        guide_path = Path(__file__).resolve().parent / 'database' / 'references' / 'gb_reyvgm.json'
    guide_bytes = guide_path.read_bytes()
    guide = json.loads(guide_bytes)
    if guide.get('schema_version') != 1:
        raise ValueError('Unsupported GB reference schema')
    fingerprint = hashlib.sha256(database_bytes + b'\\0' + guide_bytes).hexdigest()
    root = root.resolve()
    previous = previous or {}
    valid = (previous.get("schema_version") == INDEX_VERSION
             and previous.get("rom_root") == str(root)
             and previous.get("database_sha256") == fingerprint)
    cached = previous.get("files", {}) if valid else {}
    files = {}
    stats = {"cached_files": 0, "scanned_files": 0, "error_files": 0,
             "recognized": 0, "candidate": 0, "unknown": 0, "error": 0}
    for system, path in rom_files(root):
        try:
            info = path.stat()
        except OSError:
            continue
        identity = {"system": system, "size": info.st_size, "mtime_ns": info.st_mtime_ns}
        prior = cached.get(str(path))
        reusable = (isinstance(prior, dict) and prior.get("identity") == identity
                    and isinstance(prior.get("rows"), list)
                    and bool(prior["rows"])
                    and all(row.get("status") != "error" for row in prior["rows"]))
        rows = prior["rows"] if reusable else scan_one(system, path, database, guide)
        files[str(path)] = {"identity": identity, "rows": rows}
        stats["cached_files" if reusable else "scanned_files"] += 1
        if any(row.get("status") == "error" for row in rows):
            stats["error_files"] += 1
        for row in rows:
            status = row.get("status", "error")
            stats[status] = stats.get(status, 0) + 1
    return {"schema_version": INDEX_VERSION, "database_sha256": fingerprint,
            "rom_root": str(root), "files": files}, stats

def save_atomic(path, index):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            pending = stream.name
            json.dump(index, stream, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if pending and os.path.exists(pending):
            os.unlink(pending)

def main():
    parser = argparse.ArgumentParser(description="Incremental NetLink ROM index")
    parser.add_argument("--rom-root", type=Path, default=Path("/userdata/roms"))
    parser.add_argument("--database", type=Path,
                        default=Path(__file__).resolve().parent / "database" / "games.json")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--guide', type=Path, default=Path(__file__).resolve().parent / 'database' / 'references' / 'gb_reyvgm.json')
    parser.add_argument("--jsonl", action="store_true", help="Output per-ROM classification records")
    args = parser.parse_args()
    if not args.rom_root.is_dir():
        parser.error("ROM root not found: " + str(args.rom_root))
    try:
        index, stats = build_index(args.rom_root, args.database, read_previous(args.index), args.guide)
        save_atomic(args.index, index)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, "NetLink indexing error: " + str(error) + "\n")
    if args.jsonl:
        for record in index["files"].values():
            for row in record["rows"]:
                print(json.dumps(row, sort_keys=True, ensure_ascii=False))
    print("NetLink index: " + ", ".join(f"{key}={value}" for key, value in stats.items()), file=sys.stderr)
    print("Index saved: " + str(args.index), file=sys.stderr)

if __name__ == "__main__":
    main()
