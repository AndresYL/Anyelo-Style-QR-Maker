"""Arma la página de descarga lista para publicar: un solo HTML con las imágenes adentro.
Uso, desde la raíz del proyecto:   python web/build_page.py
Lee la versión de anyelo_qr/brand.py y las novedades de CHANGELOG.md (para los datos de respaldo)."""
from __future__ import annotations

import base64
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = "AndresYL/Anyelo-Style-QR-Maker"   # usuario/repositorio de GitHub: es el único lugar donde se escribe
OUT = HERE / "dist"


def parse_changelog(md: str):
    out, cur = [], None
    for line in md.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\s*[-\u2013\u2014]?\s*(.*)$", line)
        if m:
            cur = {"version": m.group(1), "fecha": m.group(2).rstrip(), "items": []}
            out.append(cur)
            continue
        b = re.match(r"^\s*[-*]\s+(.*\S)\s*$", line)
        if b and cur:
            cur["items"].append(b.group(1))
    return out


def build_html() -> tuple[str, str]:
    """Devuelve (html, versión). Lanza AssertionError si algo no cumple las reglas del tema."""
    version = re.search(r'VERSION\s*=\s*"([^"]+)"', (ROOT / "anyelo_qr" / "brand.py").read_text(encoding="utf-8")).group(1)
    changelog = parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    top = next((c for c in changelog if c["version"] == version), None)
    assert top, f"CHANGELOG.md no tiene una sección '## {version} — fecha' para la versión {version}."

    html = (HERE / "pagina-descarga.template.html").read_text(encoding="utf-8")

    # logo pequeño para el QR de la demo (PNG de 96 px, dentro del propio HTML)
    from PIL import Image
    import io
    logo = Image.open(ROOT / "anyelo_qr" / "assets" / "logo.png").convert("RGBA").resize((96, 96), Image.LANCZOS)
    buf = io.BytesIO()
    logo.save(buf, "PNG", optimize=True)
    logo_data = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    qrlib = (HERE / "vendor" / "qrcode.min.js").read_text(encoding="utf-8")
    cambios = json.dumps(changelog, ensure_ascii=False).replace("</", "<\\/")
    html = (html.replace("{{QRLIB}}", qrlib).replace("{{CAMBIOS_JSON}}", cambios).replace("{{LOGO_DATA}}", logo_data)
            .replace("{{REPO}}", REPO).replace("{{VERSION}}", version).replace("{{FECHA}}", top["fecha"]))

    # comprobaciones de las reglas del tema para herramientas
    assert "{{" not in html, "quedó un marcador sin reemplazar"
    assert "`" not in html, "hay comillas invertidas: WordPress las rompe"
    assert "${" not in html, "hay plantillas de texto: WordPress las rompe"

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.errors = [], []
            self.void = {"meta", "link", "img", "br", "base", "input", "hr"}

        def handle_starttag(self, tag, attrs):
            if tag not in self.void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.void:
                return
            if not self.stack or self.stack[-1] != tag:
                self.errors.append(f"cierre inesperado </{tag}> (abierto: {self.stack[-3:]})")
                if tag in self.stack:
                    while self.stack and self.stack[-1] != tag:
                        self.stack.pop()
                    self.stack.pop()
            else:
                self.stack.pop()
    p = P()
    p.feed(html)
    assert not p.errors and not p.stack, (p.errors, p.stack)

    return html, version


def main() -> int:
    try:
        html, version = build_html()
    except AssertionError as exc:
        print("ERROR:", exc)
        return 1
    OUT.mkdir(exist_ok=True)
    out = OUT / "descarga-anyelo-style-qr.html"
    out.write_text(html, encoding="utf-8")
    print(f"listo: {out}  ({round(out.stat().st_size / 1024)} KB, versión {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
