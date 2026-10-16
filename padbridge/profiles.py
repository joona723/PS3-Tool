"""Per-controller button-mapping profiles, stored as JSON in the profiles/ folder.

A profile maps each Xbox control to where it comes from on the real controller:
  {"type": "button", "index": 3}                       a button
  {"type": "hat", "index": 0, "dir": "up"}             one direction of a D-pad hat
  {"type": "axis", "index": 1, "invert": true}         a full stick axis (-1..1)
  {"type": "half", "index": 4, "rest": -1, "sign": 1}  part of an axis used as a button/trigger
"""
import json
import re
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _path_for(guid):
    return PROFILE_DIR / f"{re.sub(r'[^0-9a-zA-Z]', '', guid)}.json"


def load_profile(guid):
    path = _path_for(guid)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_profile(guid, name, bindings):
    PROFILE_DIR.mkdir(exist_ok=True)
    path = _path_for(guid)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"name": name, "guid": guid, "bindings": bindings}, f, indent=2)
    return path


def delete_profile(guid):
    path = _path_for(guid)
    if path.exists():
        path.unlink()
        return True
    return False
