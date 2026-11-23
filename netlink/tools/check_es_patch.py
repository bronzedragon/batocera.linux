#!/usr/bin/env python3
"""Read-only verification of the NetLink ES patch against a checked-out ES tree."""
import argparse
from pathlib import Path
import subprocess
import sys

PINNED_REVISION = "3c8f8fc7465633257210565935580617418362b7"
DEFAULT_PATCH = (Path(__file__).resolve().parents[2] /
    "package/batocera/emulationstation/batocera-emulationstation/" /
    "005-netlink-verified-tetris-menu.patch")


def cmd(args, cwd):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-source", required=True, type=Path,
                        help="Source checkout at pinned EmulationStation revision")
    parser.add_argument("--patch", type=Path, default=DEFAULT_PATCH)
    args = parser.parse_args()
    source = args.es_source.resolve()
    patch = args.patch.resolve()
    if not (source / "es-app/src/guis/GuiGameOptions.cpp").is_file():
        parser.error("Not an EmulationStation source checkout")
    if not patch.is_file():
        parser.error("Patch not found: " + str(patch))
    head = cmd(["git", "rev-parse", "HEAD"], source)
    if head.returncode != 0:
        parser.error("Git metadata unavailable: " + head.stderr.strip())
    print("Source HEAD:", head.stdout.strip())
    if head.stdout.strip() != PINNED_REVISION:
        print("WARNING: source HEAD differs from pinned Batocera revision; "
              "a different revision requires revalidation.")
    apply = cmd(["git", "apply", "--check", str(patch)], source)
    if apply.returncode == 0:
        print("PASS: Patch applies cleanly (no files modified)")
        return 0
    reverse = cmd(["git", "apply", "--reverse", "--check", str(patch)], source)
    if reverse.returncode == 0:
        print("PASS: Patch already applied")
        return 0
    print("FAIL: Patch neither applies nor appears already applied", file=sys.stderr)
    print(apply.stderr.strip(), file=sys.stderr)
    print(reverse.stderr.strip(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
