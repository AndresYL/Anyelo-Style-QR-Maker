"""Ventana principal (PySide6)."""
from __future__ import annotations

import csv
import io
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QLockFile, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSlider,
    QSpinBox, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import brand
from .core import (ERROR_LEVELS, EYE_SHAPES, MAX_PX, MIN_PX, SHAPES, Item, QRStyle, build_utm, generate_batch,
                   parse_lines, render_png, safe_filename, style_warnings, verify)
from .hotkey import GlobalHotkey
from .paths import DEFAULT_LOGO, asset
from .reader import is_url, read_paths
from .scanner import Scanner
from .settings import Settings
from .tabular import guess_columns, items_from_table, read_table, sheet_names
from .theme import build_qss
from .widgets import (ColorButton, DestinationCard, DropZone, Job, ResultsTable, StepCard, h2, muted, open_folder,
                      pil_to_pixmap, pil_to_qimage, scrolled)


# ---------- panel de estilo (derecha) ----------

class StylePanel(QFrame):
    changed = Signal()

    def __init__(self, s: Settings):
        super().__init__()
        self.setObjectName("panel")
        self.s = s
        self.sample = "https://anyelostyle.com"
        self.setFixedWidth(300)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(6)

        self.preview = QLabel(alignment=Qt.AlignCenter)
        self.preview.setFixedHeight(216)
        v.addWidget(self.preview)
        self.badge = QLabel(alignment=Qt.AlignCenter)
        v.addWidget(self.badge)
        self.warn = QLabel()
        self.warn.setObjectName("warn")
        self.warn.setWordWrap(True)
        v.addWidget(self.warn)

        v.addWidget(h2("Colores"))
        row = QHBoxLayout()
        self.fg = ColorButton(s.fg, "Color del código", lambda c: self._preview_with(fg=c))
        self.bg = ColorButton(s.bg, "Color del fondo", lambda c: self._preview_with(bg=c))
        row.addWidget(QLabel("Código"))
        row.addWidget(self.fg)
        row.addSpacing(10)
        row.addWidget(QLabel("Fondo"))
        row.addWidget(self.bg)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(h2("Forma"))
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

        v.addWidget(h2("Logo en el centro"))
        self.logo = QComboBox()
        self.logo.addItems(["Sin logo", "Anyelo Style", "Otro logo…"])
        self.logo.setCurrentIndex({"none": 0, "default": 1, "custom": 2}[s.logo_mode])
        v.addWidget(self.logo)
        self.logo_path = muted(Path(s.logo_custom).name if s.logo_custom else "")
        v.addWidget(self.logo_path)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Tamaño"))
        self.ratio = QSlider(Qt.Horizontal)
        self.ratio.setRange(10, 30)
        self.ratio.setValue(int(s.logo_ratio * 100))
        r2.addWidget(self.ratio)
        v.addLayout(r2)
        self.logo_border = QCheckBox("Con borde")
        self.logo_border.setChecked(s.logo_border)
        v.addWidget(self.logo_border)

        v.addWidget(h2("Tamaño y calidad"))
        r3 = QHBoxLayout()
        self.px = QSpinBox()
        self.px.setRange(MIN_PX, MAX_PX)
        self.px.setSuffix(" px")
        self.px.setValue(s.qr_px)
        self.px.setKeyboardTracking(False)
        r3.addWidget(QLabel("Lado:"))
        r3.addWidget(self.px, 1)
        v.addLayout(r3)
        self.err = QComboBox()
        for k, label in ERROR_LEVELS.items():
            self.err.addItem("Corrección: " + label, k)
        self.err.setCurrentIndex(max(0, self.err.findData(s.error)))
        v.addWidget(self.err)
        v.addWidget(muted("Con logo, la corrección sube sola a Máxima. El QR siempre es cuadrado."))
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
        st = replace(self.style(), size=600, **changes)
        return render_png(self.sample, st)

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
        self.sample = text or "https://anyelostyle.com"
        self.refresh()

    def refresh(self):
        st = self.style()
        has_logo = st.logo is not None
        self.ratio.setEnabled(has_logo)
        self.logo_border.setEnabled(has_logo)
        try:
            img = render_png(self.sample, replace(st, size=min(st.px, 800)))
            self.preview.setPixmap(pil_to_pixmap(img, 210))
            if verify(img, self.sample):
                self.badge.setText("✓ Se lee bien")
                self.badge.setObjectName("good")
            else:
                self.badge.setText("⚠ No se pudo leer de vuelta")
                self.badge.setObjectName("bad")
        except Exception:
            self.preview.setText("Texto demasiado largo\npara este nivel de corrección")
            self.badge.setText("")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.warn.setText("\n".join(style_warnings(st, self.sample)))


