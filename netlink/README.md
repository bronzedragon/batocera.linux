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
