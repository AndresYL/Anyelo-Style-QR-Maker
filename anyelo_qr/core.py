"""Generación de QR (PNG, SVG, PDF) con formas, ojos y logo propios; lotes, verificación y UTM."""
from __future__ import annotations

import base64
import io
import re
import unicodedata
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlsplit, urlunsplit

import segno
from PIL import Image, ImageDraw

from .reader import read_pil

FORMATS = ("png", "svg", "pdf")
ERROR_LEVELS = {"l": "Baja (7%)", "m": "Media (15%)", "q": "Alta (25%)", "h": "Máxima (30%)"}
SHAPES = {"square": "Cuadrados", "rounded": "Redondeados", "dots": "Puntos",
          "vbars": "Barras verticales", "hbars": "Barras horizontales"}
EYE_SHAPES = {"square": "Cuadrados", "rounded": "Redondeados", "circle": "Círculos"}
MIN_PX, MAX_PX = 100, 4000
MAX_LOGO_RATIO = 0.30
PDF_MIN_PX = 1200


@dataclass(frozen=True)
class QRStyle:
    fg: str = "#000000"
    bg: str = "#FFFFFF"
    size: int = 1000            # lado final en píxeles (el QR es cuadrado)
    border: int = 4             # zona de silencio, en módulos
    error: str = "m"
    shape: str = "square"
    eye_shape: str = "square"
    eye_color: str | None = None
    logo: str | None = None
    logo_ratio: float = 0.22    # ancho del logo / ancho de los módulos
    logo_border: bool = True

    @property
    def effective_error(self) -> str:
        return "h" if self.logo else self.error

    @property
    def ratio(self) -> float:
        return min(max(self.logo_ratio, 0.10), MAX_LOGO_RATIO)

    @property
    def px(self) -> int:
        return min(max(int(self.size), MIN_PX), MAX_PX)


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


def style_warnings(style: QRStyle, data: str | None = None) -> list[str]:
    out = []
    if contrast_ratio(style.fg, style.bg) < 3:
        out.append("Poco contraste entre el código y el fondo: muchos lectores no van a poder leerlo.")
    if style.eye_color and contrast_ratio(style.eye_color, style.bg) < 3:
        out.append("Poco contraste en el color de los ojos.")
    if style.logo and style.logo_ratio > 0.26:
        out.append("El logo es grande y tapa mucho código. Bájalo a 22% o menos si el QR se va a imprimir pequeño.")
    if data:
        try:
            n = _make(data, style).symbol_size(border=0)[0]
            if style.px / (n + 2 * style.border) < 3:
                out.append("Cada cuadrito queda de menos de 3 píxeles. Sube el tamaño del QR.")
        except Exception:
            pass
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


def _mark_color(style: QRStyle) -> str:
    """Color detrás de un logo blanco: el más oscuro de los dos, para que las letras se lean."""
    c = style.fg if _luminance(_rgb(style.fg)) <= _luminance(_rgb(style.bg)) else style.bg
    return c if _luminance(_rgb(c)) < 0.4 else "#000000"


def _logo_dims(modules_len: float, logo: Image.Image, ratio: float) -> tuple[float, float]:
    d = modules_len * ratio
    lw, lh = logo.size
    s = d / max(lw, lh)
    return lw * s, lh * s


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


