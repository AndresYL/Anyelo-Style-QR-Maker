"""Atajo de teclado global (solo Windows) usando RegisterHotKey, sin espiar el teclado."""
from __future__ import annotations

import ctypes
import sys
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL, "shift": MOD_SHIFT,
         "meta": MOD_WIN, "win": MOD_WIN}


def parse_hotkey(text: str) -> tuple[int, int]:
    """'Ctrl+Alt+Q' -> (modificadores, código de tecla virtual). Lanza ValueError si no sirve."""
    mods, key = 0, None
    for part in (p.strip() for p in text.split("+") if p.strip()):
        low = part.lower()
        if low in _MODS:
            mods |= _MODS[low]
        elif key is None:
            key = part.upper()
        else:
            raise ValueError("Usa una sola tecla junto a los modificadores.")
    if key is None:
        raise ValueError("Falta la tecla.")
    if not mods & (MOD_ALT | MOD_CONTROL | MOD_WIN):
        raise ValueError("Incluye Ctrl, Alt o Windows, para no estorbar cuando escribes.")
    if len(key) == 1 and (key.isalpha() or key.isdigit()) and key.isascii():
        return mods, ord(key)
    if key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        return mods, 0x6F + int(key[1:])
    raise ValueError("Usa una letra, un número o una tecla F1 a F12.")


def vk_to_name(vk: int) -> str | None:
    """Código de tecla virtual de Windows -> nombre (letras, números y F1 a F12)."""
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x7B:
        return f"F{vk - 0x6F}"
    return None


def format_hotkey(mods: int, vk: int) -> str:
    parts = []
    if mods & MOD_CONTROL:
        parts.append("Ctrl")
    if mods & MOD_ALT:
        parts.append("Alt")
    if mods & MOD_SHIFT:
        parts.append("Shift")
    if mods & MOD_WIN:
        parts.append("Win")
    name = vk_to_name(vk)
    if not name:
        raise ValueError("Usa una letra, un número o una tecla F1 a F12.")
    return "+".join(parts + [name])


def altgr_conflict(text: str) -> str | None:
    """Carácter que escribiría esta combinación en el teclado actual (por ejemplo «@»), si lo hay."""
    from .winfx import altgr_char
    try:
        mods, vk = parse_hotkey(text)
    except ValueError:
        return None
    if mods & MOD_CONTROL and mods & MOD_ALT:
        return altgr_char(vk, bool(mods & MOD_SHIFT))
    return None


FACTORY_HOTKEY = "Ctrl+Alt+Q"


def default_hotkey() -> str:
    """Ctrl+Alt+Q si no choca con tu teclado; si choca (AltGr+Q = @), la alternativa más cercana."""
    for cand in (FACTORY_HOTKEY, "Ctrl+Shift+Q", "Ctrl+Alt+Shift+Q"):
        if altgr_conflict(cand) is None:
            return cand
    return "Ctrl+Shift+Q"


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback: Callable[[], None]):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        try:
            name = bytes(eventType).decode()
        except TypeError:
            name = str(eventType)
        if name == "windows_generic_MSG":
            import ctypes.wintypes as wt
            msg = wt.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0


class GlobalHotkey:
    ID = 0xA57E

    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self._filter: _Filter | None = None
        self.active = False

    @staticmethod
    def supported() -> bool:
        return sys.platform == "win32"

    def register(self, text: str) -> tuple[bool, str]:
        self.unregister()
        if not self.supported():
            return False, "El atajo global solo funciona en Windows."
        try:
            mods, vk = parse_hotkey(text)
        except ValueError as exc:
            return False, str(exc)
        if not ctypes.windll.user32.RegisterHotKey(None, self.ID, mods | MOD_NOREPEAT, vk):
            return False, "Otro programa ya usa ese atajo. Prueba con otro."
        self._filter = _Filter(self.ID, self.callback)
        QCoreApplication.instance().installNativeEventFilter(self._filter)
        self.active = True
        return True, ""

    def unregister(self) -> None:
        if self.active and self.supported():
            ctypes.windll.user32.UnregisterHotKey(None, self.ID)
        if self._filter is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)
        self._filter = None
        self.active = False
