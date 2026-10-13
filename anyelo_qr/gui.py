"""Ventana principal (PySide6)."""
from __future__ import annotations

import csv
import re
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QScrollArea, QSlider, QSpinBox, QSplashScreen,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import brand, winfx
from .core import (ERROR_LEVELS, EYE_SHAPES, MAX_PX, MIN_PX, SHAPES, Item, QRStyle, build_utm, generate_batch,
                   normalize_data, parse_lines, render_png, safe_filename, style_warnings, verify)
from .fonts import font, load_fonts
from .hotkey import FACTORY_HOTKEY, GlobalHotkey, altgr_conflict, default_hotkey
from .paths import DEFAULT_LOGO, asset
from .reader import is_url, read_paths
from .scanner import Scanner
from .settings import Settings
from .tabular import guess_columns, items_from_table, read_table, sheet_names
from .theme import build_qss
from .widgets import (ColorButton, CtaButton, CreamCard, DestinationCard, DropZone, HotkeyRecorder, Job, LinkButton,
                      NavButton, Pages, Pill, ResultsTable, StepCard, Toast, eyebrow, h2, headline, muted, open_folder,
                      pil_to_pixmap, pil_to_qimage, scrolled, section, style_table)


# ---------- panel de estilo (derecha) ----------

class StylePanel(QFrame):
    changed = Signal()
    copy_requested = Signal()

    def __init__(self, s: Settings):
        super().__init__()
        self.setObjectName("panelSide")
        self.s = s
        self.sample = "https://anyelostyle.com"
        self.sample_real = False
        self.setFixedWidth(334)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 22)
        v.setSpacing(9)

        v.addWidget(eyebrow("Vista previa"))
        card = CreamCard()
        self.preview = QLabel(alignment=Qt.AlignCenter)
        self.preview.setFixedSize(236, 236)
        card.lay.addWidget(self.preview)
        v.addWidget(card)
        v.addSpacing(6)
        st = QHBoxLayout()
        st.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.badge = QLabel()
        self.badge.setFont(font("semibold", 12, 1.0))
        st.addWidget(self.dot)
        st.addWidget(self.badge, 1)
        v.addLayout(st)
        self.warn = QLabel()
        self.warn.setFont(font("regular", 12))
        self.warn.setStyleSheet(f"color:{brand.RED_L};")
        self.warn.setWordWrap(True)
        v.addWidget(self.warn)
        cp = Pill("Copiar este QR")
        cp.clicked.connect(self.copy_requested.emit)
        v.addWidget(cp)

        v.addWidget(section("Colores"))
        row = QHBoxLayout()
        self.fg = ColorButton(s.fg, "Color del código", lambda c: self._preview_with(fg=c))
        self.bg = ColorButton(s.bg, "Color del fondo", lambda c: self._preview_with(bg=c))
        row.addWidget(QLabel("Código"))
        row.addWidget(self.fg)
        row.addSpacing(14)
        row.addWidget(QLabel("Fondo"))
        row.addWidget(self.bg)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(section("Forma"))
        self.shape = QComboBox()
        for k, label in SHAPES.items():
            self.shape.addItem("Cuadritos: " + label.lower(), k)
        self.shape.setCurrentIndex(max(0, self.shape.findData(s.shape)))
        self.eye = QComboBox()
        for k, label in EYE_SHAPES.items():
            self.eye.addItem("Ojos: " + label.lower(), k)
        self.eye.setCurrentIndex(max(0, self.eye.findData(s.eye_shape)))
        v.addWidget(self.shape)
        v.addWidget(self.eye)
        er = QHBoxLayout()
        self.eye_on = QCheckBox("Color propio en los ojos")
        self.eye_on.setChecked(s.eye_color_on)
        self.eye_btn = ColorButton(s.eye_color, "Color de los ojos", lambda c: self._preview_with(eye_color=c))
        er.addWidget(self.eye_on, 1)
        er.addWidget(self.eye_btn)
        v.addLayout(er)

        v.addWidget(section("Logo en el centro"))
        self.logo = QComboBox()
        self.logo.addItems(["Sin logo", "Anyelo Style", "Otro logo…"])
        self.logo.setCurrentIndex({"none": 0, "default": 1, "custom": 2}[s.logo_mode])
        v.addWidget(self.logo)
        self.logo_path = muted(Path(s.logo_custom).name if s.logo_custom else "", 12)
        v.addWidget(self.logo_path)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Tamaño"))
        self.ratio = QSlider(Qt.Horizontal)
        self.ratio.setRange(10, 30)
        self.ratio.setValue(int(s.logo_ratio * 100))
        r2.addWidget(self.ratio, 1)
        v.addLayout(r2)
        self.logo_border = QCheckBox("Con borde")
        self.logo_border.setChecked(s.logo_border)
        v.addWidget(self.logo_border)

        v.addWidget(section("Tamaño y calidad"))
        r3 = QHBoxLayout()
        self.px = QSpinBox()
        self.px.setRange(MIN_PX, MAX_PX)
        self.px.setSuffix(" px")
        self.px.setValue(s.qr_px)
        self.px.setKeyboardTracking(False)
        r3.addWidget(QLabel("Lado"))
        r3.addWidget(self.px, 1)
        v.addLayout(r3)
        self.err = QComboBox()
        for k, label in ERROR_LEVELS.items():
            self.err.addItem("Corrección: " + label, k)
        self.err.setCurrentIndex(max(0, self.err.findData(s.error)))
        v.addWidget(self.err)
        v.addWidget(muted("El QR siempre es cuadrado. Con logo, la corrección sube sola a Máxima.", 12))
        v.addStretch()

        for w in (self.fg, self.bg, self.eye_btn):
            w.changed.connect(self._on_change)
            w.live.connect(lambda _c: self.refresh())
        self.logo.currentIndexChanged.connect(self._on_logo)
        self.ratio.valueChanged.connect(self._on_change)
        for w in (self.shape, self.eye, self.err):
            w.currentIndexChanged.connect(self._on_change)
        self.px.valueChanged.connect(self._on_change)
        for cb in (self.eye_on, self.logo_border):
            cb.toggled.connect(self._on_change)
        self.refresh()

    # --- estado ---
    def logo_file(self) -> str | None:
        i = self.logo.currentIndex()
        if i == 1:
            return str(DEFAULT_LOGO)
        if i == 2 and self.s.logo_custom and Path(self.s.logo_custom).exists():
            return self.s.logo_custom
        return None

    def style(self) -> QRStyle:
        return QRStyle(
            fg=self.fg.color, bg=self.bg.color, size=self.px.value(), error=self.err.currentData(),
            shape=self.shape.currentData(), eye_shape=self.eye.currentData(),
            eye_color=self.eye_btn.color if self.eye_on.isChecked() else None,
            logo=self.logo_file(), logo_ratio=self.ratio.value() / 100, logo_border=self.logo_border.isChecked())

    def _preview_with(self, **changes):
        return render_png(self.sample, replace(self.style(), size=600, **changes))

    # --- acciones ---
    def _on_logo(self):
        if self.logo.currentIndex() == 2:
            f, _ = QFileDialog.getOpenFileName(self, "Elegir logo", "", "Imágenes (*.png *.jpg *.jpeg *.webp)")
            if f:
                self.s.logo_custom = f
                self.logo_path.setText(Path(f).name)
            elif not self.s.logo_custom:
                self.logo.blockSignals(True)
                self.logo.setCurrentIndex(0)
                self.logo.blockSignals(False)
        self._on_change()

    def _on_change(self, *_):
        s = self.s
        s.fg, s.bg = self.fg.color, self.bg.color
        s.qr_px, s.error = self.px.value(), self.err.currentData()
        s.shape, s.eye_shape = self.shape.currentData(), self.eye.currentData()
        s.eye_color_on, s.eye_color = self.eye_on.isChecked(), self.eye_btn.color
        s.logo_mode = ["none", "default", "custom"][self.logo.currentIndex()]
        s.logo_ratio = self.ratio.value() / 100
        s.logo_border = self.logo_border.isChecked()
        s.save()
        self.refresh()
        self.changed.emit()

    def set_sample(self, text: str):
        self.sample_real = bool(text)
        self.sample = text or "https://anyelostyle.com"
        self.refresh()

    def _status(self, text: str, color: str):
        self.badge.setText(text.upper())
        self.badge.setStyleSheet(f"color:{color};")
        self.dot.setStyleSheet(f"background:{color}; border-radius:4px;")

    def refresh(self):
        st = self.style()
        has_logo = st.logo is not None
        self.ratio.setEnabled(has_logo)
        self.logo_border.setEnabled(has_logo)
        try:
            img = render_png(self.sample, replace(st, size=min(st.px, 800)))
            self.preview.setPixmap(pil_to_pixmap(img, 232))
            if verify(img, self.sample):
                self._status("Se lee bien", brand.GOLD)
            else:
                self._status("No se pudo leer de vuelta", brand.RED_L)
        except Exception:
            self.preview.setText("Texto demasiado largo\npara este nivel de corrección")
            self._status("Sin vista previa", brand.MUTED)
        self.warn.setText("\n".join(style_warnings(st, self.sample)))