# ---------- pestañas ----------

class GenerateTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 8, 10, 8)
        v.setSpacing(12)

        c1 = StepCard(1, "Pon tus links", "Uno por línea. Para nombrar el archivo escribe «Nombre | link».")
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("https://anyelostyle.com\nPromo otoño | anyelostyle.com/otono\n…")
        self.text.setMinimumHeight(110)
        c1.body.addWidget(self.text)
        r = QHBoxLayout()
        self.count = muted("")
        utm = QPushButton("Armar un link con UTM →")
        utm.setObjectName("link")
        utm.clicked.connect(lambda: win.tabs.setCurrentWidget(win.utm_tab))
        r.addWidget(self.count, 1)
        r.addWidget(utm)
        c1.body.addLayout(r)

        self.dest = DestinationCard(win.settings, 2)
        win.register_destination(self.dest)

        c3 = StepCard(3, "Genera", "Los QR se guardan en tu carpeta. También puedes copiar uno al portapapeles.")
        row = QHBoxLayout()
        self.btn = QPushButton("Generar QR")
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.generate)
        self.copy_btn = QPushButton("Copiar QR al portapapeles")
        self.copy_btn.clicked.connect(lambda: win.copy_qr(self._items(), self.table))
        row.addWidget(self.btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        c3.body.addLayout(row)
        self.table = ResultsTable()
        c3.body.addWidget(self.table)

        v.addWidget(c1)
        v.addWidget(self.dest)
        v.addWidget(c3)
        v.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(page))

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
            QMessageBox.information(self, brand.APP_NAME, "Pega al menos un link.")
            return
        self.win.run_batch(items, self.table, [self.btn, self.copy_btn])


class ExcelTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.path = ""
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 8, 10, 8)
        v.setSpacing(12)

        c1 = StepCard(1, "Carga tu lista", "Un Excel (.xlsx) o un CSV. Si está en Google Sheets, descárgala como Excel o CSV.")
        top = QHBoxLayout()
        pick = QPushButton("Elegir archivo…")
        pick.clicked.connect(self.choose)
        self.file_lbl = muted("Ningún archivo cargado")
        self.sheet = QComboBox()
        self.sheet.setVisible(False)
        self.sheet.currentTextChanged.connect(self._sheet_changed)
        top.addWidget(pick)
        top.addWidget(self.file_lbl, 1)
        top.addWidget(self.sheet)
        c1.body.addLayout(top)
        cols = QHBoxLayout()
        self.name_col = QComboBox()
        self.data_col = QComboBox()
        cols.addWidget(QLabel("Nombre del archivo:"))
        cols.addWidget(self.name_col, 1)
        cols.addSpacing(12)
        cols.addWidget(QLabel("Link o dato del QR:"))
        cols.addWidget(self.data_col, 1)
        c1.body.addLayout(cols)
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setMaximumHeight(190)
        self.preview.setMinimumHeight(120)
        c1.body.addWidget(self.preview)

        self.dest = DestinationCard(win.settings, 2)
        win.register_destination(self.dest)

        c3 = StepCard(3, "Genera", "Un QR por cada fila de tu lista.")
        row = QHBoxLayout()
        self.btn = QPushButton("Generar un QR por fila")
        self.btn.setObjectName("primary")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.generate)
        row.addWidget(self.btn)
        row.addStretch()
        c3.body.addLayout(row)
        self.table = ResultsTable()
        c3.body.addWidget(self.table)

        v.addWidget(c1)
        v.addWidget(self.dest)
        v.addWidget(c3)
        v.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(page))
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
        self.preview.setHorizontalHeaderLabels(self.headers)
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
            QMessageBox.information(self, brand.APP_NAME, "La columna elegida no tiene datos.")
            return
        self.win.run_batch(items, self.table, [self.btn])


class ReadTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.found = []
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 8, 10, 8)
        self.drop = DropZone("Arrastra aquí imágenes, PDFs o carpetas con códigos QR")
        self.drop.dropped.connect(self.read)
        v.addWidget(self.drop, 1)
        row = QHBoxLayout()
        b1 = QPushButton("Elegir archivos…")
        b1.clicked.connect(self.pick_files)
        b2 = QPushButton("Elegir carpeta…")
        b2.clicked.connect(self.pick_folder)
        b3 = QPushButton("Escanear la pantalla…")
        b3.clicked.connect(lambda: win.scanner.show_menu())
        for b in (b1, b2, b3):
            row.addWidget(b)
        row.addStretch()
        v.addLayout(row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Pág.", "Contenido", "Aviso"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        v.addWidget(self.table, 3)

        row2 = QHBoxLayout()
        self.copy_btn = QPushButton("Copiar contenidos")
        self.copy_btn.clicked.connect(self.copy_all)
        self.csv_btn = QPushButton("Exportar CSV…")
        self.csv_btn.clicked.connect(self.export_csv)
        self.open_btn = QPushButton("Abrir link…")
        self.open_btn.clicked.connect(self.open_link)
        self.info = muted("")
        for b in (self.copy_btn, self.csv_btn, self.open_btn):
            row2.addWidget(b)
        row2.addWidget(self.info, 1)
        v.addLayout(row2)

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
                    it.setForeground(QColor(brand.WARN))
                self.table.setItem(i, c, it)
        msg = f"{len(found)} código(s) encontrado(s)."
        if errors:
            msg += f" {len(errors)} archivo(s) con problemas: " + "; ".join(errors[:2])
        elif not found:
            msg = "No se encontró ningún código. Prueba con una imagen más grande o con mejor luz."
        self.info.setText(msg)

    def copy_all(self):
        QGuiApplication.clipboard().setText("\n".join(f.text for f in self.found))
        self.info.setText("Copiado al portapapeles.")

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
            self.info.setText("CSV guardado.")

    def open_link(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.found):
            self.info.setText("Selecciona una fila primero.")
            return
        f = self.found[r]
        if not is_url(f.text):
            self.info.setText("Ese contenido no es un link web.")
            return
        warn = ("\n\nCuidado:\n• " + "\n• ".join(f.warnings)) if f.warnings else ""
        ok = QMessageBox.question(self, "¿Abrir este link?", f"Este QR lleva a:\n\n{f.text}{warn}\n\n¿Abrirlo en el navegador?")
        if ok == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(f.text))


UTM_PRESETS = [("Instagram", "instagram", "social"), ("TikTok", "tiktok", "social"), ("YouTube", "youtube", "video"),
               ("WhatsApp", "whatsapp", "mensaje"), ("Facebook", "facebook", "social"), ("Email", "newsletter", "email"),
               ("QR impreso", "qr", "impreso")]


class UtmTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 8, 10, 8)
        v.setSpacing(12)
        c = StepCard(1, "Arma tu link con UTM", "Los parámetros UTM te dicen de dónde llegó cada visita en Google Analytics.")
        self.base = QLineEdit()
        self.base.setPlaceholderText("anyelostyle.com/promo")
        c.body.addWidget(QLabel("Link base"))
        c.body.addWidget(self.base)

        c.body.addWidget(muted("Atajos para fuente y medio:"))
        chips = QHBoxLayout()
        for label, src, med in UTM_PRESETS:
            b = QPushButton(label)
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, s=src, m=med: self._preset(s, m))
            chips.addWidget(b)
        chips.addStretch()
        c.body.addLayout(chips)

        self.fields = {}
        grid = QVBoxLayout()
        for key, label, ph in (("source", "Fuente (utm_source)", "instagram"), ("medium", "Medio (utm_medium)", "social"),
                               ("campaign", "Campaña (utm_campaign)", "otono-2026"),
                               ("term", "Término (opcional)", ""), ("content", "Contenido (opcional)", "")):
            row = QHBoxLayout()
            lb = QLabel(label)
            lb.setFixedWidth(190)
            e = QLineEdit()
            e.setPlaceholderText(ph)
            e.textChanged.connect(self.update_result)
            row.addWidget(lb)
            row.addWidget(e, 1)
            grid.addLayout(row)
            self.fields[key] = e
        c.body.addLayout(grid)
        self.lower = QCheckBox("Pasar todo a minúsculas (recomendado: Analytics distingue mayúsculas)")
        self.lower.setChecked(True)
        self.lower.toggled.connect(self.update_result)
        c.body.addWidget(self.lower)
        self.base.textChanged.connect(self.update_result)

        c2 = StepCard(2, "Tu link", "Cópialo o súmalo a la lista de QR.")
        self.result = QLineEdit()
        self.result.setReadOnly(True)
        c2.body.addWidget(self.result)
        self.hint = muted("")
        c2.body.addWidget(self.hint)
        row = QHBoxLayout()
        self.add_btn = QPushButton("Agregar a la lista de QR")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self.add_to_list)
        self.copy_btn = QPushButton("Copiar link")
        self.copy_btn.clicked.connect(self.copy)
        row.addWidget(self.add_btn)
        row.addWidget(self.copy_btn)
        row.addStretch()
        c2.body.addLayout(row)
        v.addWidget(c)
        v.addWidget(c2)
        v.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(page))
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
        self.hint.setText("Link copiado.")

    def add_to_list(self):
        name = "_".join(x for x in (self.fields["campaign"].text(), self.fields["source"].text()) if x.strip())
        line = f"{safe_filename(name)} | {self.result.text()}" if name else self.result.text()
        self.win.generate_tab.append_line(line)
        self.win.tabs.setCurrentWidget(self.win.generate_tab)
        self.win.status.setText("Link agregado a tu lista de QR")


class SettingsTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        s = win.settings
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 8, 10, 8)
        v.setSpacing(12)

        c1 = StepCard(1, "Atajo para escanear QR", "Funciona desde cualquier programa mientras Anyelo Style QR siga abierto.")
        self.hk_on = QCheckBox("Activar el atajo global")
        self.hk_on.setChecked(s.hotkey_enabled)
        self.hk_edit = QKeySequenceEdit()
        self.hk_edit.setMaximumSequenceLength(1)
        from PySide6.QtGui import QKeySequence
        self.hk_edit.setKeySequence(QKeySequence(s.hotkey))
        self.hk_status = muted("")
        row = QHBoxLayout()
        row.addWidget(QLabel("Combinación:"))
        row.addWidget(self.hk_edit, 1)
        c1.body.addWidget(self.hk_on)
        c1.body.addLayout(row)
        c1.body.addWidget(self.hk_status)
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
        c3.body.addWidget(muted(f"{brand.APP_NAME} v{brand.VERSION} · código abierto (MIT) · funciona sin internet."))
        v.addWidget(c1)
        v.addWidget(c2)
        v.addWidget(c3)
        v.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(page))

        self.hk_on.toggled.connect(self._hotkey_changed)
        self.hk_edit.editingFinished.connect(self._hotkey_changed)
        self.keep.toggled.connect(self._save)
        self.refresh_status()

    def _save(self, *_):
        s = self.win.settings
        s.keep_running = self.keep.isChecked()
        s.add_https, s.skip_dupes = self.o_https.isChecked(), self.o_dupes.isChecked()
        s.verify, s.overwrite = self.o_verify.isChecked(), self.o_over.isChecked()
        s.save()
        self.win.panel.refresh()

    def _hotkey_changed(self, *_):
        s = self.win.settings
        seq = self.hk_edit.keySequence().toString()
        s.hotkey_enabled = self.hk_on.isChecked()
        if seq:
            s.hotkey = seq
        ok, msg = self.win.apply_hotkey()
        if not ok and s.hotkey_enabled:
            self.hk_status.setText(msg)
        else:
            self.refresh_status()
        s.save()

    def refresh_status(self):
        s = self.win.settings
        if not GlobalHotkey.supported():
            self.hk_status.setText("El atajo global solo funciona en Windows.")
        elif self.win.hotkey.active:
            self.hk_status.setText(f"Activo: {s.hotkey}")
        else:
            self.hk_status.setText("Desactivado.")


