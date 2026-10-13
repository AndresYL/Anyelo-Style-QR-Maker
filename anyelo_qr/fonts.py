"""Tipografía Bricolage Grotesque (la misma de la página), empaquetada en el programa."""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from .paths import asset

_FILES = {"regular": "BricolageGrotesque-Regular.ttf", "semibold": "BricolageGrotesque-SemiBold.ttf",
          "bold": "BricolageGrotesque-Bold.ttf", "xbold": "BricolageGrotesque-ExtraBold.ttf"}
_FAMILY = {"regular": "Bricolage Grotesque", "semibold": "Bricolage Grotesque SemiBold",
           "bold": "Bricolage Grotesque Bold", "xbold": "Bricolage Grotesque ExtraBold"}
_loaded = False


def load_fonts() -> bool:
    """Registra las fuentes. Si algo falla, el programa usa Segoe UI y sigue funcionando."""
    global _loaded
    ok = True
    for key, name in _FILES.items():
        path = asset("fonts/" + name)
        if not path.exists() or QFontDatabase.addApplicationFont(str(path)) < 0:
            ok = False
    _loaded = ok
    return ok


def family(kind: str = "regular") -> str:
    return _FAMILY[kind] if _loaded else "Segoe UI"


def font(kind: str = "regular", px: int = 13, tracking: float = 0.0, caps: bool = False) -> QFont:
    """kind: regular | semibold | bold | xbold. tracking: separación entre letras en píxeles."""
    f = QFont(family(kind))
    f.setPixelSize(px)
    if not _loaded and kind != "regular":
        f.setBold(True)
    if tracking:
        f.setLetterSpacing(QFont.AbsoluteSpacing, tracking)
    if caps:
        f.setCapitalization(QFont.AllUppercase)
    return f
