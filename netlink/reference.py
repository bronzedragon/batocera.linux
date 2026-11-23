"""Conservative title matching against the user-supplied ReyVGM GB guide.

Reference matches are *hardware evidence*, never proof of NetLink compatibility.
"""
import re
import unicodedata
from pathlib import Path

SOURCE = "https://gamefaqs.gamespot.com/gameboy/916375-game-boy/faqs/82719"

# Only aliases with unambiguous, documented equivalence. Do not fuzzy-match substrings.
EXPLICIT_ALIASES = {
    "pokémon: red version / pocket monsters aka": ["Pokemon Red", "Pokémon Red"],
    "pokémon: blue version / pocket monsters ao": ["Pokemon Blue", "Pokémon Blue"],
    "pokémon: special pikachu edition - yellow version / pocket monsters pikachu":
        ["Pokemon Yellow", "Pokémon Yellow"],
}
RELEASE_SUFFIX = re.compile(
    r"\s*\((?:usa|europe|japan|world|asia|australia|france|germany|"
    r"rev(?:ision)?\b|beta\b|proto\b|sgb\b|en\b|unl\b|unknown\b)[^)]*\)",
    flags=re.IGNORECASE,
)

def normalize(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())

def name_candidates(file_name, header_title=""):
    stem = Path(file_name).stem
    clean_stem = RELEASE_SUFFIX.sub("", stem).strip()
    return {normalize(v) for v in (clean_stem, header_title) if normalize(v)}

def catalog_matches(file_name, header_title, system, catalog):
    if system != "gb":  # This specific guide expressly excludes GBC games.
        return []
    candidates = name_candidates(file_name, header_title)
    found = []
    for entry in catalog.get("games", []):
        if entry.get("system") != "gb":
            continue
        title = entry["title"]
        aliases = [title, *EXPLICIT_ALIASES.get(title.casefold(), [])]
        # Slash-separated regional names are alternate titles. Keep separate
        # instead of matching arbitrary substrings such as 'Tetris' in 'Tetris 2'.
        aliases += [part.strip() for part in title.split(" / ")]
        if not candidates.intersection(normalize(alias) for alias in aliases):
            continue
        modes = entry.get("modes", [])
        link_modes = [m for m in modes if any(
            m.get("links", {}).get(k, False) for k in
            ("cable", "four_player_adapter", "infrared", "gbkiss")
        ) and not m.get("no_link")]
        found.append({
            "title": title,
            "source": catalog.get("source", SOURCE),
            "source_line": entry.get("source_line"),
            "hardware_link_capable": bool(link_modes),
            "modes": modes,
            "evidence": "guide_exact_title"
        })
    return found
