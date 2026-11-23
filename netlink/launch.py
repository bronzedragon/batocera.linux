#!/usr/bin/env python3
"""Fingerprint-gated, explicit NetLink launcher. Default is read-only preflight.

This is the safe launcher boundary for a future EmulationStation Host/Join menu.
It never edits game, save, gamelist, global emulator, or netplay configuration.
RetroArch itself may write runtime files when --launch is requested.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "database" / "games.json"
DEFAULT_CORE = Path("/userdata/system/custom-cores/gambatte_link_libretro.so")
ROM_ROOT = Path("/userdata/roms")
PROTOCOL = "gambatte-hb-link-6"


def file_hash(path, name):
    h = hashlib.new(name)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rom_sha1(path):
    if path.suffix.lower() != ".zip":
        return file_hash(path, "sha1")
    with zipfile.ZipFile(path) as z:
        entries = [i for i in z.infolist()
                   if not i.is_dir() and Path(i.filename).suffix.lower() in (".gb", ".gbc")]
        if len(entries) != 1:
            raise ValueError("ZIP must contain exactly one GB/GBC ROM")
        entry = entries[0]
        if entry.file_size > 8 * 1024 * 1024:
            raise ValueError("Inner ROM is unexpectedly large")
        h = hashlib.sha1()
        with z.open(entry) as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role", choices=("host", "join"), required=True)
    p.add_argument("--rom", required=True, type=Path)
    p.add_argument("--peer", help="LAN host IPv4/IPv6 address for join")
    p.add_argument("--port", type=int, default=55435)
    p.add_argument("--core", type=Path, default=DEFAULT_CORE)
    p.add_argument("--database", type=Path, default=DEFAULT_DB)
    p.add_argument("--config", type=Path)
    p.add_argument("--launch", action="store_true", help="Execute RetroArch after validation")
    a = p.parse_args(argv)
    if not 1 <= a.port <= 65535:
        p.error("port must be in 1..65535")
    if a.role == "join":
        if not a.peer:
            p.error("--peer is required for join")
        try:
            ip = ipaddress.ip_address(a.peer)
        except ValueError:
            p.error("join peer must be an explicit IP address")
        if ip.is_unspecified or ip.is_multicast or ip.is_loopback:
            p.error("join peer must be a non-loopback unicast address")
    elif a.peer:
        p.error("--peer is valid only with --role join")
    rom = a.rom.resolve(strict=True)
    core = a.core.resolve(strict=True)
    if not rom.is_file() or not core.is_file():
        p.error("ROM and core must be regular files")
    try:
        rom.relative_to(ROM_ROOT.resolve())
    except ValueError:
        p.error("ROM must reside within /userdata/roms")
    if rom.suffix.lower() not in (".gb", ".gbc", ".zip"):
        p.error("Only GB/GBC ROMs or ZIP archives are currently supported")
    if a.config and not a.config.is_file():
        p.error("--config path does not exist")
    if not shutil.which("retroarch"):
        p.error("retroarch executable not found")
    with core.open("rb") as f:
        if PROTOCOL.encode() not in f.read():
            p.error("core is missing NetLink protocol marker")
    core_sha = file_hash(core, "sha256")
    try:
        rom_sha = rom_sha1(rom)
    except (zipfile.BadZipFile, ValueError) as exc:
        p.error(str(exc))
    db = json.loads(a.database.read_text(encoding="utf-8"))
    matches = [
        (game, test)
        for game in db.get("games", [])
        if game.get("compatibility") == "network_verified"
        for test in game.get("network_tests", [])
        if test.get("result") == "passed"
        and test.get("transport") == "cable"
        and test.get("protocol") == PROTOCOL
        and test.get("rom_sha1", "").lower() == rom_sha
        and test.get("core_sha256", "").lower() == core_sha
    ]
    if len(matches) != 1:
        p.error("exact ROM/core/protocol combination has no single passing NetLink test record")
    game, _ = matches[0]
    cmd = ["retroarch", "--verbose", "--libretro", str(core),
           "--port", str(a.port)]
    if a.config:
        cmd += ["--config", str(a.config)]
    cmd += ["--host"] if a.role == "host" else ["--connect", a.peer]
    cmd.append(str(rom))
    print("NetLink validated game:", game["id"])
    print("ROM SHA-1:", rom_sha)
    print("Core SHA-256:", core_sha)
    print("Protocol:", PROTOCOL)
    print("Role:", a.role)
    print("Command:", " ".join(__import__("shlex").quote(x) for x in cmd), flush=True)
    if not a.launch:
        print("PREFLIGHT ONLY; use --launch to start the verified session.")
        return 0
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit("NetLink: " + str(exc))