def _overlay_logo(img: Image.Image, style: QRStyle, modules_px: float) -> Image.Image:
    logo = load_logo(style.logo)
    light = _is_light_mark(logo)
    lw, lh = (max(int(v), 1) for v in _logo_dims(modules_px, logo, style.ratio))
    logo = logo.resize((lw, lh), Image.LANCZOS)
    base = img.convert("RGBA")
    cx = cy = base.width // 2
    big = max(lw, lh)
    if light:
        if style.logo_border:
            bw = bh = big + 2 * max(int(big * 0.10), 2)
        else:   # disco apenas más chico que el logo: sin anillo visible
            bw = bh = big - 2 * max(int(big * 0.012), 1)
        base.alpha_composite(_backing(bw, bw, _rgb(_mark_color(style)), True), (cx - bw // 2, cy - bh // 2))
    elif style.logo_border:
        pad = max(int(big * 0.10), 2)
        bw, bh = lw + 2 * pad, lh + 2 * pad
        base.alpha_composite(_backing(bw, bh, _rgb(style.bg), False), (cx - bw // 2, cy - bh // 2))
    base.alpha_composite(logo, (cx - lw // 2, cy - lh // 2))
    return base.convert("RGB")


# ---------- dibujo del QR ----------

def _make(data: str, style: QRStyle) -> segno.QRCode:
    return segno.make(data, error=style.effective_error, micro=False)


def _eye_origins(n: int):
    return ((0, 0), (n - 7, 0), (0, n - 7))


def _dark_cells(matrix, n: int) -> list[list[bool]]:
    skip = {(ex + dx, ey + dy) for ex, ey in _eye_origins(n) for dx in range(7) for dy in range(7)}
    return [[bool(matrix[y][x]) and (x, y) not in skip for x in range(n)] for y in range(n)]


def _runs(cells, n: int, vertical: bool):
    out = []
    for a in range(n):
        b = 0
        while b < n:
            on = cells[b][a] if vertical else cells[a][b]
            if on:
                s = b
                while b < n and (cells[b][a] if vertical else cells[a][b]):
                    b += 1
                out.append((a, s, 1, b - s) if vertical else (s, a, b - s, 1))
            else:
                b += 1
    return out


@lru_cache(maxsize=256)
def _sprite(kind: str, wc: int, hc: int, scale: int) -> Image.Image:
    k = 4
    cell = scale * k
    W, H = wc * cell, hc * cell
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    if kind == "rounded":
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(cell * 0.35), fill=255)
    elif kind == "dots":
        i = int(cell * 0.05)
        d.ellipse((i, i, W - 1 - i, H - 1 - i), fill=255)
    elif kind == "vbars":
        i = int(cell * 0.09)
        d.rounded_rectangle((i, 0, W - 1 - i, H - 1), radius=(W - 2 * i) // 2, fill=255)
    elif kind == "hbars":
        i = int(cell * 0.09)
        d.rounded_rectangle((0, i, W - 1, H - 1 - i), radius=(H - 2 * i) // 2, fill=255)
    else:
        d.rectangle((0, 0, W - 1, H - 1), fill=255)
    return m.resize((wc * scale, hc * scale), Image.LANCZOS)


def _paint_modules(img, cells, n, scale, off, color, shape):
    if shape == "square":
        d = ImageDraw.Draw(img)
        for y in range(n):
            x = 0
            while x < n:
                if cells[y][x]:
                    s = x
                    while x < n and cells[y][x]:
                        x += 1
                    d.rectangle((off + s * scale, off + y * scale, off + x * scale - 1, off + (y + 1) * scale - 1), fill=color)
                else:
                    x += 1
    elif shape in ("vbars", "hbars"):
        for cx, cy, w, h in _runs(cells, n, shape == "vbars"):
            x0, y0 = off + cx * scale, off + cy * scale
            img.paste(color, (x0, y0, x0 + w * scale, y0 + h * scale), _sprite(shape, w, h, scale))
    else:
        sp = _sprite(shape, 1, 1, scale)
        for y in range(n):
            for x in range(n):
                if cells[y][x]:
                    x0, y0 = off + x * scale, off + y * scale
                    img.paste(color, (x0, y0, x0 + scale, y0 + scale), sp)


_EYE_RADII = (2.0, 1.2, 0.9)   # esquinas del cuadro exterior, del hueco y del centro (en módulos)


def _paint_eye(img, x0, y0, scale, shape, color):
    k = 4
    size = 7 * scale
    cell = scale * k
    S = size * k
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)

    def shp(a, b, fill, r):
        box = (a * cell, a * cell, b * cell - 1, b * cell - 1)
        if shape == "circle":
            d.ellipse(box, fill=fill)
        elif shape == "rounded":
            d.rounded_rectangle(box, radius=int(r * cell), fill=fill)
        else:
            d.rectangle(box, fill=fill)

    shp(0, 7, 255, _EYE_RADII[0])
    shp(1, 6, 0, _EYE_RADII[1])
    shp(2, 5, 255, _EYE_RADII[2])
    m = m.resize((size, size), Image.LANCZOS)
    img.paste(color, (x0, y0, x0 + size, y0 + size), m)


def render_png(data: str, style: QRStyle) -> Image.Image:
    qr = _make(data, style)
    matrix = [list(r) for r in qr.matrix]
    n = len(matrix)
    total = n + 2 * style.border
    px = style.px
    scale = max(1, px // total)
    inner = total * scale
    bg, fg = _rgb(style.bg), _rgb(style.fg)
    eye = _rgb(style.eye_color or style.fg)
    off = style.border * scale

    img = Image.new("RGB", (inner, inner), bg)
    _paint_modules(img, _dark_cells(matrix, n), n, scale, off, fg, style.shape)
    for ex, ey in _eye_origins(n):
        _paint_eye(img, off + ex * scale, off + ey * scale, scale, style.eye_shape, eye)
    if style.logo:
        img = _overlay_logo(img, style, n * scale)
    if px > inner:          # el sobrante se reparte como margen extra, así los cuadritos quedan nítidos
        canvas = Image.new("RGB", (px, px), bg)
        canvas.paste(img, ((px - inner) // 2, (px - inner) // 2))
        img = canvas
    elif px < inner:
        img = img.resize((px, px), Image.LANCZOS)
    return img


def _f(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _svg_eye(x, y, shape, color, bg) -> str:
    if shape == "circle":
        c = x + 3.5
        return (f'<circle cx="{_f(c)}" cy="{_f(y + 3.5)}" r="3.5" fill="{color}"/>'
                f'<circle cx="{_f(c)}" cy="{_f(y + 3.5)}" r="2.5" fill="{bg}"/>'
                f'<circle cx="{_f(c)}" cy="{_f(y + 3.5)}" r="1.5" fill="{color}"/>')
    r = _EYE_RADII if shape == "rounded" else (0, 0, 0)
    return (f'<rect x="{x}" y="{y}" width="7" height="7" rx="{r[0]}" fill="{color}"/>'
            f'<rect x="{x + 1}" y="{y + 1}" width="5" height="5" rx="{r[1]}" fill="{bg}"/>'
            f'<rect x="{x + 2}" y="{y + 2}" width="3" height="3" rx="{r[2]}" fill="{color}"/>')


def render_svg(data: str, style: QRStyle) -> str:
    qr = _make(data, style)
    matrix = [list(r) for r in qr.matrix]
    n = len(matrix)
    b = style.border
    total = n + 2 * b
    px = style.px
    cells = _dark_cells(matrix, n)
    fg, bg = style.fg, style.bg
    eye = style.eye_color or style.fg

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="{px}" height="{px}" viewBox="0 0 {total} {total}">',
           f'<rect width="{total}" height="{total}" fill="{bg}"/>']
    if style.shape == "square":
        d = []
        for y in range(n):
            x = 0
            while x < n:
                if cells[y][x]:
                    s = x
                    while x < n and cells[y][x]:
                        x += 1
                    d.append(f"M{b + s} {b + y}h{x - s}v1h-{x - s}z")
                else:
                    x += 1
        out.append(f'<path d="{"".join(d)}" fill="{fg}" shape-rendering="crispEdges"/>')
    else:
        out.append(f'<g fill="{fg}">')
        if style.shape in ("vbars", "hbars"):
            for cx, cy, w, h in _runs(cells, n, style.shape == "vbars"):
                if style.shape == "vbars":
                    out.append(f'<rect x="{_f(b + cx + 0.09)}" y="{b + cy}" width="0.82" height="{h}" rx="0.41"/>')
                else:
                    out.append(f'<rect x="{b + cx}" y="{_f(b + cy + 0.09)}" width="{w}" height="0.82" rx="0.41"/>')
        else:
            for y in range(n):
                for x in range(n):
                    if cells[y][x]:
                        if style.shape == "dots":
                            out.append(f'<circle cx="{b + x + 0.5}" cy="{b + y + 0.5}" r="0.45"/>')
                        else:
                            out.append(f'<rect x="{b + x}" y="{b + y}" width="1" height="1" rx="0.35"/>')
        out.append("</g>")
    for ex, ey in _eye_origins(n):
        out.append(_svg_eye(b + ex, b + ey, style.eye_shape, eye, bg))

    if style.logo:
        logo = load_logo(style.logo)
        light = _is_light_mark(logo)
        lw, lh = _logo_dims(n, logo, style.ratio)
        big = max(lw, lh)
        cx = cy = total / 2
        if light:
            r = big / 2 + (big * 0.10 if style.logo_border else -big * 0.012)
            out.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{_mark_color(style)}"/>')
        elif style.logo_border:
            pad = big * 0.10
            bw, bh = lw + 2 * pad, lh + 2 * pad
            out.append(f'<rect x="{_f(cx - bw / 2)}" y="{_f(cy - bh / 2)}" width="{_f(bw)}" height="{_f(bh)}" '
                       f'rx="{_f(min(bw, bh) * 0.22)}" fill="{bg}"/>')
        small = logo.copy()
        small.thumbnail((600, 600), Image.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, "PNG")
        uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        out.append(f'<image x="{_f(cx - lw / 2)}" y="{_f(cy - lh / 2)}" width="{_f(lw)}" height="{_f(lh)}" xlink:href="{uri}"/>')
    out.append("</svg>")
    return "".join(out)


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
            if png_img is not None and png_img.width >= PDF_MIN_PX:
                img = png_img
            else:
                img = render_png(data, replace(style, size=max(style.px, PDF_MIN_PX)))
            img.save(path, "PDF", resolution=300)
        else:
            raise ValueError(f"Formato desconocido: {f}")
        written.append(path)
    return written


def verify(img: Image.Image, expected: str) -> bool:
    """Lee de vuelta el QR recién creado y confirma que dice lo mismo."""
    return any(text == expected for text, _ in read_pil(img))


# ---------- nombres, líneas y UTM ----------

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


def build_utm(base: str, source: str, medium: str = "", campaign: str = "",
              term: str = "", content: str = "", lower: bool = True) -> str:
    """Arma un link con parámetros UTM, conservando los parámetros que ya tuviera."""
    base = normalize_data(base, True)
    if not re.match(r"^https?://\S+$", base, re.I):
        raise ValueError("Escribe el link base, por ejemplo anyelostyle.com/promo")
    if not source.strip():
        raise ValueError("Falta la fuente (de dónde viene la gente: instagram, tiktok…)")
    u = urlsplit(base)
    keep = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith("utm_")]

    def clean(v: str) -> str:
        v = unicodedata.normalize("NFKD", v.strip())
        v = "".join(ch for ch in v if not unicodedata.combining(ch))   # otoño -> otono
        v = re.sub(r"\s+", "-", v)
        return v.lower() if lower else v

    for key, val in (("utm_source", source), ("utm_medium", medium), ("utm_campaign", campaign),
                     ("utm_term", term), ("utm_content", content)):
        if val.strip():
            keep.append((key, clean(val)))
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(keep, quote_via=quote), u.fragment))


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
                rows.append(BatchRow(cand, it.data, "aviso", "Se creó, pero no se pudo leer de vuelta. Revisa colores, forma y logo.", files))
            else:
                rows.append(BatchRow(cand, it.data, "ok", "", files))
        except segno.DataOverflowError:
            rows.append(BatchRow(cand, it.data, "error", "Texto demasiado largo para este nivel de corrección"))
        except Exception as exc:
            rows.append(BatchRow(cand, it.data, "error", str(exc)))
        if progress:
            progress(i + 1, n)
    return rows
