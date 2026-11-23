"""Read-only No-Intro Logiqx XML DAT identification for GB, GBC and GBA.

The official No-Intro DAT files are user-supplied, never bundled or fetched.
A DAT identification does not imply Game Link Cable or NetLink compatibility.
"""
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

DAT_NAMES = {"gb": "gb.dat", "gbc": "gbc.dat", "gba": "gba.dat"}
MAX_DAT_BYTES = 100 * 1024 * 1024
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
CRC_RE = re.compile(r"^[0-9a-f]{8}$")

def local_name(tag):
    return tag.rsplit("}", 1)[-1]

def dat_paths(folder):
    if folder is None:
        return {}
    folder = Path(folder)
    paths = {}
    for system, name in DAT_NAMES.items():
        path = folder / name
        if path.is_file():
            paths[system] = path
    return paths

def dat_fingerprint(folder):
    """Hash DAT contents so index cache invalidates on catalog changes."""
    dig = hashlib.sha256()
    for system, path in sorted(dat_paths(folder).items()):
        if path.stat().st_size > MAX_DAT_BYTES:
            raise ValueError("No-Intro DAT too large: " + str(path))
        dig.update(system.encode("ascii") + b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                dig.update(chunk)
    return dig.digest()

def build_lookup(folder):
    """Return per-system indices keyed by SHA-1 and (CRC32, ROM size).

    XML iterparse avoids storing complete parsed trees. Named 'machine' records
    are accepted along with ordinary 'game' records.
    """
    indices = {}
    for system, path in dat_paths(folder).items():
        if path.stat().st_size > MAX_DAT_BYTES:
            raise ValueError("No-Intro DAT too large: " + str(path))
        by_sha1, by_crc = {}, {}
        active_name = None
        for event, elem in ET.iterparse(path, events=("start", "end")):
            tag = local_name(elem.tag)
            if event == "start":
                if tag in ("game", "machine"):
                    active_name = elem.attrib.get("name", "")
            elif tag == "rom" and active_name is not None:
                raw_size = elem.attrib.get("size", "")
                sha = elem.attrib.get("sha1", "").lower()
                crc = elem.attrib.get("crc", "").lower()
                if raw_size.isdigit():
                    size = int(raw_size)
                    record = {
                        "game": active_name,
                        "rom": elem.attrib.get("name", ""),
                        "size": size,
                        "source_dat": path.name,
                        "system": system,
                    }
                    if SHA1_RE.fullmatch(sha):
                        record["sha1"] = sha
                        by_sha1.setdefault((sha, size), []).append(record)
                    if CRC_RE.fullmatch(crc):
                        record["crc32"] = crc
                        by_crc.setdefault((crc, size), []).append(record)
                elem.clear()
            elif event == "end" and tag in ("game", "machine"):
                elem.clear()
                active_name = None
        indices[system] = {"sha1": by_sha1, "crc32": by_crc}
    return indices

def identify(system, sha1, crc32, size, indices):
    """Give SHA-1 priority; do not accept CRC-only for a conflicting SHA-1."""
    idx = (indices or {}).get(system)
    if not idx:
        return []
    matches = idx["sha1"].get((sha1.lower(), size), [])
    if matches:
        return [{**m, "evidence": "no_intro_sha1", "identification": "exact_sha1"}
                for m in matches[:10]]
    matches = idx["crc32"].get((crc32.lower(), size), [])
    return [{**m, "evidence": "no_intro_crc32_size", "identification": "advisory_crc32_size"}
            for m in matches[:10] if "sha1" not in m]
