import sys
from pathlib import Path


def package_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):  # ejecutable de PyInstaller
        return Path(sys._MEIPASS) / "anyelo_qr"
    return Path(__file__).resolve().parent


def asset(name: str) -> Path:
    return package_dir() / "assets" / name


DEFAULT_LOGO = asset("logo.png")
