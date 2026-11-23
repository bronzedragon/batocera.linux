# NetLink ROM detector prototype

This is a **read-only**, standard-library Python prototype for Batocera's eventual NetLink feature. It scans the existing `gb`, `gbc`, and `gba` ROM directories, including ZIP-contained ROMs. It neither edits gamelists nor changes emulator selection or NetPlay settings.

## Run

```sh
python3 netlink/detect.py --rom-root /userdata/roms > /tmp/netlink-games.jsonl
```

One JSON object per ROM is printed to stdout; totals go to stderr. `--recognized-only` filters unknowns and title candidates.

**Meaning of statuses:**

- `recognized`: SHA-1 or CRC32+size matches a curated exact ROM revision. The `compatibility` field separately records whether actual two-machine NetLink was tested.
- `candidate`: game title resembles a known link-capable game; **not sufficient to enable NetLink automatically**.
- `unknown`: no match; never assume the title is incapable.
- `error`: failed to inspect a file.

The initial registry contains the verified CRC32 from the user's Tetris (World) (Rev A) RetroArch log, plus unverified title hints. Hash entries must be independently validated before adding new exact variants. No universal GB/GBC/GBA header flag establishes link support. Detection does **not** advertise link capability in EmulationStation yet.

Future phases: integrate metadata into Batocera's indexing lifecycle, allow per-game overrides, identify compatible regional pairs, and expose Host/Join actions only where core capabilities and testing warrant them.

## ReyVGM Game Boy hardware guide integration

The read-only detector now consults `database/references/gb_reyvgm.json` alongside the curated ROM-fingerprint database. It uses exact normalized titles and explicitly curated aliases, never substring matching. The reference guide excludes Game Boy Color and Game Boy Advance; those systems remain handled by the curated registry.

Reference matches appear in each result's `reference_matches` array with the original guide's hardware mode tags, source URL, and source line. A documented title is only a hardware-capability **candidate**, never proof of a matching ROM revision or working network synchronization. Super Game Boy-only games without cable or infrared support remain `unknown` for NetLink eligibility.

`index.py` cache schema version 2 fingerprints both database files; first launch after upgrading rebuilds classifications, subsequent runs reuse unchanged ROM files. Changes to reference data invalidate prior cached classifications.

To validate on the development host:

```sh
python3 -m unittest discover -s netlink/tests -v
```

To rebuild the Batocera index and inspect matches:

```sh
python3 /userdata/system/netlink/index.py --rom-root /userdata/roms --jsonl > /tmp/netlink-index-results.jsonl
```

The current implementation does **not** alter EmulationStation menus, select a core automatically, or enable NetLink Host/Join sessions.

## Optional Thomas Daley GB/GBC cartridge catalog (2017)

`tools/import_gb_rom_info.py` converts the user-supplied `GB_ROM_INFO.txt` into an advisory JSON catalog. The original document has 9,333 GB/GBC ROM records, but **no SHA-1 or CRC32**. Matching size, header title, CGB flag, ROM version, header checksum and global checksum narrows candidate revisions without establishing an exact byte-for-byte match. Neither catalog matches nor checksum success imply network connectivity.

Generate the reference on a computer with the source text:

```sh
python3 netlink/tools/import_gb_rom_info.py GB_ROM_INFO.txt \
    netlink/database/references/gb_rom_info_reference.json
```

Deploy the resulting JSON alongside the other NetLink files. The catalog is optional, and is **not committed** to this branch at present; without it, the detector retains its previous behavior. Once deployed, it produces advisory `rom_info_matches` in the per-ROM output, including for entries still classified as `unknown`. Index schema version 3 invalidates old classifications when this catalog appears, disappears, or changes.

```sh
python3 /userdata/system/netlink/index.py --rom-root /userdata/roms --jsonl > /tmp/netlink-index-results.jsonl
```

ROM bytes, saves, gamelists and existing NetPlay settings are never modified.

## Optional official No-Intro XML DAT identification

Download XML DATs for **Nintendo - Game Boy**, **Nintendo - Game Boy Color**, and **Nintendo - Game Boy Advance** from https://datomatic.no-intro.org/index.php?page=download and place them at:

```text
netlink/database/no-intro/gb.dat
netlink/database/no-intro/gbc.dat
netlink/database/no-intro/gba.dat
```

You can specify another location with `--dat-dir /path/to/dats`. The source DATs are not bundled or automatically downloaded; this keeps ROM library scans offline and allows independently chosen No-Intro releases.

