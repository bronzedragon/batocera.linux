#!/usr/bin/env python3
"""Fetch GB/GBC/GBA Libretro No-Intro DAT metadata, never game ROMs.

Explicit opt-in operation; the runtime detector never downloads anything.
Use --revision <git commit SHA> for reproducible catalog snapshots.
"""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

REMOTE = "https://raw.githubusercontent.com/libretro/libretro-database"
DAT_PATHS = {
    "gb": "Nintendo - Game Boy.dat",
    "gbc": "Nintendo - Game Boy Color.dat",
    "gba": "Nintendo - Game Boy Advance.dat",
}
MAX_BYTES = 100 * 1024 * 1024

def update(output_dir, revision="master"):
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for system, filename in DAT_PATHS.items():
        from urllib.parse import quote
        url = REMOTE + "/" + quote(revision, safe="") + "/metadat/no-intro/" + quote(filename)
        request = urllib.request.Request(
            url, headers={"User-Agent": "batocera-netlink-dat-import/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            contents = response.read(MAX_BYTES + 1)
        if len(contents) > MAX_BYTES:
            raise ValueError("DAT exceeds 100 MiB: " + filename)
        if not contents.lstrip(b"\\xef\\xbb\\xbf \\r\\n\\t").startswith(
                (b"clrmamepro", b"<")):
            raise ValueError("Unrecognized DAT format: " + filename)
        target = output_dir / (system + ".dat")
        pending = None
        try:
            with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as tmp:
                pending = Path(tmp.name)
                tmp.write(contents)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(pending, target)
        finally:
            if pending and pending.exists():
                pending.unlink()
        results.append((system, len(contents), hashlib.sha256(contents).hexdigest(), url))
    return results

def main():
    parser = argparse.ArgumentParser(description="Download Libretro GB/GBC/GBA No-Intro DATs")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "database" / "no-intro")
    parser.add_argument("--revision", default="master", help="Libretro repository Git commit SHA or branch")
    args = parser.parse_args()
    for system, size, sha256, url in update(args.output, args.revision):
        print(f"{system}: {size} bytes SHA256={sha256} {url}")

if __name__ == "__main__":
    main()
