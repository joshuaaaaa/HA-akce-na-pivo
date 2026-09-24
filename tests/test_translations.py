"""Překlady nesmí obsahovat {proměnné}, které kód nedodává (frontend pak hlásí MISSING_VALUE)."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "akce_na_pivo"
FILES = [ROOT / "strings.json", *sorted((ROOT / "translations").glob("*.json"))]

# proměnné, které integrace opravdu předává (description_placeholders / translation_placeholders)
PROVIDED = {
    ("config", "step", "settings"): {"country"},
    ("options", "step", "init"): {"country"},
    ("entity", "sensor", "rank"): {"rank"},
    ("entity", "sensor", "brand"): {"brand"},
    ("entity", "sensor", "where_brand"): {"brand"},
}


def _walk(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*path, key))
    elif isinstance(node, str):
        yield path, node


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_placeholders_are_provided(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for key_path, text in _walk(data):
        used = set(re.findall(r"\{(\w+)\}", text))
        allowed = set()
        for prefix, names in PROVIDED.items():
            if key_path[: len(prefix)] == prefix:
                allowed |= names
        assert used <= allowed, f"{path.name}: {'.'.join(key_path)} používá {used - allowed}"