The `<datafile><game><rom>` (or `<machine>`) XML is parsed into hash indices. SHA-1 + size is treated as an exact catalog **ROM identity**; CRC32 + size is advisory only when the DAT entry has no SHA-1. It never accepts a conflicting SHA-1 by falling back to CRC32. Exact DAT identification appears in `no_intro_matches` in JSONL and the cache. It **does not** upgrade NetLink's `status` to `recognized`, or imply a game's link-cable support or network readiness. Keep network eligibility tied to the curated hardware capability and core test records.

Index schema version 4 fingerprints all present DAT contents and rebuilds classifications automatically when a DAT is added, removed, or updated. Each DAT is subject to a 100-MiB input limit.

```sh
python3 -m unittest discover -s netlink/tests -v
python3 /userdata/system/netlink/index.py --rom-root /userdata/roms --jsonl > /tmp/netlink-index-results.jsonl
```

Older installations still work with no DAT files. The importer is read-only and never renames or copies ROMs.

## Libretro database source for GB, GBC, and GBA (ClrMamePro DAT format)

The three system DATs are available at https://github.com/libretro/libretro-database/tree/master/metadat/no-intro . These are **ClrMamePro text DATs**, not XML: the `nointro.py` reader now accepts both formats.

Observed Libretro catalog version **2026.11.14**, containing 2,144 GB entries, 2,446 GBC entries, and 3,509 GBA entries. These counts describe the checked repository revision, not a promise that a later `master` snapshot will match.

Run the opt-in downloader on Ubuntu, not from the game launch path:

```sh
python3 netlink/tools/update_libretro_dats.py
```

The script saves `gb.dat`, `gbc.dat`, and `gba.dat` beneath `netlink/database/no-intro/`, displaying each SHA-256. For reproducibility, specify `--revision <commit SHA>` instead of following `master`. Deploy these three DAT files alongside the NetLink code on Batocera. They are not committed into this project's repository and **no ROM files are downloaded**.

```sh
python3 -m unittest discover -s netlink/tests -v
python3 /userdata/system/netlink/index.py --rom-root /userdata/roms --jsonl > /tmp/netlink-index-results.jsonl
```

The DAT reader identifies ROM contents by hash. NetLink eligibility and core transport compatibility remain independent.

## Combined NetLink eligibility report (read-only)

After scanning the local ROM library and placing the optional Libretro GB/GBC/GBA DAT files, build a report from the persistent index:

```sh
python3 /userdata/system/netlink/index.py --rom-root /userdata/roms
python3 /userdata/system/netlink/report.py \
  --index /userdata/system/configs/netlink/index.json \
  --output /userdata/system/configs/netlink/eligibility.jsonl
```

Each JSONL row contains `rom_identity` (`exact`, `advisory_metadata`, or `unidentified`), `rom_identification_source` (curated hash, No-Intro SHA-1, or metadata), `hardware_status` (`documented`, `other_multiplayer`, or `unknown`), transport-specific `hardware` flags, relevant `guide_titles`, registry `game_ids`, and separate `netlink_readiness`, `host_enabled`, `join_enabled` fields. A verified No-Intro SHA-1 identity can supply a normalized title for exact matching against the ReyVGM *Game Boy* guide, even for opaque ROM filenames. Game Boy Color and GBA are never matched to that GB-only guide.

**Host/Join are always disabled for now.** A playable game, No-Intro hash match, physical link support, or emulator boot test does not prove working two-device network transport. This report is intended for future EmulationStation UI consumption only. It does not change NetPlay settings, game lists, saves, or default launchers.

Run regression tests on Ubuntu first:

```sh
python3 -m unittest discover -s netlink/tests -v
```

## Two-machine Gambatte NetLink LAN test (experimental)

This test uses the custom Gambatte `gambatte-hb-link-6` **RetroArch netpacket** interface, not a separate socket/server. A core already proven to load a local ROM is not yet proof of two-peer link gameplay. Do not enable EmulationStation Host/Join actions until both machines actually complete a game link session.

Use the same patched core build on both Batocera hosts and the **same Tetris ROM SHA-1**. Exit running RetroArch instances before testing. The new helper is **dry-run by default**; it prints core SHA-256 and ROM SHA-1 and checks the embedded protocol string. It does not write system settings.

```sh
# Both machines: verify core and ROM without starting RetroArch
bash /userdata/system/netlink/tools/test_gambatte_lan.sh \
  --role host --rom '/userdata/roms/gb/Tetris (World) (Rev A).gb'

# On ginryuus-Emulation-Box (known LAN IP 10.8.76.244), then repeat with --launch
bash /userdata/system/netlink/tools/test_gambatte_lan.sh \
  --role host --rom '/userdata/roms/gb/Tetris (World) (Rev A).gb' --launch

# On seidouryuus-Emulation-Laptop, join the box's IP
bash /userdata/system/netlink/tools/test_gambatte_lan.sh \
  --role join --peer 10.8.76.244 \
  --rom '/userdata/roms/gb/Tetris (World) (Rev A).gb' --launch
```

