"""Advisory GB/GBC cartridge identification from Thomas Daley's ROM-info catalog.

No SHA-1/CRC32 in this source. Matching headers and checksums can narrow a
variant but MUST NOT change exact-hash confidence or NetLink readiness.
"""
from collections import defaultdict

def header_signature(data):
    if len(data) < 0x150:
        return None
    title_end = 0x143 if data[0x143] in (0x80, 0xC0) else 0x144
    header = data[0x134:title_end].split(b"\0", 1)[0].decode("ascii", "replace").strip()
    # Standard GB header checksum covers 0x134..0x14C inclusive.
    calculated = (-sum(data[0x134:0x14D]) - 25) & 0xff
    global_sum = (sum(data) - data[0x14E] - data[0x14F]) & 0xffff
    return {
        "title": header, "size": len(data), "cgb_flag": data[0x143],
        "rom_version": data[0x14C],
        "header_checksum": f"{data[0x14D]:02x}",
        "global_checksum": f"{(data[0x14E] << 8) | data[0x14F]:04x}",
        "header_checksum_valid": calculated == data[0x14D],
        "global_checksum_valid": global_sum == ((data[0x14E] << 8) | data[0x14F])
    }

def make_lookup(catalog):
    result = defaultdict(list)
    for record in catalog.get("records", []):
        if record.get("system_hint") not in ("gb", "gbc"):
            continue
        # Only records with all signature components can be compared.
        hc = record.get("header_checksum", {})
        gc = record.get("global_checksum", {})
        if not (isinstance(hc, dict) and isinstance(gc, dict)
                and hc.get("value") and gc.get("value")
                and "file_size" in record and "rom_version" in record
                and "cgb_flag" in record and record.get("title")):
            continue
        key = (record["title"].strip(), record["file_size"],
               record["cgb_flag"], record["rom_version"],
               hc["value"].lower().zfill(2), gc["value"].lower().zfill(4))
        result[key].append(record)
    return result

def candidates(data, system, lookup):
    if system not in ("gb", "gbc") or not lookup:
        return []
    sig = header_signature(data)
    if sig is None:
        return []
    key = (sig["title"], sig["size"], sig["cgb_flag"], sig["rom_version"],
           sig["header_checksum"], sig["global_checksum"])
    found = lookup.get(key, [])
    return [{
        "filename": r["filename"],
        "source": "GB_ROM_INFO.txt (Thomas Daley, 2017)",
        "reference_quality": "catalog_checksums_pass" if (
            r.get("header_checksum", {}).get("valid") and
            r.get("global_checksum", {}).get("valid")) else "catalog_checksum_warning",
        "confidence": "advisory_metadata"
    } for r in found[:12]]

