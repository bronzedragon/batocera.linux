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

def _rom_records_xml(path):
    """Yield (game name, ROM attributes) from Logiqx XML."""
    active_name = None
    for event, elem in ET.iterparse(path, events=("start", "end")):
        tag = local_name(elem.tag)
        if event == "start" and tag in ("game", "machine"):
            active_name = elem.attrib.get("name", "")
        elif event == "end" and tag == "rom" and active_name is not None:
            yield active_name, dict(elem.attrib)
            elem.clear()
        elif event == "end" and tag in ("game", "machine"):
            active_name = None
            elem.clear()


# Quoted strings are a single token, regardless of parentheses in game titles.
_CM_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+')

def _rom_records_cmpro(path):
    """Yield (game name, ROM attributes) from Libretro's ClrMamePro DAT."""
    source = path.read_text(encoding="utf-8-sig")
    def unquote(token):
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        return token

    tokens = iter(_CM_TOKEN.findall(source))
    def group():
        fields, children = {}, []
        for key in tokens:
            if key == ")":
                return fields, children
            try:
                value = next(tokens)
            except StopIteration:
                raise ValueError("Truncated ClrMamePro DAT: " + str(path)) from None
            if value == "(":
                child_fields, child_children = group()
                children.append((key.lower(), child_fields, child_children))
            elif value == ")":
                raise ValueError("Malformed ClrMamePro DAT: " + str(path))
            else:
                fields[key.lower()] = unquote(value)
        raise ValueError("Truncated ClrMamePro DAT: " + str(path))

    for token in tokens:
        if token.lower() not in ("game", "machine", "clrmamepro"):
            continue
        if next(tokens, None) != "(":
            raise ValueError("Invalid ClrMamePro DAT group: " + str(path))
        fields, children = group()
        if token.lower() == "clrmamepro":
            continue
        for kind, child, _ in children:
            if kind == "rom":
                yield fields.get("name", ""), child


def build_lookup(folder):
    """Index both Logiqx XML and ClrMamePro text .dat catalogs."""
    indices = {}
    for system, path in dat_paths(folder).items():
        if path.stat().st_size > MAX_DAT_BYTES:
            raise ValueError("No-Intro DAT too large: " + str(path))
        with path.open("rb") as stream:
            prefix = stream.read(128).lstrip(b"\xef\xbb\xbf \r\n\t")
        records = (_rom_records_xml(path) if prefix.startswith(b"<")
                   else _rom_records_cmpro(path))
        by_sha1, by_crc = {}, {}
        for game_name, attrs in records:
            raw_size = attrs.get("size", "")
            sha = attrs.get("sha1", "").lower()
            crc = attrs.get("crc", "").lower()
            if not raw_size.isdigit():
                continue
            size = int(raw_size)
            record = {
                "game": game_name,
                "rom": attrs.get("name", ""),
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