For either machine, adjust `--rom` if its actual path differs. The custom libretro core defaults to `/usr/lib/libretro/gambatte_link_libretro.so`; if your installation differs use `--core /path/to/core.so`. The RetroArch netplay port defaults to 55435; for a different port use the same `--port` on both. To use an existing config explicitly add `--config /path/to/retroarch.cfg`. Run sessions from the machine's graphical environment: SSH alone may lack its display/audio environment.

Before trying gameplay compare the printed SHA-256 of the two cores and SHA-1 of both Tetris ROMs. Protocol markers matching without identical core builds is **not** sufficient to guarantee consistent behavior. When a session runs, record whether the guest connects, whether both sides reach Tetris 2P/versus, whether moves and garbage transfer, and whether the link survives a full round. Do not mark compatibility `network_verified` until the serial gameplay test is completed. No game save files or global Batocera settings are modified by the test helper; RetroArch itself may write its normal runtime saves/configuration depending on existing settings.

The host and join commands match RetroArch's `--host`, `--connect`, `--port`, `--libretro` CLI options. These are *experiment* sessions, not EmulationStation actions.


## Verified first two-host link session (2026-11-23)

**Tetris (World) (Rev A), GB: network verified by live two-machine test.** Both
machines used the same inner ROM SHA-1
`74591cc9501af93873f9a5d3eb12da12c0723bbc` and the same patched
Gambatte core SHA-256
`0c8db0ead8ae814d2e65fd7bc867e767344dad37fc0c42380063b4a7b44b26b2`.
The protocol was `gambatte-hb-link-6`, using RetroArch 1.22.2 on
`ginryuus-Emulation-Box` (host) and `seidouryuus-Emulation-Laptop` (client).
Live session logs confirmed host and guest netpacket initialization and
connection. The user confirmed both sides entered two-player gameplay, exchanged
penalty blocks bidirectionally and completed a round.

The curated database now records `compatibility: network_verified` for this
**specific** Tetris revision/core/protocol test. The read-only eligibility
report emits `netlink_readiness: manual_verified` only if the same exact
ROM SHA-1 appears in a No-Intro exact match and a passing test record; other
ROM revisions remain unverified. `host_enabled` and `join_enabled` stay
`false` until safe EmulationStation menu actions and session management are
implemented and tested. Re-run indexing and reporting after deployment.

Next implementation phase: an explicit per-title EmulationStation Host/Join
integration guarded by exact hash, matching core build, and supported transport.
Do not modify systemwide RetroArch netplay defaults or automatically enroll
other ROMs in link play.

## Exact-fingerprint NetLink session launcher (pre-EmulationStation integration)

`launch.py` is the validated **launch boundary** for a future per-game
EmulationStation **Host NetLink / Join NetLink** menu, not yet an actual ES menu
extension. It checks the *inner* GB/GBC ROM SHA-1 even if the file is ZIP
compressed, the installed custom core SHA-256, protocol, and a passing
`network_tests` record for the exact combination before preparing RetroArch
`--host` or `--connect`. A title similarity or hardware capability flag
is insufficient. It refuses unverified ROM/core combinations. Default behavior
is read-only preflight; `--launch` is explicitly required to start RetroArch.

This is currently gated to the Tetris (World) (Rev A) tested combination:

```sh
# On ginryuus-Emulation-Box, preflight first
python3 /userdata/system/netlink/launch.py --role host \
  --rom '/userdata/roms/gb/Tetris (World) (Rev A).zip'

# Host live (only after preflight)
python3 /userdata/system/netlink/launch.py --role host \
  --rom '/userdata/roms/gb/Tetris (World) (Rev A).zip' --launch

# Join live, from seidouryuus-Emulation-Laptop
python3 /userdata/system/netlink/launch.py --role join \
  --peer 10.8.76.244 \
  --rom '/userdata/roms/gb/Tetris (World) (Rev A).zip' --launch
```

Default core is `/userdata/system/custom-cores/gambatte_link_libretro.so`,
the validated installation path. `--core` permits an alternative path but
**never** bypasses the pinned binary fingerprint. `--peer` must be a literal
unicast IP; `--port` defaults to 55435. Use `--config` only if a specific
RetroArch configuration is required. ROMs must remain under `/userdata/roms`.

