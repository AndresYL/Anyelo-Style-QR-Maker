from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .brand import DEFAULT_BG, DEFAULT_FG

SCHEMA = 3


def settings_path() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "AnyeloStyleQR" / "settings.json"


def _sane_hotkey(value: str, migrating: bool) -> str:
    """Un atajo guardado que no sirve (por ejemplo «Ctrl+Alt+@») vuelve al recomendado."""
    from .hotkey import FACTORY_HOTKEY, altgr_conflict, default_hotkey, parse_hotkey
    if not value:
        return default_hotkey()
    try:
        parse_hotkey(value)
    except ValueError:
        return default_hotkey()
    if migrating and value == FACTORY_HOTKEY and altgr_conflict(value):
        return default_hotkey()      # el de fábrica de la v0.2 quitaba la @ en teclados latinoamericanos
    return value


@dataclass
class Settings:
    schema: int = SCHEMA
    # destino
    out_dir: str = ""
    fmts: list[str] = field(default_factory=lambda: ["png", "svg"])
    open_after: bool = True
    # estilo del QR
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    qr_px: int = 1000
    error: str = "m"
    shape: str = "square"
    eye_shape: str = "square"
    eye_color_on: bool = False
    eye_color: str = "#000000"
    logo_mode: str = "none"         # none | default | custom
    logo_custom: str = ""
    logo_ratio: float = 0.22
    logo_border: bool = True
    # opciones de generación
    add_https: bool = True
    skip_dupes: bool = True
    verify: bool = True
    overwrite: bool = False
    # atajo global
    hotkey_enabled: bool = True
    hotkey: str = ""             # vacío = el recomendado para tu teclado
    keep_running: bool = True

    def __post_init__(self):
        if not self.hotkey:
            from .hotkey import default_hotkey
            self.hotkey = default_hotkey()

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(settings_path().read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            s = cls(**{k: v for k, v in data.items() if k in known})
            if data.get("schema", 1) < 2:      # la v0.1 traía el logo activado por defecto
                s.logo_mode = "none"
            s.hotkey = _sane_hotkey(s.hotkey, migrating=data.get("schema", 1) < 3)
            s.schema = SCHEMA
            return s
        except Exception:
            s = cls()
            s.hotkey = _sane_hotkey("", False)
            return s

    def save(self) -> None:
        try:
            p = settings_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
