#!/usr/bin/env bash
set -euo pipefail
usage() {
  echo 'Usage: test_gambatte_lan.sh --role host|join --rom /path/game.gb [--peer HOST] [--port 55435] [--core /path/core.so] [--config /path/retroarch.cfg] [--launch]'
}
ROLE=""; ROM=""; PEER=""; PORT="55435"; CORE="/usr/lib/libretro/gambatte_link_libretro.so"; CONFIG=""; LAUNCH=0
while (($#)); do
  case "$1" in
    --role|--rom|--peer|--port|--core|--config)
      (($# >= 2)) || { usage >&2; exit 2; }
      case "$1" in
        --role) ROLE="$2";; --rom) ROM="$2";; --peer) PEER="$2";;
        --port) PORT="$2";; --core) CORE="$2";; --config) CONFIG="$2";;
      esac
      shift 2;;
    --launch) LAUNCH=1; shift;;
    -h|--help) usage; exit 0;;
    *) usage >&2; exit 2;;
  esac
done
[[ "$ROLE" == host || "$ROLE" == join ]] || { usage >&2; exit 2; }
[[ -n "$ROM" && -f "$ROM" ]] || { echo "ROM not found: $ROM" >&2; exit 2; }
[[ -f "$CORE" ]] || { echo "Core not found: $CORE" >&2; exit 2; }
[[ "$PORT" =~ ^[0-9]+$ ]] && ((10#$PORT >= 1 && 10#$PORT <= 65535)) || { echo "Invalid port" >&2; exit 2; }
[[ "$ROLE" != join || -n "$PEER" ]] || { echo "Join needs --peer" >&2; exit 2; }
[[ -z "$CONFIG" || -f "$CONFIG" ]] || { echo "Config not found: $CONFIG" >&2; exit 2; }
for tool in retroarch sha1sum sha256sum python3; do
  command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }
done
if ! python3 - "$CORE" <<'PY'
import pathlib
import sys
with pathlib.Path(sys.argv[1]).open("rb") as stream:
    found = b"gambatte-hb-link-6" in stream.read()
sys.exit(0 if found else 1)
PY
then
  echo 'Core does not contain protocol marker gambatte-hb-link-6' >&2
  exit 2
fi
printf 'Role: %s | Port: %s | Peer: %s\n' "$ROLE" "$PORT" "$PEER"
printf 'Core: %s\n' "$CORE"
sha256sum "$CORE"
printf 'ROM: %s\n' "$ROM"
sha1sum "$ROM"
cmd=(retroarch --verbose --libretro "$CORE" --port "$PORT")
[[ -z "$CONFIG" ]] || cmd+=(--config "$CONFIG")
if [[ "$ROLE" == host ]]; then cmd+=(--host); else cmd+=(--connect "$PEER"); fi
cmd+=("$ROM")
printf 'Command: '; printf '%q ' "${cmd[@]}"; printf '\n'
if (( ! LAUNCH )); then
  echo 'PREFLIGHT ONLY. Use --launch on both machines to start the test.'
  exit 0
fi
echo 'Launching foreground RetroArch. EmulationStation settings remain unchanged.'
exec "${cmd[@]}"
