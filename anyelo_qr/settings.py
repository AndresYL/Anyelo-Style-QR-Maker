from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .brand import DEFAULT_BG, DEFAULT_FG


def settings_path() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "AnyeloStyleQR" / "settings.json"


@dataclass
class Settings:
    out_dir: str = ""
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    scale: int = 12
    error: str = "m"
    logo_mode: str = "default"      # default | none | custom
    logo_custom: str = ""
    logo_ratio: float = 0.22
    fmts: list[str] = field(default_factory=lambda: ["png", "svg"])
    add_https: bool = True
    skip_dupes: bool = True
    verify: bool = True
    overwrite: bool = False

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(settings_path().read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        except Exception:
            return cls()

    def save(self) -> None:
        try:
            p = settings_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
