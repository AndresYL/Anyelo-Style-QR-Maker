import csv
from pathlib import Path

import pytest
from openpyxl import Workbook

from anyelo_qr.core import (QRStyle, generate_batch, name_from_data, normalize_data, parse_lines,
                            render_png, render_svg, safe_filename, save_qr, style_warnings, verify)
from anyelo_qr.paths import DEFAULT_LOGO
from anyelo_qr.reader import analyze_link, read_paths
from anyelo_qr.tabular import guess_columns, items_from_table, read_table, sheet_names

URL = "https://anyelostyle.com/promo?utm_source=ig&utm_campaign=otoño"


@pytest.mark.parametrize("logo", [None, str(DEFAULT_LOGO)])
def test_png_roundtrip(logo):
    st = QRStyle(logo=logo)
    assert verify(render_png(URL, st), URL)


def test_colors_roundtrip():
    st = QRStyle(fg="#1B2A6B", bg="#F5E9D3", logo=str(DEFAULT_LOGO))
    assert verify(render_png(URL, st), URL)


def test_inverted_roundtrip():
    st = QRStyle(fg="#FFFFFF", bg="#000000")
    assert verify(render_png(URL, st), URL)


def test_svg_with_logo_is_valid_xml():
    import xml.dom.minidom as md
    svg = render_svg(URL, QRStyle(logo=str(DEFAULT_LOGO)))
    md.parseString(svg)
    assert "<image" in svg and "<circle" in svg


def test_save_all_formats_and_read_back(tmp_path):
    for logo in (None, str(DEFAULT_LOGO)):
        st = QRStyle(logo=logo)
        files = save_qr(URL, tmp_path / f"t{bool(logo)}", ["png", "svg", "pdf"], st)
        assert all(f.exists() and f.stat().st_size > 0 for f in files)
        found, errs = read_paths([files[0], files[2]])
        assert not errs
        assert {f.text for f in found} == {URL}


def test_parse_lines():
    items = parse_lines("# comentario\n\nanyelostyle.com/x\nPromo | https://a.com/b\nOtra\thttps://c.com\ninforme.pdf\nhttps://x.com/?a=1|2")
    assert [(i.name, i.data) for i in items] == [
        (None, "https://anyelostyle.com/x"),
        ("Promo", "https://a.com/b"),
        ("Otra", "https://c.com"),
        (None, "informe.pdf"),
        (None, "https://x.com/?a=1|2"),
    ]


def test_filenames():
    assert safe_filename('a/b:c*?"d') == "a_b_c_d"
    assert safe_filename("CON") == "_CON"
    assert safe_filename("   ") == "qr"
    assert name_from_data("https://www.anyelostyle.com/promo/otoño") == "anyelostyle.com_promo-otoño"


def test_batch(tmp_path):
    items = parse_lines("Uno | https://a.com\nUno | https://b.com\nhttps://a.com\nDos | https://d.com")
    rows = generate_batch(items, tmp_path, ["png"], QRStyle(logo=str(DEFAULT_LOGO)))
    assert [r.status for r in rows] == ["ok", "ok", "omitido", "ok"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Dos.png", "Uno-2.png", "Uno.png"]
    # segunda corrida no pisa nada
    rows = generate_batch(items[:1], tmp_path, ["png"], QRStyle())
    assert (tmp_path / "Uno-3.png").exists()


def test_batch_too_long(tmp_path):
    rows = generate_batch(parse_lines("x" * 5000), tmp_path, ["png"], QRStyle())
    assert rows[0].status == "error"


def test_tables(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre", "Link"])
    ws.append(["Uno", "https://a.com"])
    ws.append(["Dos", "b.com/x"])
    ws.append([None, None])
    p = tmp_path / "t.xlsx"
    wb.save(p)
    assert sheet_names(p) == [ws.title]
    h, rows = read_table(p)
    assert h == ["Nombre", "Link"] and len(rows) == 2
    n, d = guess_columns(h, rows)
    assert (n, d) == (0, 1)
    assert [(i.name, i.data) for i in items_from_table(rows, n, d)] == [("Uno", "https://a.com"), ("Dos", "https://b.com/x")]

    c = tmp_path / "t.csv"
    c.write_text("titulo;url\nÑandú;https://ñ.com\n", encoding="cp1252", errors="replace")
    h, rows = read_table(c)
    assert h == ["titulo", "url"] and rows[0][0] == "Ñandú"


def test_link_warnings():
    assert analyze_link("https://bit.ly/abc")
    assert analyze_link("http://192.168.1.1/x")
    assert analyze_link("https://google.com@evil.com")
    assert not analyze_link("https://anyelostyle.com/x")
    assert not analyze_link("texto suelto")


def test_style_warnings():
    assert style_warnings(QRStyle(fg="#888888", bg="#999999"))
    assert style_warnings(QRStyle(logo=str(DEFAULT_LOGO), logo_ratio=0.3))
    assert not style_warnings(QRStyle())
