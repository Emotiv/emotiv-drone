"""
High-score table for the 60-second ring run.

Deliberately a plain JSON file next to the app's other settings: this is a
single-machine party game — several people take turns on one headset — so there
is no server, no account, and nothing to sync. Same directory as config.json,
which means it survives an app update and never lands inside a read-only bundle.
"""

import json
import os
import time

from app_paths import user_data_dir

LEADERBOARD_FILE = os.path.join(user_data_dir(), "leaderboard.json")

# Keep the file from growing without bound on a machine used for demos all day.
MAX_ENTRIES = 200


def _sort_key(entry):
    # Higher score first; on a tie the earlier run wins, so beating someone
    # requires actually beating them, not just matching them.
    return (-int(entry.get("score", 0)), float(entry.get("time", 0)))


def load() -> list:
    """Every stored run, best first. A corrupt file is treated as empty."""
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        print(f"[leaderboard] could not read {LEADERBOARD_FILE}: {e}")
        return []
    if not isinstance(entries, list):
        return []
    clean = [e for e in entries if isinstance(e, dict) and "score" in e]
    clean.sort(key=_sort_key)
    return clean


def save(entries: list) -> None:
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(entries[:MAX_ENTRIES], f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[leaderboard] could not write {LEADERBOARD_FILE}: {e}")


def add(name: str, score: int, coins: int = 0, profile: str = "") -> dict:
    """Record one run and return the stored entry.

    The returned dict is the same object that lives in the list, so callers can
    identify their own row later even when several runs share a name and score.
    """
    entry = {
        "name": (name or "").strip() or "Player",
        "score": int(score),
        "coins": int(coins),
        "profile": profile or "",
        "time": time.time(),
    }
    entries = load()
    entries.append(entry)
    entries.sort(key=_sort_key)
    save(entries)
    return entry


def rank_of(entry: dict, entries: list = None) -> int:
    """1-based position of `entry`. 0 when it is not in the table."""
    entries = load() if entries is None else entries
    for i, e in enumerate(entries):
        if e is entry or (
            e.get("time") == entry.get("time")
            and e.get("name") == entry.get("name")
            and e.get("score") == entry.get("score")
        ):
            return i + 1
    return 0


def top(count: int = 10) -> list:
    return load()[:count]


def clear() -> None:
    save([])