# ---------- páginas ----------

class Page(QWidget):
    """Cada página: etiqueta dorada, título editorial y contenido que se desplaza."""

    def __init__(self, tag: str, plain: str, em: str = "", tail: str = ""):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head = QVBoxLayout()
        head.setContentsMargins(40, 30, 40, 14)
        head.setSpacing(6)
        head.addWidget(eyebrow(tag))
        head.addWidget(headline(plain, em, tail))
        outer.addLayout(head)
        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(40, 6, 40, 30)
        self.body.setSpacing(16)
        outer.addWidget(scrolled(self.content), 1)


class GenerateTab(Page):
    def __init__(self, win: "MainWindow"):
        super().__init__("01 · Generar", "Pega, elige,", "fluye.")
        self.win = win

        c1 = StepCard(1, "Pon tus links", "Uno por línea. Para nombrar el archivo escribe «Nombre | link».")
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("https://anyelostyle.com\nPromo otoño | anyelostyle.com/otono\n…")
        self.text.setMinimumHeight(120)
        self.text.setFont(font("regular", 14))
        c1.body.addWidget(self.text)
        r = QHBoxLayout()
        self.count = muted("", 12)
        utm = LinkButton("Armar un link con UTM")
        utm.clicked.connect(lambda: win.pages.setCurrentWidget(win.utm_tab))
        r.addWidget(self.count, 1)
        r.addWidget(utm)
        c1.body.addLayout(r)

        self.dest = DestinationCard(win.settings, 2)
        win.register_destination(self.dest)

        c3 = StepCard(3, "Genera")
        row = QHBoxLayout()
        row.setSpacing(18)
        self.btn = CtaButton("Generar QR")
        self.btn.clicked.connect(self.generate)
        self.copy_btn = Pill("Copiar al portapapeles")
        self.copy_btn.clicked.connect(lambda: win.copy_qr(self._items(), self.table))
        row.addWidget(self.btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        c3.body.addLayout(row)
        c3.body.addWidget(muted("Copiar no crea ningún archivo: el QR va directo al portapapeles.", 12))
        self.table = ResultsTable()
        c3.body.addWidget(self.table)

        self.body.addWidget(c1)
        self.body.addWidget(self.dest)
        self.body.addWidget(c3)
        self.body.addStretch()

        self._timer = QTimer(singleShot=True, interval=300)
        self._timer.timeout.connect(self._sample)
        self.text.textChanged.connect(self._timer.start)
        win.panel.changed.connect(self._sample)

    def append_line(self, line: str):
        cur = self.text.toPlainText().rstrip("\n")
        self.text.setPlainText((cur + "\n" if cur else "") + line)

    def _items(self) -> list[Item]:
        return parse_lines(self.text.toPlainText(), self.win.settings.add_https)

    def _sample(self):
        items = self._items()
        self.count.setText(f"{len(items)} QR en la lista" if items else "")
        self.win.panel.set_sample(items[0].data if items else "")

    def generate(self):
        items = self._items()
        if not items:
            self.win.toast.show_message("Pega al menos un link para generar.", "warn")
            return
        self.win.run_batch(items, self.table, [self.btn, self.copy_btn])


class ExcelTab(Page):
    def __init__(self, win: "MainWindow"):
        super().__init__("02 · Excel / CSV", "Una fila,", "un QR.")
        self.win = win
        self.path = ""
        self.headers: list[str] = []
        self.rows: list[list[str]] = []

        c1 = StepCard(1, "Carga tu lista", "Un Excel (.xlsx) o un CSV. Si está en Google Sheets, descárgala como Excel o CSV.")
        top = QHBoxLayout()
        top.setSpacing(12)
        pick = Pill("Elegir archivo")
        pick.clicked.connect(self.choose)
        self.file_lbl = muted("Ningún archivo cargado", 13)
        self.sheet = QComboBox()
        self.sheet.setVisible(False)
        self.sheet.currentTextChanged.connect(self._sheet_changed)
        top.addWidget(pick)
        top.addWidget(self.file_lbl, 1)
        top.addWidget(self.sheet)
        c1.body.addLayout(top)
        cols = QGridLayout()
        cols.setHorizontalSpacing(14)
        cols.setVerticalSpacing(6)
        self.name_col = QComboBox()
        self.data_col = QComboBox()
        cols.addWidget(h2("Nombre del archivo"), 0, 0)
        cols.addWidget(h2("Link o dato del QR"), 0, 1)
        cols.addWidget(self.name_col, 1, 0)
        cols.addWidget(self.data_col, 1, 1)
        c1.body.addLayout(cols)
        self.preview = QTableWidget()
        style_table(self.preview)
        self.preview.setMaximumHeight(200)
        self.preview.setMinimumHeight(120)
        c1.body.addWidget(self.preview)

        self.dest = DestinationCard(win.settings, 2)
        win.register_destination(self.dest)

        c3 = StepCard(3, "Genera", "Un QR por cada fila de tu lista.")
        row = QHBoxLayout()
        self.btn = CtaButton("Generar un QR por fila")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.generate)
        row.addWidget(self.btn)
        row.addStretch()
        c3.body.addLayout(row)
        self.table = ResultsTable()
        c3.body.addWidget(self.table)

        self.body.addWidget(c1)
        self.body.addWidget(self.dest)
        self.body.addWidget(c3)
        self.body.addStretch()
        self.name_col.currentIndexChanged.connect(self._sample)
        self.data_col.currentIndexChanged.connect(self._sample)

    def choose(self):
        f, _ = QFileDialog.getOpenFileName(self, "Elegir archivo", "", "Excel o CSV (*.xlsx *.xlsm *.csv *.tsv *.txt)")
        if f:
            self.load(f)

    def load(self, path: str, sheet: str | None = None):
        try:
            if sheet is None:
                names = sheet_names(path)
                self.sheet.blockSignals(True)
                self.sheet.clear()
                self.sheet.addItems(names)
                self.sheet.setVisible(len(names) > 1)
                self.sheet.blockSignals(False)
                sheet = names[0] if names else None
            self.headers, self.rows = read_table(path, sheet)
        except Exception as exc:
            QMessageBox.warning(self, brand.APP_NAME, f"No pude leer el archivo.\n\n{exc}")
            return
        self.path = path
        self.file_lbl.setText(f"{Path(path).name} · {len(self.rows)} filas")
        n_idx, d_idx = guess_columns(self.headers, self.rows)
        for cb in (self.name_col, self.data_col):
            cb.blockSignals(True)
            cb.clear()
        self.name_col.addItem("(usar el link como nombre)", -1)
        for i, h in enumerate(self.headers):
            self.name_col.addItem(h, i)
            self.data_col.addItem(h, i)
        self.name_col.setCurrentIndex(self.name_col.findData(n_idx))
        self.data_col.setCurrentIndex(self.data_col.findData(d_idx))
        for cb in (self.name_col, self.data_col):
            cb.blockSignals(False)
        self.preview.setColumnCount(len(self.headers))
        self.preview.setHorizontalHeaderLabels([h.upper() for h in self.headers])
        shown = self.rows[:8]
        self.preview.setRowCount(len(shown))
        for r, row in enumerate(shown):
            for c, val in enumerate(row):
                self.preview.setItem(r, c, QTableWidgetItem(val))
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.btn.setEnabled(bool(self.rows))
        self._sample()

    def _sheet_changed(self, name: str):
        if self.path and name:
            self.load(self.path, name)

    def _items(self) -> list[Item]:
        return items_from_table(self.rows, self.name_col.currentData(), self.data_col.currentData(),
                                self.win.settings.add_https)

    def _sample(self):
        if self.rows:
            items = self._items()
            self.win.panel.set_sample(items[0].data if items else "")

    def generate(self):
        items = self._items()
        if not items:
            self.win.toast.show_message("La columna elegida no tiene datos.", "warn")
            return
        self.win.run_batch(items, self.table, [self.btn])


