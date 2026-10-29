"""La página de descarga se arma bien y no se puede publicar una versión sin sus novedades."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("build_page", ROOT / "web" / "build_page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_page_builds_with_current_version():
    mod = _load()
    html, version = mod.build_html()
    assert version in html
    assert "AnyeloStyleQR-Setup.exe" in html and "releases/latest/download" in html
    assert "`" not in html and "${" not in html           # WordPress rompe las plantillas de texto
    assert "../assets/tools.css" in html                  # la tipografía del sitio, igual que las otras herramientas
    assert "qrcode-generator" in html and "MIT License" in html     # la librería de la demo, con su licencia
    assert "data:image/webp" not in html                  # las capturas salen del repositorio, no pesan en la página
    assert len(html.encode("utf-8")) < 150_000            # cabe pegada en el campo "Código de la herramienta"
    assert "{{" not in html


def test_screenshots_the_page_asks_for_exist():
    html = (ROOT / "web" / "pagina-descarga.template.html").read_text(encoding="utf-8")
    import re
    for name in set(re.findall(r'data-shot="([\w-]+)"', html)):
        assert (ROOT / "web" / "shots" / f"{name}.webp").exists(), name


def test_changelog_has_a_section_for_every_version_line():
    mod = _load()
    entries = mod.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert entries and all(e["items"] for e in entries)
    versions = [e["version"] for e in entries]
    assert versions == sorted(versions, key=lambda v: tuple(map(int, v.split("."))), reverse=True)   # la más nueva, arriba


def test_page_script_parser_matches_python_parser():
    """El JavaScript de la página lee CHANGELOG.md con la misma regla que Python."""
    html = (ROOT / "web" / "pagina-descarga.template.html").read_text(encoding="utf-8")
    assert r"/^##\s+v?(\d+\.\d+\.\d+)\s*[-\u2013\u2014]?\s*(.*)$/" in html
    assert r"/^\s*[-*]\s+(.*\S)\s*$/" in html


def test_version_hooks_do_not_collide_with_demo_buttons():
    """Los botones de la demo usan data-v; el número de versión usa data-vnum (antes se pisaban)."""
    html = (ROOT / "web" / "pagina-descarga.template.html").read_text(encoding="utf-8")
    assert "setAll('[data-vnum]'" in html and "setAll('[data-v]'" not in html


def test_missing_changelog_section_stops_the_build(tmp_path, monkeypatch):
    mod = _load()
    (tmp_path / "anyelo_qr").mkdir()
    (tmp_path / "anyelo_qr" / "brand.py").write_text('VERSION = "9.9.9"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## 0.1.0 — 1 de enero de 2026\n- algo\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    try:
        mod.build_html()
    except AssertionError as exc:
        assert "9.9.9" in str(exc)
    else:
        raise AssertionError("debió fallar: la versión 9.9.9 no está en el CHANGELOG")
