#!/usr/bin/env python3
"""Read-only, EmulationStation-ready NetLink eligibility report.

The output describes candidate hardware capabilities and independent ROM
identification evidence. It intentionally NEVER enables Host or Join: no
verified two-machine transport records exist yet.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import reference

REPORT_SCHEMA = 1
TRANSPORT_KEYS = ("cable", "four_player_adapter", "infrared", "gbkiss",
                  "snes_controller", "super_multitap", "wireless_adapter")
NETWORK_KEYS = ("cable", "four_player_adapter", "infrared", "gbkiss",
                "wireless_adapter")


def _core_match(row, database):
    by_id = {record["id"]: record for record in database.get("games", [])}
    found = []
    if row.get("game_id") in by_id:
        found.append(by_id[row["game_id"]])
    for suggestion in row.get("suggestions", []):
        record = by_id.get(suggestion.get("game_id"))
        if record and record not in found:
            found.append(record)
    return found


def _guide_matches(row, guide):
    # Start with scanner results; use the No-Intro title for opaque filenames.
    found = list(row.get("reference_matches", []))
    exact = [m for m in row.get("no_intro_matches", [])
             if m.get("identification") == "exact_sha1"]
    if len({(m.get("game"), m.get("sha1")) for m in exact}) == 1:
        for match in reference.catalog_matches(
                exact[0].get("game", ""), "", row.get("system"), guide):
            if not any(m.get("title") == match["title"] for m in found):
                found.append({**match, "evidence": "no_intro_title_plus_guide"})
    return found


def _flags(records, matches):
    result = {name: False for name in TRANSPORT_KEYS}
    for record in records:
        for key in result:
            result[key] |= bool(record.get("capabilities", {}).get(key, False))
    for match in matches:
        for mode in match.get("modes", []):
            if mode.get("no_link"):
                continue
            for key in result:
                result[key] |= bool(mode.get("links", {}).get(key, False))
    return result


def describe_row(row, database, guide):
    status = row.get("status", "error")
    if status == "error":
        return {"system": row.get("system"), "path": row.get("path"),
                "rom_entry": row.get("rom_entry"), "classification": "error",
                "error": row.get("error"), "host_enabled": False,
                "join_enabled": False}
    candidates = _core_match(row, database)
    matches = _guide_matches(row, guide)
    flags = _flags(candidates, matches)
    source = row.get("no_intro_matches", [])
    exact_dat = [m for m in source if m.get("identification") == "exact_sha1"]
    identified = status == "recognized" or bool(exact_dat)
    if identified:
        rom_identity = "exact"
    elif source or row.get("rom_info_matches", []):
        rom_identity = "advisory_metadata"
    else:
        rom_identity = "unidentified"
    hardware = "documented" if any(flags[k] for k in NETWORK_KEYS) else (
        "other_multiplayer" if any(flags.values()) else "unknown"
    )
    # Source-backed hardware capability must not imply a working network core.
    compatible = [r for r in candidates
                  if r.get("compatibility") == "network_verified"]
    # Even a stored compatibility label is not yet sufficient: a separate
    # same-revision, tested transport record will be required in future.
    readiness = "not_implemented"
    return {
        "system": row.get("system"),
        "path": row.get("path"),
        "rom_entry": row.get("rom_entry"),
        "rom_identity": rom_identity,
        "rom_identification_source": (
            "no_intro_sha1" if exact_dat else
            "curated_hash" if status == "recognized" else
            "metadata" if rom_identity == "advisory_metadata" else "none"),
        "no_intro_titles": sorted({m.get("game", "") for m in exact_dat}),
        "hardware_status": hardware,
        "hardware": flags,
        "guide_titles": sorted({m["title"] for m in matches}),
        "game_ids": sorted({r["id"] for r in candidates}),
        "compatibility_records": sorted({str(r.get("compatibility", "untested"))
                                          for r in candidates}),
        "netlink_readiness": readiness,
        "host_enabled": False,
        "join_enabled": False,
        "reason": "Network link transport not verified for this ROM/core",
    }


def generate(index, database, guide):
    for path in sorted(index.get("files", {})):
        for row in index["files"][path].get("rows", []):
            yield describe_row(row, database, guide)


def main():
    parser = argparse.ArgumentParser(description="Read-only NetLink eligibility report")
    parser.add_argument("--index", type=Path,
                        default=Path("/userdata/system/configs/netlink/index.json"))
    parser.add_argument("--database", type=Path,
                        default=Path(__file__).resolve().parent / "database" / "games.json")
    parser.add_argument("--guide", type=Path,
                        default=Path(__file__).resolve().parent / "database" / "references" / "gb_reyvgm.json")
    parser.add_argument("--output", type=Path,
                        help="Optional JSON Lines output file (default: stdout)")
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    database = json.loads(args.database.read_text(encoding="utf-8"))
    guide = json.loads(args.guide.read_text(encoding="utf-8"))
    if index.get("schema_version") != 4:
        parser.error("NetLink index must be version 4; rerun index.py")
    stats = Counter()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    out = args.output.open("w", encoding="utf-8") if args.output else sys.stdout
    try:
        for record in generate(index, database, guide):
            stats[record.get("hardware_status", "error")] += 1
            stats["total"] += 1
            print(json.dumps(record, ensure_ascii=False, sort_keys=True), file=out)
    finally:
        if args.output:
            out.close()
    print("NetLink report: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())),
          file=sys.stderr)


if __name__ == "__main__":
    main()
