"""Detalles de Windows: barra de título oscura y detección de teclas que ya escriben un carácter."""
from __future__ import annotations

import sys

IS_WIN = sys.platform == "win32"


def _hex_to_colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def style_titlebar(hwnd: int, caption: str, text: str) -> None:
    """Barra de título negra con texto hueso (Windows 10 oscuro; Windows 11 con el color exacto)."""
    if not IS_WIN:
        return
    try:
        import ctypes
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 en Windows 10 antiguo)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), ctypes.sizeof(on))
        cap, txt = ctypes.c_int(_hex_to_colorref(caption)), ctypes.c_int(_hex_to_colorref(text))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), ctypes.sizeof(cap))   # color de la barra (Win 11)
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(txt), ctypes.sizeof(txt))   # color del texto (Win 11)
    except Exception:
        pass


def altgr_char(vk: int, shift: bool = False) -> str | None:
    """Si Ctrl+Alt+<tecla> escribe un carácter en el teclado actual (AltGr), lo devuelve.
    Ejemplo: en teclado español latinoamericano, Ctrl+Alt+Q escribe «@»."""
    if not IS_WIN:
        return None
    try:
        import ctypes
        u = ctypes.windll.user32
        hkl = u.GetKeyboardLayout(0)
        state = (ctypes.c_ubyte * 256)()
        for k in (0x11, 0x12, 0xA2, 0xA5):          # Ctrl, Alt, Ctrl izq., Alt der. (AltGr)
            state[k] = 0x80
        if shift:
            state[0x10] = 0x80
        scan = u.MapVirtualKeyExW(vk, 0, hkl)
        buf = ctypes.create_unicode_buffer(8)
        n = u.ToUnicodeEx(vk, scan, state, buf, 8, 0x4, hkl)
        if n == 1 and buf[0].isprintable() and not buf[0].isspace():
            return buf[0]
    except Exception:
        pass
    return None
