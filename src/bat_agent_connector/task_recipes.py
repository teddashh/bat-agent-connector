"""Bundled Goose-compatible YAML recipes (JSON is a YAML subset)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent / "recipes"
CAPS = {"feature-to-staging": (5, 2), "bugfix-with-tests": (5, 2),
        "small-task-with-tests": (2, 0)}


def load(name: str) -> dict:
    if name not in CAPS:
        raise ValueError("unknown task recipe")
    recipe = json.loads((ROOT / (name + ".yaml")).read_text())
    if not all(recipe.get(k) for k in ("title", "description", "instructions", "prompt")):
        raise ValueError("incomplete task recipe")
    return recipe


def limits(name: str) -> tuple[int, int]:
    load(name)
    return CAPS[name]
