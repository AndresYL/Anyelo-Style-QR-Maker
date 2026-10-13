"""Generación de QR (PNG, SVG, PDF), logo central, lotes y verificación."""
from __future__ import annotations

import base64
import io
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import segno
from PIL import Image, ImageDraw

from .reader import read_pil

FORMATS = ("png", "svg", "pdf")
ERROR_LEVELS = {"l": "Baja (7%)", "m": "Media (15%)", "q": "Alta (25%)", "h": "Máxima (30%)"}
MAX_LOGO_RATIO = 0.30


@dataclass(frozen=True)
class QRStyle:
    fg: str = "#000000"
    bg: str = "#FFFFFF"
    scale: int = 12          # píxeles por módulo
    border: int = 4          # zona de silencio, en módulos
    error: str = "m"
    logo: str | None = None  # ruta del logo central
    logo_ratio: float = 0.22  # ancho del logo / ancho de los módulos

    @property
    def effective_error(self) -> str:
        return "h" if self.logo else self.error

    @property
    def ratio(self) -> float:
        return min(max(self.logo_ratio, 0.10), MAX_LOGO_RATIO)


# ---------- colores ----------

def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def ch(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(ch, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _luminance(_rgb(a)), _luminance(_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def style_warnings(style: QRStyle) -> list[str]:
    out = []
    if contrast_ratio(style.fg, style.bg) < 3:
        out.append("Poco contraste entre los colores: muchos lectores no van a poder leer este QR.")
    if style.logo and style.logo_ratio > 0.26:
        out.append("El logo es grande y tapa mucho código. Bájalo a 22% o menos si el QR se va a imprimir pequeño.")
    return out


# ---------- logo ----------

@lru_cache(maxsize=8)
def _load_logo(path: str, mtime: float) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im


def load_logo(path: str) -> Image.Image:
    return _load_logo(path, Path(path).stat().st_mtime).copy()


def _is_light_mark(logo: Image.Image) -> bool:
    """True si el logo es blanco con partes transparentes (como el de Anyelo Style)."""
    small = logo.resize((64, 64))
    px = [small.getpixel((x, y)) for x in range(64) for y in range(64) if small.getpixel((x, y))[3] > 200]
    if not px:
        return False
    return sum(min(p[:3]) for p in px) / len(px) > 235


def _backing(w: int, h: int, color: tuple[int, int, int], circle: bool) -> Image.Image:
    k = 4
    mask = Image.new("L", (w * k, h * k), 0)
    d = ImageDraw.Draw(mask)
    if circle:
        d.ellipse((0, 0, w * k - 1, h * k - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=int(min(w, h) * k * 0.22), fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), color + (255,))
    out.putalpha(mask)
    return out


def _mark_color(style: QRStyle) -> str:
    """Color detrás de un logo blanco: el más oscuro de los dos, para que las letras se lean."""
    c = style.fg if _luminance(_rgb(style.fg)) <= _luminance(_rgb(style.bg)) else style.bg
    return c if _luminance(_rgb(c)) < 0.4 else "#000000"


def _logo_geometry(modules_px: float, logo: Image.Image, ratio: float):
    d = max(int(modules_px * ratio), 16)
    lw, lh = logo.size
    s = d / max(lw, lh)
    return max(int(lw * s), 1), max(int(lh * s), 1)


def _overlay_logo(img: Image.Image, style: QRStyle) -> Image.Image:
    logo = load_logo(style.logo)
    light = _is_light_mark(logo)
    modules_px = img.width - 2 * style.border * style.scale
    lw, lh = _logo_geometry(modules_px, logo, style.ratio)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    pad = max(int(max(lw, lh) * 0.10), 4)
    bw, bh = lw + 2 * pad, lh + 2 * pad
    color = _rgb(_mark_color(style)) if light else _rgb(style.bg)
    back = _backing(bw, bh, color, circle=light)
    cx, cy = img.width // 2, img.height // 2
    img.alpha_composite(back, (cx - bw // 2, cy - bh // 2))
    img.alpha_composite(logo, (cx - lw // 2, cy - lh // 2))
    return img


# ---------- render ----------

def _make(data: str, style: QRStyle) -> segno.QRCode:
    return segno.make(data, error=style.effective_error, micro=False)


def render_png(data: str, style: QRStyle) -> Image.Image:
    qr = _make(data, style)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=style.scale, border=style.border, dark=style.fg, light=style.bg)
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")
    if style.logo:
        img = _overlay_logo(img, style)
    return img.convert("RGB")


def render_svg(data: str, style: QRStyle) -> str:
    qr = _make(data, style)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=style.scale, border=style.border,
            dark=style.fg, light=style.bg, xmldecl=False, svgns=True)
    svg = buf.getvalue().decode("utf-8")
    if not style.logo:
        return svg

    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if m:
        vw = float(m.group(1))
    else:
        vw = float(re.search(r'width="([\d.]+)"', svg).group(1))
    modules = qr.symbol_size(border=0)[0]
    unit = vw / (modules + 2 * style.border)          # tamaño de un módulo en unidades del SVG
    logo = load_logo(style.logo)
    light = _is_light_mark(logo)
    lw, lh = _logo_geometry(modules * unit, logo, style.ratio)
    pad = max(max(lw, lh) * 0.10, 4 * unit / style.scale)
    cx = cy = vw / 2

    small = logo.copy()
    small.thumbnail((600, 600), Image.LANCZOS)
    b = io.BytesIO()
    small.save(b, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()

    if light:
        r = max(lw, lh) / 2 + pad
        back = f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="{_mark_color(style)}"/>'
    else:
        bw, bh = lw + 2 * pad, lh + 2 * pad
        back = (f'<rect x="{cx - bw / 2:.3f}" y="{cy - bh / 2:.3f}" width="{bw:.3f}" height="{bh:.3f}" '
                f'rx="{min(bw, bh) * 0.22:.3f}" fill="{style.bg}"/>')
    image = (f'<image x="{cx - lw / 2:.3f}" y="{cy - lh / 2:.3f}" width="{lw:.3f}" height="{lh:.3f}" '
             f'xlink:href="{uri}"/>')
    svg = svg.replace("<svg ", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ', 1)
    return svg.replace("</svg>", back + image + "</svg>")


def save_qr(data: str, base: Path, fmts: list[str], style: QRStyle,
            png_img: Image.Image | None = None) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for f in fmts:
        path = Path(f"{base}.{f}")
        if f == "png":
            (png_img or render_png(data, style)).save(path, dpi=(300, 300))
        elif f == "svg":
            path.write_text(render_svg(data, style), encoding="utf-8")
        elif f == "pdf":
            if style.logo:
                (png_img or render_png(data, style)).save(path, "PDF", resolution=300)
            else:
                _make(data, style).save(str(path), kind="pdf", scale=style.scale,
                                        border=style.border, dark=style.fg, light=style.bg)
        else:
            raise ValueError(f"Formato desconocido: {f}")
        written.append(path)
    return written


def verify(img: Image.Image, expected: str) -> bool:
    """Lee de vuelta el QR recién creado y confirma que dice lo mismo."""
    return any(text == expected for text, _ in read_pil(img))


# ---------- nombres y líneas ----------

_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_BARE_DOMAIN = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?#]\S*)?$", re.I)
_FILE_EXT = {"pdf", "png", "jpg", "jpeg", "txt", "doc", "docx", "xls", "xlsx", "csv", "zip", "mp3", "mp4"}


def safe_filename(text: str, maxlen: int = 80) -> str:
    t = unicodedata.normalize("NFC", text).strip()
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", t)
    t = re.sub(r"[\s_]+", "_", t).strip("._ ")
    t = t[:maxlen].rstrip("._ ")
    if not t:
        t = "qr"
    if t.upper() in _RESERVED:
        t = "_" + t
    return t


def name_from_data(data: str) -> str:
    d = data.strip()
    if re.match(r"^https?://", d, re.I):
        u = urlparse(d)
        host = (u.netloc or "").removeprefix("www.")
        path = u.path.strip("/").replace("/", "-")
        return safe_filename(host + ("_" + path if path else ""))
    if d.upper().startswith("WIFI:"):
        return "wifi"
    return safe_filename(d[:40])


def normalize_data(s: str, add_https: bool = True) -> str:
    s = s.strip()
    if add_https and "@" not in s and _BARE_DOMAIN.match(s):
        if s.rsplit(".", 1)[-1].split("/")[0].lower() not in _FILE_EXT:
            return "https://" + s
    return s


@dataclass
class Item:
    name: str | None
    data: str


def parse_lines(text: str, add_https: bool = True) -> list[Item]:
    """Una línea por QR. Para ponerle nombre al archivo: `Nombre | link` o `Nombre<TAB>link`."""
    items: list[Item] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = None
        if "\t" in line:
            left, right = line.split("\t", 1)
            name, line = left.strip() or None, right.strip()
        elif "|" in line and not re.match(r"^https?://", line, re.I):
            left, right = line.split("|", 1)
            if right.strip():
                name, line = left.strip() or None, right.strip()
        if line:
            items.append(Item(name, normalize_data(line, add_https)))
    return items


# ---------- lotes ----------

@dataclass
class BatchRow:
    name: str
    data: str
    status: str          # ok | aviso | error | omitido
    note: str = ""
    files: list[Path] = field(default_factory=list)


def generate_batch(
    items: list[Item],
    out_dir: str | Path,
    fmts: list[str],
    style: QRStyle,
    verify_each: bool = True,
    skip_dupes: bool = True,
    overwrite: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> list[BatchRow]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    seen: set[str] = set()
    rows: list[BatchRow] = []
    n = len(items)

    for i, it in enumerate(items):
        base_name = safe_filename(it.name) if it.name else name_from_data(it.data)
        if skip_dupes and it.data in seen:
            rows.append(BatchRow(base_name, it.data, "omitido", "Link repetido en la lista"))
            if progress:
                progress(i + 1, n)
            continue
        seen.add(it.data)

        cand, k = base_name, 2
        while cand.lower() in used or (not overwrite and any(Path(f"{out / cand}.{f}").exists() for f in fmts)):
            cand = f"{base_name}-{k}"
            k += 1
        used.add(cand.lower())

        try:
            img = render_png(it.data, style)
            files = save_qr(it.data, out / cand, fmts, style, png_img=img)
            if verify_each and not verify(img, it.data):
                rows.append(BatchRow(cand, it.data, "aviso", "Se creó, pero no se pudo leer de vuelta. Revisa colores y logo.", files))
            else:
                rows.append(BatchRow(cand, it.data, "ok", "", files))
        except segno.DataOverflowError:
            rows.append(BatchRow(cand, it.data, "error", "Texto demasiado largo para este nivel de corrección"))
        except Exception as exc:
            rows.append(BatchRow(cand, it.data, "error", str(exc)))
        if progress:
            progress(i + 1, n)
    return rows
