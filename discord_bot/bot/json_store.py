from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    """Simple JSON file loader with explicit save support."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