To exercise the synthetic tests: `python3 -m unittest discover -s
netlink/tests -v`. These new tests have not yet been run on actual Batocera
hosts. The launcher intentionally does not alter game metadata or save files;
RetroArch itself may create or update its usual runtime configuration when
started.

The *next* change belongs in Batocera's pinned EmulationStation source
(`batocera-emulationstation`, package version
`3c8f8fc7465633257210565935580617418362b7`):
`es-app/src/guis/GuiGameOptions.cpp` owns the game's action menu and currently
offers generic `START A NETPLAY GAME`. Native NetLink entries must use the
fingerprint-gated launcher and a proper ES game launch lifecycle/return path,
rather than hijacking generic Netplay or changing global core selection.
Until that integration is implemented and tested, report
`host_enabled=false`, `join_enabled=false`.

## Native EmulationStation menu patch (Phase 14, build pending)

An experimental patch is committed at
`package/batocera/emulationstation/batocera-emulationstation/005-netlink-verified-tetris-menu.patch`.
It is authored against the Batocera package's pinned EmulationStation revision
`3c8f8fc7465633257210565935580617418362b7`. The patch modifies
`FileData.h`, `FileData.cpp`, and `GuiGameOptions.cpp`:

- Adds separate `netLinkRole` and `netLinkPeer` launch options, which are
  independent of Batocera's generic Netplay mode.
- Adds **HOST NETLINK GAME** and **JOIN NETLINK GAME** to game options only for
  `gb/Tetris (World) (Rev A).zip` as a *provisional UI filter*. This filename
  is not trusted as identity: the launch backend still enforces the exact
  ROM SHA-1 and custom core SHA-256 against the verified database record.
- JOIN prompts for the host IP using EmulationStation's text edit popup.
  The Python backend rejects malformed or invalid peer addresses.
- Uses `ViewController::launch` and the existing `FileData::launchGame`
  lifecycle so the frontend deinitializes before the emulator starts and
  reinitializes upon exit. Generic single-player launch is untouched.
- Calls `python3 /userdata/system/netlink/launch.py ... --launch`.
  The interpreter and script must be deployed before enabling the patch.

**Status:** Patch context was checked against the exact pinned source files;
the EmulationStation C++ binary has **not yet been compiled, installed, or
tested**. This source patch will only appear in a future custom Batocera
build, not merely by updating `/userdata/system/netlink` on stock Batocera.
Maintain a stock bootable system/image until that build passes a full
compile and hardware return-to-menu test. The current report's
`host_enabled` and `join_enabled` remain disabled.

For integration validation: (1) compile ES with the patch, (2) verify normal
single-player launches and return to ES, (3) verify the two NetLink entries
appear for only the provisional Tetris selection, (4) test malformed IP
rejection and hash mismatch refusal, (5) Host/Join a linked Tetris round,
(6) exit RetroArch on both hosts and confirm ES reinitializes normally.

## Phase 14 build validation on an Ubuntu x86_64 development host

The NetLink menu patch was checked against the pinned upstream files and its
unified-diff hunk sizes, but this development session does not have the full
Batocera Buildroot source/toolchain or a prepared output tree. A compiled ES
executable has **not** been produced. Never replace the stock ES binary on
either production machine just because source applicability passes.

With the `feature/handheld-network-link` checkout in `~/src/batocera-netlink`:

```sh
cd ~/src/batocera-netlink
git pull --ff-only

# Fetch the exact pinned ES sources into a *separate* checkout.
git clone https://github.com/batocera-linux/batocera-emulationstation.git /tmp/netlink-es-check
git -C /tmp/netlink-es-check checkout --detach 3c8f8fc7465633257210565935580617418362b7

# Read-only patch applicability verification; does not alter ES files:
python3 netlink/tools/check_es_patch.py --es-source /tmp/netlink-es-check

# Optional direct check with an absolute patch path:
PATCH="$PWD/package/batocera/emulationstation/batocera-emulationstation/005-netlink-verified-tetris-menu.patch"
git -C /tmp/netlink-es-check apply --check "$PATCH"
```

For an **existing configured** x86_64 Buildroot development tree, Batocera's
top-level Makefile supports targeted package builds:

```sh
make x86_64-pkg PKG=batocera-emulationstation-dirclean
make x86_64-pkg PKG=batocera-emulationstation
```

`dirclean` ensures the package is re-extracted and the new `005` patch is
actually applied (instead of reusing a stale, already-patched build stamp).
These commands depend on a configured toolchain/output tree and may need to
download/build prerequisite packages. Keep this build separate from the
working Batocera devices. Inspect build logs and verify `HOST NETLINK GAME`
and `JOIN NETLINK GAME` strings in the newly built binary before *any*
controlled installation trial.
