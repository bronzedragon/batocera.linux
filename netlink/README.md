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