UTM_PRESETS = [("Instagram", "instagram", "social"), ("TikTok", "tiktok", "social"), ("YouTube", "youtube", "video"),
               ("WhatsApp", "whatsapp", "mensaje"), ("Facebook", "facebook", "social"), ("Email", "newsletter", "email"),
               ("QR impreso", "qr", "impreso")]


class UtmTab(Page):
    def __init__(self, win: "MainWindow"):
        super().__init__("03 · UTM", "Cada link,", "con rastro.")
        self.win = win
        c = StepCard(1, "Arma tu link", "Los parámetros UTM dicen de dónde llegó cada visita en Google Analytics.")
        self.base = QLineEdit()
        self.base.setPlaceholderText("anyelostyle.com/promo")
        c.body.addWidget(h2("Link base"))
        c.body.addWidget(self.base)
        c.body.addWidget(h2("Atajos para fuente y medio"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (label, src, med) in enumerate(UTM_PRESETS):
            b = Pill(label)
            b.clicked.connect(lambda _=False, s=src, m=med: self._preset(s, m))
            grid.addWidget(b, i // 4, i % 4)
        grid.setColumnStretch(4, 1)
        c.body.addLayout(grid)

        self.fields = {}
        for key, label, ph in (("source", "Fuente", "instagram"), ("medium", "Medio", "social"),
                               ("campaign", "Campaña", "otono-2026"), ("term", "Término (opcional)", ""),
                               ("content", "Contenido (opcional)", "")):
            row = QHBoxLayout()
            lb = h2(label)
            lb.setFixedWidth(190)
            e = QLineEdit()
            e.setPlaceholderText(ph)
            e.textChanged.connect(self.update_result)
            row.addWidget(lb)
            row.addWidget(e, 1)
            c.body.addLayout(row)
            self.fields[key] = e
        self.lower = QCheckBox("Todo en minúsculas (Analytics distingue mayúsculas)")
        self.lower.setChecked(True)
        self.lower.toggled.connect(self.update_result)
        c.body.addWidget(self.lower)
        self.base.textChanged.connect(self.update_result)

        c2 = StepCard(2, "Tu link", "Cópialo o súmalo a la lista de QR.")
        self.result = QLineEdit()
        self.result.setReadOnly(True)
        c2.body.addWidget(self.result)
        self.hint = muted("", 12)
        c2.body.addWidget(self.hint)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.add_btn = CtaButton("Agregar a la lista")
        self.add_btn.clicked.connect(self.add_to_list)
        self.copy_btn = Pill("Copiar link")
        self.copy_btn.clicked.connect(self.copy)
        row.addWidget(self.add_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        c2.body.addLayout(row)
        self.body.addWidget(c)
        self.body.addWidget(c2)
        self.body.addStretch()
        self.update_result()

    def _preset(self, source, medium):
        self.fields["source"].setText(source)
        self.fields["medium"].setText(medium)

    def link(self) -> str:
        f = {k: e.text() for k, e in self.fields.items()}
        return build_utm(self.base.text(), f["source"], f["medium"], f["campaign"], f["term"], f["content"], self.lower.isChecked())

    def update_result(self, *_):
        try:
            self.result.setText(self.link())
            self.hint.setText("")
            ok = True
        except ValueError as exc:
            self.result.setText("")
            self.hint.setText(str(exc))
            ok = False
        self.add_btn.setEnabled(ok)
        self.copy_btn.setEnabled(ok)

    def copy(self):
        QGuiApplication.clipboard().setText(self.result.text())
        self.win.toast.show_message("Link copiado.")

    def add_to_list(self):
        name = "_".join(x for x in (self.fields["campaign"].text(), self.fields["source"].text()) if x.strip())
        line = f"{safe_filename(name)} | {self.result.text()}" if name else self.result.text()
        self.win.generate_tab.append_line(line)
        self.win.pages.setCurrentWidget(self.win.generate_tab)
        self.win.toast.show_message("Link agregado a tu lista de QR.")


class ReadTab(Page):
    def __init__(self, win: "MainWindow"):
        super().__init__("04 · Leer", "Apunta,", "lee,", "decide.")
        self.win = win
        self.found = []
        self.drop = DropZone("Suelta aquí tus imágenes o PDFs", "También sirven carpetas enteras con códigos QR")
        self.drop.dropped.connect(self.read)
        self.body.addWidget(self.drop)
        row = QHBoxLayout()
        row.setSpacing(10)
        for label, fn in (("Elegir archivos", self.pick_files), ("Elegir carpeta", self.pick_folder),
                          ("Escanear la pantalla", lambda: win.scanner.show_menu())):
            b = Pill(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.body.addLayout(row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ARCHIVO", "PÁG.", "CONTENIDO", "AVISO"])
        style_table(self.table)
        self.table.setMinimumHeight(200)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.body.addWidget(self.table, 1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.copy_btn = Pill("Copiar contenidos")
        self.copy_btn.clicked.connect(self.copy_all)
        self.csv_btn = Pill("Exportar CSV")
        self.csv_btn.clicked.connect(self.export_csv)
        self.open_btn = Pill("Abrir link")
        self.open_btn.clicked.connect(self.open_link)
        self.info = muted("Aquí aparece lo que encuentres.", 12)
        for b in (self.copy_btn, self.csv_btn, self.open_btn):
            row2.addWidget(b)
        row2.addWidget(self.info, 1)
        self.body.addLayout(row2)

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Elegir archivos", "",
                                             "Imágenes y PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.pdf)")
        if fs:
            self.read(fs)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Elegir carpeta")
        if d:
            self.read([d])

    def read(self, paths: list):
        self.win.run_job(lambda prog: read_paths(paths, prog), self._done, [self.drop])

    def _done(self, result):
        found, errors = result
        self.found = found
        self.table.setRowCount(0)
        for f in found:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [Path(f.source).name, str(f.page or ""), f.text, "; ".join(f.warnings)]
            for c, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if c == 3 and val:
                    it.setForeground(QColor(brand.RED_L))
                self.table.setItem(i, c, it)
        msg = f"{len(found)} código(s) encontrado(s)."
        if errors:
            msg += f" {len(errors)} archivo(s) con problemas: " + "; ".join(errors[:2])
        elif not found:
            msg = "No se encontró ningún código. Prueba con una imagen más grande o con mejor luz."
        self.info.setText(msg)

    def copy_all(self):
        QGuiApplication.clipboard().setText("\n".join(f.text for f in self.found))
        self.win.toast.show_message("Copiado al portapapeles.")

    def export_csv(self):
        if not self.found:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Exportar", "qr_leidos.csv", "CSV (*.csv)")
        if f:
            with open(f, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["archivo", "pagina", "tipo", "contenido", "avisos"])
                for x in self.found:
                    w.writerow([x.source, x.page or "", x.kind, x.text, "; ".join(x.warnings)])
            self.win.toast.show_message("CSV guardado.")

    def open_link(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.found):
            self.win.toast.show_message("Selecciona una fila primero.", "warn")
            return
        f = self.found[r]
        if not is_url(f.text):
            self.win.toast.show_message("Ese contenido no es un link web.", "warn")
            return
        warn = ("\n\nCuidado:\n• " + "\n• ".join(f.warnings)) if f.warnings else ""
        ok = QMessageBox.question(self, "¿Abrir este link?", f"Este QR lleva a:\n\n{f.text}{warn}\n\n¿Abrirlo en el navegador?")
        if ok == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(f.text))


class SettingsTab(Page):
    def __init__(self, win: "MainWindow"):
        super().__init__("05 · Ajustes", "Hecho", "a tu manera.")
        self.win = win
        s = win.settings

        c1 = StepCard(1, "Atajo para escanear", "Funciona desde cualquier programa mientras Anyelo Style QR siga abierto.")
        self.hk_on = QCheckBox("Activar el atajo global")
        self.hk_on.setChecked(s.hotkey_enabled)
        c1.body.addWidget(self.hk_on)
        self.rec = HotkeyRecorder(s.hotkey)
        c1.body.addWidget(self.rec, alignment=Qt.AlignLeft)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.reset = Pill("")
        self.reset.clicked.connect(self._reset)
        self.hk_msg = muted("", 12)
        row.addWidget(self.reset)
        row.addWidget(self.hk_msg, 1)
        c1.body.addLayout(row)
        self.hk_warn = QLabel()
        self.hk_warn.setFont(font("regular", 12))
        self.hk_warn.setStyleSheet(f"color:{brand.RED_L};")
        self.hk_warn.setWordWrap(True)
        c1.body.addWidget(self.hk_warn)
        c1.body.addWidget(muted("Haz clic en la combinación y presiona las teclas que quieras. Incluye Ctrl, Alt o Windows "
                                "para no estorbar cuando escribes.", 12))
        self.keep = QCheckBox("Al cerrar la ventana, seguir en segundo plano (ícono junto al reloj)")
        self.keep.setChecked(s.keep_running)
        c1.body.addWidget(self.keep)

        c2 = StepCard(2, "Al generar", "Valores que casi nunca hace falta tocar.")
        self.o_https = QCheckBox("Agregar https:// cuando falte")
        self.o_dupes = QCheckBox("Omitir links repetidos")
        self.o_verify = QCheckBox("Leer de vuelta cada QR creado para confirmar que escanea")
        self.o_over = QCheckBox("Reemplazar archivos que ya existen (si no, se agrega -2, -3…)")
        for cb, val in ((self.o_https, s.add_https), (self.o_dupes, s.skip_dupes), (self.o_verify, s.verify), (self.o_over, s.overwrite)):
            cb.setChecked(val)
            c2.body.addWidget(cb)
            cb.toggled.connect(self._save)

        c3 = StepCard(3, "Acerca de")
        c3.body.addWidget(muted(f"{brand.APP_NAME} v{brand.VERSION} · código abierto (MIT) · funciona sin internet. "
                                "Tipografía: Bricolage Grotesque (SIL OFL).", 13))
        self.body.addWidget(c1)
        self.body.addWidget(c2)
        self.body.addWidget(c3)
        self.body.addStretch()

        self.hk_on.toggled.connect(self._toggle_hotkey)
        self.rec.recordingChanged.connect(win.pause_hotkey)
        self.rec.committed.connect(self._commit)
        self.rec.rejected.connect(lambda m: win.toast.show_message(m, "warn"))
        self.keep.toggled.connect(self._save)
        self.refresh()

    def _save(self, *_):
        s = self.win.settings
        s.keep_running = self.keep.isChecked()
        s.add_https, s.skip_dupes = self.o_https.isChecked(), self.o_dupes.isChecked()
        s.verify, s.overwrite = self.o_verify.isChecked(), self.o_over.isChecked()
        s.save()
        self.win.panel.refresh()

    def _toggle_hotkey(self, on: bool):
        self.win.settings.hotkey_enabled = on
        self.win.settings.save()
        ok, msg = self.win.apply_hotkey()
        if not ok:
            self.win.toast.show_message(msg, "warn")
        self.refresh()

    def _commit(self, text: str):
        ok, msg = self.win.set_hotkey(text)
        if ok:
            self.win.toast.show_message(f"Atajo guardado: {text}")
        else:
            self.rec.set_value(self.win.settings.hotkey)
            self.win.toast.show_message(msg, "warn")
        self.refresh()

    def _reset(self):
        d = default_hotkey()
        self._commit(d)
        self.rec.set_value(self.win.settings.hotkey)

    def refresh(self):
        s = self.win.settings
        d = default_hotkey()
        self.rec.set_value(s.hotkey)
        self.reset.setText(f"Restablecer a {d}")
        self.reset.setEnabled(s.hotkey != d)
        if not GlobalHotkey.supported():
            self.hk_msg.setText("El atajo global solo funciona en Windows.")
        elif self.win.hotkey.active:
            self.hk_msg.setText("Activo ahora.")
        else:
            self.hk_msg.setText("Desactivado.")
        ch = altgr_conflict(s.hotkey)
        if ch:
            self.hk_warn.setText(f"Con tu teclado, {s.hotkey} escribe «{ch}». Mientras el programa esté abierto, "
                                 f"esa combinación dejaría de escribir «{ch}» en cualquier parte.")
        elif d != FACTORY_HOTKEY:
            self.hk_warn.setText(f"En tu teclado {FACTORY_HOTKEY} escribe «{altgr_conflict(FACTORY_HOTKEY)}», "
                                 f"por eso el recomendado es {d}.")
        else:
            self.hk_warn.setText("")


# ---------- ventana ----------

class MainWindow(QMainWindow):
    NAV = [("01", "Generar"), ("02", "Excel / CSV"), ("03", "UTM"), ("04", "Leer"), ("05", "Ajustes")]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(brand.APP_NAME)
        self.resize(1320, 840)
        self.setMinimumSize(1100, 700)
        self._job: Job | None = None
        self._quitting = False
        self._told = False
        self._titlebar_done = False
        self._destinations: list[DestinationCard] = []
        self.settings = Settings.load()
        self.tray: QSystemTrayIcon | None = None
        self.hotkey = GlobalHotkey(lambda: self.scanner.show_menu())
        self.scanner = Scanner(self, lambda: self.settings.hotkey if self.hotkey.active else "")

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # riel lateral
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(226)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(0, 26, 0, 20)
        rv.setSpacing(0)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(22, 0, 18, 0)
        brand_row.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(DEFAULT_LOGO)).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(headline("Anyelo", "Style", px=19))
        names.addWidget(eyebrow("QR · sin internet", brand.GOLD, 10))
        brand_row.addWidget(logo)
        brand_row.addLayout(names)
        rv.addLayout(brand_row)
        rv.addSpacing(34)
        self.nav_buttons = []
        for num, label in self.NAV:
            b = NavButton(num, label)
            self.nav_buttons.append(b)
            rv.addWidget(b)
        rv.addStretch()
        foot = QVBoxLayout()
        foot.setContentsMargins(22, 0, 22, 0)
        foot.setSpacing(8)
        scan = Pill("Escanear pantalla")
        scan.clicked.connect(lambda: self.scanner.show_menu())
        foot.addWidget(scan)
        self.hk_hint = eyebrow("", brand.MUTED, 10)
        foot.addWidget(self.hk_hint, alignment=Qt.AlignHCenter)
        foot.addWidget(muted(f"v{brand.VERSION}", 11), alignment=Qt.AlignHCenter)
        rv.addLayout(foot)
        outer.addWidget(rail)

        # centro: páginas
        center = QVBoxLayout()
        center.setSpacing(0)
        self.panel = StylePanel(self.settings)
        self.pages = Pages()
        self.tabs = self.pages        # nombre anterior, lo usan las pruebas
        self.generate_tab = GenerateTab(self)
        self.excel_tab = ExcelTab(self)
        self.utm_tab = UtmTab(self)
        self.read_tab = ReadTab(self)
        self.settings_tab = SettingsTab(self)
        for page in (self.generate_tab, self.excel_tab, self.utm_tab, self.read_tab, self.settings_tab):
            self.pages.addWidget(page)
        center.addWidget(self.pages, 1)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        center.addWidget(self.bar)
        self.status = muted("", 12)
        self.status.setContentsMargins(40, 8, 40, 10)
        self.status.setFixedHeight(32)
        center.addWidget(self.status)
        outer.addLayout(center, 1)

        # panel de estilo (solo en las páginas que generan)
        self.panel_scroll = QScrollArea()
        self.panel_scroll.setWidget(self.panel)
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.panel_scroll.setFixedWidth(334)
        self.panel_scroll.setStyleSheet(f"QScrollArea{{background:{brand.SURFACE}; border-left:1px solid {brand.LINE};}}")
        outer.addWidget(self.panel_scroll)

        for i, b in enumerate(self.nav_buttons):
            b.clicked.connect(lambda _=False, i=i: self.pages.setCurrentIndex(i))
        self.pages.currentChanged.connect(self._page_changed)
        self.panel.copy_requested.connect(self.copy_preview)
        self.toast = Toast(root)

        self._setup_tray()
        self.apply_hotkey()
        self._page_changed(0)

    # --- navegación ---
    def _page_changed(self, i: int):
        for k, b in enumerate(self.nav_buttons):
            b.setChecked(k == i)
        self.panel_scroll.setVisible(i in (0, 1))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast"):
            self.toast.reposition()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._titlebar_done:
            self._titlebar_done = True
            winfx.style_titlebar(int(self.winId()), brand.INK, brand.BONE)

    # --- atajo y bandeja ---
    def apply_hotkey(self) -> tuple[bool, str]:
        if not self.settings.hotkey_enabled:
            self.hotkey.unregister()
            self._refresh_hotkey_ui()
            return True, ""
        ok, msg = self.hotkey.register(self.settings.hotkey)
        self._refresh_hotkey_ui()
        return ok, msg

    def pause_hotkey(self, recording: bool):
        """Mientras se graba una combinación nueva, el atajo actual se libera para poder grabar la misma."""
        if recording:
            self.hotkey.unregister()
        else:
            self.apply_hotkey()

    def set_hotkey(self, text: str) -> tuple[bool, str]:
        old = self.settings.hotkey
        if not self.settings.hotkey_enabled:
            self.settings.hotkey = text
            self.settings.save()
            return True, ""
        ok, msg = self.hotkey.register(text)
        if ok:
            self.settings.hotkey = text
            self.settings.save()
        else:
            self.hotkey.register(old)
        self._refresh_hotkey_ui()
        return ok, msg

    def _refresh_hotkey_ui(self):
        hk = self.settings.hotkey if self.hotkey.active else ""
        self.hk_hint.setText(f"Atajo  {hk}".upper() if hk else "")
        if self.tray:
            self.tray.setToolTip(f"{brand.APP_NAME}" + (f" ({hk})" if hk else ""))
        if hasattr(self, "settings_tab"):
            self.settings_tab.refresh()

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(str(asset("icon.ico"))), self)
        menu = QMenu()
        act_scan = QAction("Escanear QR…", self)
        act_scan.triggered.connect(lambda: self.scanner.show_menu())
        act_new = QAction("Crear un QR", self)
        act_new.triggered.connect(self.open_create)
        act_open = QAction("Abrir Anyelo Style QR", self)
        act_open.triggered.connect(self.show_window)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self.quit_app)
        for a in (act_scan, act_new, act_open):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.scanner.show_menu() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_create(self):
        """Abre el programa listo para crear: en 'Generar', con el link copiado ya pegado si lo hay."""
        self.show_window()
        self.pages.setCurrentWidget(self.generate_tab)
        gt = self.generate_tab
        if not gt.text.toPlainText().strip():
            clip = QGuiApplication.clipboard().text().strip()
            if clip and "\n" not in clip and len(clip) < 2000:
                n = normalize_data(clip)
                if re.match(r"^https?://\S+$", n, re.I):
                    gt.text.setPlainText(n)
                    self.toast.show_message("Pegué el link que tenías copiado.")
        gt.text.setFocus()

    def quit_app(self):
        self._quitting = True
        self.hotkey.unregister()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        if not self._quitting and self.tray and self.settings.keep_running:
            e.ignore()
            self.hide()
            if not self._told:
                self._told = True
                hk = f" Atajo: {self.settings.hotkey}." if self.hotkey.active else ""
                self.tray.showMessage(brand.APP_NAME, "Sigue activo junto al reloj." + hk, QSystemTrayIcon.Information, 4000)
            return
        self.hotkey.unregister()
        e.accept()

    # --- destinos sincronizados ---
    def register_destination(self, card: DestinationCard):
        self._destinations.append(card)
        card.changed.connect(lambda c=card: [d.load() for d in self._destinations if d is not c])

    # --- trabajos en segundo plano ---
    def run_job(self, fn, on_done, lock=()):
        if self._job and self._job.isRunning():
            return
        for w in lock:
            w.setEnabled(False)
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        self.status.setText("Trabajando…")
        job = Job(fn)
        job.progress.connect(self._on_progress)

        def finish():
            for w in lock:
                w.setEnabled(True)
            self.bar.setVisible(False)

        def ok(res):
            finish()
            self.status.setText("")
            on_done(res)

        def bad(msg):
            finish()
            self.status.setText("")
            self.toast.show_message(msg, "warn")

        job.done.connect(ok)
        job.failed.connect(bad)
        self._job = job
        job.start()

    def _on_progress(self, i: int, n: int):
        self.bar.setRange(0, n)
        self.bar.setValue(i)
        self.status.setText(f"{i} de {n}")

    def run_batch(self, items: list[Item], table: ResultsTable, lock):
        s = self.settings
        if not s.out_dir:
            d = QFileDialog.getExistingDirectory(self, "¿Dónde guardo los QR?", str(Path.home()))
            if not d:
                return
            s.out_dir = d
            s.save()
            for card in self._destinations:
                card.load()
        if not s.fmts:
            self.toast.show_message("Marca al menos un formato (PNG, SVG o PDF) en el paso 2.", "warn")
            return
        style, out, fmts = self.panel.style(), s.out_dir, list(s.fmts)
        dupes, ver, over, after = s.skip_dupes, s.verify, s.overwrite, s.open_after

        def fn(prog):
            return generate_batch(items, out, fmts, style, ver, dupes, over, prog)

        def done(rows):
            table.show_rows(rows)
            ok = sum(r.status == "ok" for r in rows)
            bad = sum(r.status in ("aviso", "error") for r in rows)
            msg = f"{ok} QR listos" + (f" · {bad} para revisar" if bad else "")
            self.toast.show_message(msg, "ok" if not bad else "warn")
            if after and (ok or bad):
                open_folder(out)

        self.run_job(fn, done, lock)

    # --- portapapeles (sin crear archivos) ---
    def _copy_data(self, data: str):
        try:
            img = render_png(data, self.panel.style())
        except Exception as exc:
            self.toast.show_message(f"No pude crear ese QR: {exc}", "warn")
            return False
        QGuiApplication.clipboard().setImage(pil_to_qimage(img))
        return True

    def copy_qr(self, items: list[Item], table: ResultsTable):
        data = None
        row = table.currentRow() if not table.isHidden() else -1
        if row >= 0:
            data = table.item(row, 0).data(Qt.UserRole)
        if not data and items:
            data = items[0].data
        if not data:
            self.toast.show_message("Pega un link y copio su QR al instante.", "warn")
            return
        if self._copy_data(data):
            extra = " (el primero de la lista)" if len(items) > 1 and row < 0 else ""
            self.toast.show_message(f"QR copiado{extra}. No se guardó ningún archivo.")

    def copy_preview(self):
        if not self.panel.sample_real:
            self.toast.show_message("Escribe o pega un link y copio su QR al instante.", "warn")
            return
        if self._copy_data(self.panel.sample):
            self.toast.show_message("QR copiado. No se guardó ningún archivo.")


def _splash() -> QSplashScreen:
    pm = QPixmap(540, 300)
    pm.fill(QColor(brand.INK))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(brand.LINE_2))
    p.drawRect(0, 0, 539, 299)
    logo = QPixmap(str(DEFAULT_LOGO)).scaled(84, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawPixmap((540 - 84) // 2, 58, logo)
    p.setFont(font("xbold", 30, -0.6))
    p.setPen(QColor(brand.BONE))
    p.drawText(pm.rect().adjusted(0, 156, 0, 0), Qt.AlignHCenter | Qt.AlignTop, "Anyelo Style")
    p.setFont(font("semibold", 11, 2.2))
    p.setPen(QColor(brand.GOLD))
    p.drawText(pm.rect().adjusted(0, 204, 0, 0), Qt.AlignHCenter | Qt.AlignTop, "QR  ·  SIN INTERNET")
    p.fillRect(250, 250, 40, 2, QColor(brand.GOLD))
    p.end()
    return QSplashScreen(pm, Qt.WindowStaysOnTopHint)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(brand.APP_NAME)
    app.setOrganizationName(brand.ORG)
    app.setQuitOnLastWindowClosed(False)
    load_fonts()
    app.setFont(font("regular", 13))
    app.setStyleSheet(build_qss())
    icon = asset("icon.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    lock = QLockFile(str(Path(tempfile.gettempdir()) / "AnyeloStyleQR.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.information(None, brand.APP_NAME,
                                "Anyelo Style QR ya está abierto. Búscalo junto al reloj (ícono en la bandeja).")
        sys.exit(0)

    splash = _splash()
    splash.show()
    app.processEvents()
    t0 = time.monotonic()
    win = MainWindow()
    win.show()
    wait = max(0, 900 - int((time.monotonic() - t0) * 1000))
    QTimer.singleShot(wait, lambda: splash.finish(win))
    code = app.exec()
    lock.unlock()
    sys.exit(code)
