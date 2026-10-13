"""Lectura de códigos QR desde imágenes, PDFs y carpetas, y chequeo básico de links."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import zxingcpp
from PIL import Image, ImageOps

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "tiny.cc", "rb.gy", "lnkd.in", "qrco.de",
}


@dataclass
class Found:
    source: str
    page: int | None
    text: str
    kind: str
    warnings: list[str] = field(default_factory=list)


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://\S+$", text.strip(), re.I))


def analyze_link(text: str) -> list[str]:
    """Avisos de seguridad para un link. Lista vacía si no hay nada raro."""
    if not is_url(text):
        return []
    warns: list[str] = []
    u = urlparse(text.strip())
    host = (u.hostname or "").lower()
    if u.scheme.lower() == "http":
        warns.append("Usa http sin cifrar")
    if host in SHORTENERS:
        warns.append("Acortador: el destino final queda oculto")
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        warns.append("Apunta a una dirección IP, no a un dominio")
    if "xn--" in host:
        warns.append("Dominio con caracteres internacionales (puede imitar otro)")
    if host.count(".") >= 4:
        warns.append("Demasiados subdominios")
    if u.username:
        warns.append("Trae un usuario antes del dominio (truco típico de phishing)")
    return warns


def read_pil(img: Image.Image) -> list[tuple[str, str]]:
    """Devuelve [(texto, tipo)] de todo lo que se pueda leer en la imagen."""
    base = img.convert("RGBA")
    flat = Image.new("RGBA", base.size, (255, 255, 255, 255))
    flat.alpha_composite(base)
    rgb = flat.convert("RGB")

    attempts = [rgb, ImageOps.autocontrast(rgb.convert("L"))]
    if max(rgb.size) > 2400:
        attempts.append(rgb.resize((rgb.width // 2, rgb.height // 2), Image.LANCZOS))
    if max(rgb.size) < 500:  # recortes pequeños (por ejemplo, de la pantalla)
        attempts.append(rgb.resize((rgb.width * 3, rgb.height * 3), Image.LANCZOS))
    for cand in attempts:
        res = zxingcpp.read_barcodes(cand)
        if res:
            out = []
            for r in res:
                kind = getattr(r.format, "name", str(r.format)).replace("BarcodeFormat.", "")
                out.append((r.text, kind))
            return out
    return []


def _found(source: str, page: int | None, pairs: list[tuple[str, str]]) -> list[Found]:
    return [Found(source, page, t, k, analyze_link(t)) for t, k in pairs]


def read_image_file(path: Path) -> list[Found]:
    with Image.open(path) as im:
        im.load()
        return _found(str(path), None, read_pil(im))


def read_pdf_file(path: Path) -> list[Found]:
    import pypdfium2 as pdfium

    out: list[Found] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            pil = page.render(scale=2.5).to_pil()
            out.extend(_found(str(path), i + 1, read_pil(pil)))
    finally:
        pdf.close()
    return out


def collect_files(paths: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(f for f in p.rglob("*") if f.suffix.lower() in IMAGE_EXT | PDF_EXT))
        elif p.suffix.lower() in IMAGE_EXT | PDF_EXT:
            files.append(p)
    return files


def read_paths(
    paths: list[str | Path], progress: Callable[[int, int], None] | None = None
) -> tuple[list[Found], list[str]]:
    """Lee archivos y carpetas. Devuelve (hallazgos, errores)."""
    files = collect_files(paths)
    results: list[Found] = []
    errors: list[str] = []
    for i, f in enumerate(files):
        try:
            if f.suffix.lower() in PDF_EXT:
                results.extend(read_pdf_file(f))
            else:
                results.extend(read_image_file(f))
        except Exception as exc:  # archivo dañado, PDF con clave, etc.
            errors.append(f"{f.name}: {exc}")
        if progress:
            progress(i + 1, len(files))
    return results, errors