# ---------- ventana ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(brand.APP_NAME)
        self.resize(1200, 780)
        self.setMinimumSize(1000, 640)
        self._job: Job | None = None
        self._quitting = False
        self._destinations: list[DestinationCard] = []
        self.settings = Settings.load()
        self.tray: QSystemTrayIcon | None = None
        self.hotkey = GlobalHotkey(lambda: self.scanner.show_menu())
        self.scanner = Scanner(self, lambda: self.settings.hotkey if self.hotkey.active else "")

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 12)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(DEFAULT_LOGO)).scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        title = QLabel(brand.APP_NAME)
        title.setObjectName("h1")
        head.addWidget(logo)
        head.addSpacing(8)
        head.addWidget(title)
        head.addStretch()
        scan = QPushButton("Escanear QR en pantalla")
        scan.clicked.connect(lambda: self.scanner.show_menu())
        ver = muted(f"v{brand.VERSION} · funciona sin internet")
        ver.setWordWrap(False)
        head.addWidget(scan)
        head.addSpacing(12)
        head.addWidget(ver)
        outer.addLayout(head)

        body = QHBoxLayout()
        self.panel = StylePanel(self.settings)
        self.tabs = QTabWidget()
        self.generate_tab = GenerateTab(self)
        self.excel_tab = ExcelTab(self)
        self.utm_tab = UtmTab(self)
        self.read_tab = ReadTab(self)
        self.settings_tab = SettingsTab(self)
        self.tabs.addTab(self.generate_tab, "Generar")
        self.tabs.addTab(self.excel_tab, "Excel / CSV")
        self.tabs.addTab(self.utm_tab, "UTM")
        self.tabs.addTab(self.read_tab, "Leer QR")
        self.tabs.addTab(self.settings_tab, "Ajustes")
        sc = QScrollArea()
        sc.setWidget(self.panel)
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setFixedWidth(322)
        body.addWidget(self.tabs, 1)
        body.addWidget(sc)
        outer.addLayout(body, 1)

        foot = QHBoxLayout()
        self.status = muted("Listo")
        self.bar = QProgressBar()
        self.bar.setFixedWidth(220)
        self.bar.setVisible(False)
        foot.addWidget(self.status, 1)
        foot.addWidget(self.bar)
        outer.addLayout(foot)

        self._setup_tray()
        self.apply_hotkey()
        self.settings_tab.refresh_status()

    # --- atajo y bandeja ---
    def apply_hotkey(self) -> tuple[bool, str]:
        if not self.settings.hotkey_enabled:
            self.hotkey.unregister()
            self._refresh_tray_text()
            return True, ""
        ok, msg = self.hotkey.register(self.settings.hotkey)
        self._refresh_tray_text()
        return ok, msg

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(str(asset("icon.ico"))), self)
        menu = QMenu()
        self.act_scan = QAction("Escanear QR…", self)
        self.act_scan.triggered.connect(lambda: self.scanner.show_menu())
        act_open = QAction("Abrir Anyelo Style QR", self)
        act_open.triggered.connect(self.show_window)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(self.act_scan)
        menu.addAction(act_open)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.scanner.show_menu() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()
        self._refresh_tray_text()

    def _refresh_tray_text(self):
        if self.tray:
            hk = f" ({self.settings.hotkey})" if self.hotkey.active else ""
            self.tray.setToolTip(f"{brand.APP_NAME}{hk}")

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

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
            if not getattr(self, "_told", False):
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
            self.status.setText("Listo")
            on_done(res)

        def bad(msg):
            finish()
            self.status.setText("Algo falló")
            QMessageBox.warning(self, brand.APP_NAME, msg)

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
            QMessageBox.information(self, brand.APP_NAME, "Marca al menos un formato (PNG, SVG o PDF) en el paso 2.")
            return
        style, out, fmts = self.panel.style(), s.out_dir, list(s.fmts)
        dupes, ver, over, after = s.skip_dupes, s.verify, s.overwrite, s.open_after

        def fn(prog):
            return generate_batch(items, out, fmts, style, ver, dupes, over, prog)

        def done(rows):
            table.show_rows(rows)
            ok = sum(r.status == "ok" for r in rows)
            bad = sum(r.status in ("aviso", "error") for r in rows)
            self.status.setText(f"{ok} QR listos" + (f" · {bad} para revisar" if bad else ""))
            if after and (ok or bad):
                open_folder(out)

        self.run_job(fn, done, lock)

    def copy_qr(self, items: list[Item], table: ResultsTable):
        data = None
        row = table.currentRow() if table.isVisible() else -1
        if row >= 0:
            data = table.item(row, 0).data(Qt.UserRole)
        if not data and items:
            data = items[0].data
        if not data:
            QMessageBox.information(self, brand.APP_NAME, "Pega un link primero.")
            return
        try:
            img = render_png(data, self.panel.style())
        except Exception as exc:
            QMessageBox.warning(self, brand.APP_NAME, f"No pude crear ese QR.\n\n{exc}")
            return
        QGuiApplication.clipboard().setImage(pil_to_qimage(img))
        extra = " (el primero de tu lista)" if len(items) > 1 and row < 0 else ""
        self.status.setText(f"QR copiado al portapapeles{extra}: {data[:60]}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(brand.APP_NAME)
    app.setOrganizationName(brand.ORG)
    app.setQuitOnLastWindowClosed(False)
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

    win = MainWindow()
    win.show()
    code = app.exec()
    lock.unlock()
    sys.exit(code)
