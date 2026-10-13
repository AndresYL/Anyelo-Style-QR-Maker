"""Ventana principal (PySide6)."""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QScrollArea, QColorDialog, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import brand
from .core import ERROR_LEVELS, Item, QRStyle, generate_batch, parse_lines, render_png, style_warnings
from .paths import DEFAULT_LOGO, asset
from .reader import is_url, read_paths
from .settings import Settings
from .tabular import guess_columns, items_from_table, read_table, sheet_names

QSS = f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: {brand.TEXT}; }}
QMainWindow, QWidget#root {{ background: {brand.BG}; }}
QTabWidget::pane {{ border: 1px solid {brand.BORDER}; border-radius: 10px; background: {brand.PANEL}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {brand.MUTED}; padding: 9px 18px; margin-right: 2px; border: none; font-weight: 600; }}
QTabBar::tab:selected {{ color: {brand.TEXT}; border-bottom: 2px solid {brand.ACCENT}; }}
QFrame#panel {{ background: {brand.PANEL}; border: 1px solid {brand.BORDER}; border-radius: 10px; }}
QLabel#muted {{ color: {brand.MUTED}; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; }}
QLabel#h2 {{ font-size: 12px; font-weight: 700; color: {brand.MUTED}; letter-spacing: 1px; }}
QPlainTextEdit, QLineEdit, QComboBox, QTableWidget {{
    background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 8px; padding: 6px; selection-background-color: #3A3D41; }}
QComboBox QAbstractItemView {{ background: {brand.PANEL_2}; selection-background-color: #3A3D41; }}
QHeaderView::section {{ background: {brand.PANEL}; color: {brand.MUTED}; border: none; padding: 6px; font-weight: 600; }}
QTableWidget {{ gridline-color: {brand.BORDER}; }}
QPushButton {{ background: {brand.PANEL_2}; border: 1px solid {brand.BORDER}; border-radius: 8px; padding: 8px 14px; font-weight: 600; }}
QPushButton:hover {{ border-color: {brand.MUTED}; }}
QPushButton:disabled {{ color: #5A5E63; }}
QPushButton#primary {{ background: {brand.ACCENT}; color: {brand.ACCENT_TEXT}; border: none; }}
QPushButton#primary:hover {{ background: #E4E4E4; }}
QPushButton#primary:disabled {{ background: #3A3D41; color: #7A7E83; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {brand.MUTED}; background: {brand.PANEL_2}; }}
QCheckBox::indicator:checked {{ background: {brand.ACCENT}; border-color: {brand.ACCENT}; image: url({asset("check.png").as_posix()}); }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {brand.BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {brand.BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {brand.ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QProgressBar {{ background: {brand.PANEL_2}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {brand.ACCENT}; border-radius: 4px; }}
QLabel#drop {{ border: 2px dashed {brand.BORDER}; border-radius: 12px; color: {brand.MUTED}; padding: 26px; }}
QLabel#drop[hover="true"] {{ border-color: {brand.ACCENT}; color: {brand.TEXT}; }}
"""

STATUS_COLOR = {"ok": brand.OK, "aviso": brand.WARN, "error": brand.DANGER, "omitido": brand.MUTED}
STATUS_TEXT = {"ok": "Listo", "aviso": "Revisar", "error": "Error", "omitido": "Omitido"}


# ---------- utilidades ----------

class Job(QThread):
    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(lambda i, n: self.progress.emit(i, n)))
        except Exception as exc:
            self.failed.emit(str(exc))


def pil_to_pixmap(img, size: int) -> QPixmap:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")
    pm = QPixmap()
    pm.loadFromData(buf.getvalue())
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def h2(text: str) -> QLabel:
    lb = QLabel(text.upper())
    lb.setObjectName("h2")
    return lb


def muted(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("muted")
    lb.setWordWrap(True)
    return lb


def open_folder(path: str):
    if path and Path(path).exists():
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class DropZone(QLabel):
    dropped = Signal(list)

    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("drop")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setWordWrap(True)

    def _hover(self, on: bool):
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover(True)

    def dragLeaveEvent(self, e):
        self._hover(False)

    def dropEvent(self, e):
        self._hover(False)
        self.dropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str):
        super().__init__()
        self.color = color
        self.setFixedSize(44, 30)
        self._paint()
        self.clicked.connect(self._pick)

    def _paint(self):
        self.setStyleSheet(f"background:{self.color}; border:1px solid {brand.MUTED}; border-radius:6px;")

    def set_color(self, c: str):
        self.color = c
        self._paint()

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, "Elegir color")
        if c.isValid():
            self.set_color(c.name().upper())
            self.changed.emit(self.color)


class ResultsTable(QTableWidget):
    def __init__(self):
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["Archivo", "Estado", "Detalle"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)

    def show_rows(self, rows):
        self.setRowCount(0)
        for r in rows:
            i = self.rowCount()
            self.insertRow(i)
            detail = r.note or (", ".join(f.suffix.lstrip(".") for f in r.files) if r.files else "")
            for col, txt in enumerate([r.name, STATUS_TEXT[r.status], detail]):
                it = QTableWidgetItem(txt)
                if col == 1:
                    it.setForeground(QColor(STATUS_COLOR[r.status]))
                self.setItem(i, col, it)


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
        self.preview.setMinimumHeight(216)
        self.preview.setMaximumHeight(216)
        v.addWidget(self.preview)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet(f"color:{brand.WARN};")
        v.addWidget(self.warn)

        v.addWidget(h2("Colores"))
        row = QHBoxLayout()
        self.fg = ColorButton(s.fg)
        self.bg = ColorButton(s.bg)
        row.addWidget(QLabel("Código"))
        row.addWidget(self.fg)
        row.addSpacing(10)
        row.addWidget(QLabel("Fondo"))
        row.addWidget(self.bg)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(h2("Logo en el centro"))
        self.logo = QComboBox()
        self.logo.addItems(["Anyelo Style", "Sin logo", "Otro logo…"])
        self.logo.setCurrentIndex({"default": 0, "none": 1, "custom": 2}[s.logo_mode])
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

        v.addWidget(h2("Calidad"))
        r3 = QHBoxLayout()
        self.size = QComboBox()
        self.size.addItem("Pequeño", 8)
        self.size.addItem("Mediano", 12)
        self.size.addItem("Grande", 20)
        self.size.addItem("Muy grande", 32)
        self.size.setCurrentIndex(max(0, self.size.findData(s.scale)))
        self.err = QComboBox()
        for k, label in ERROR_LEVELS.items():
            self.err.addItem(label, k)
        self.err.setCurrentIndex(max(0, self.err.findData(s.error)))
        r3.addWidget(self.size)
        r3.addWidget(self.err)
        v.addLayout(r3)
        v.addWidget(muted("Con logo, la corrección sube sola a Máxima."))

        v.addWidget(h2("Guardar como"))
        r4 = QHBoxLayout()
        self.fmt = {f: QCheckBox(f.upper()) for f in ("png", "svg", "pdf")}
        for f, cb in self.fmt.items():
            cb.setChecked(f in s.fmts)
            r4.addWidget(cb)
        r4.addStretch()
        v.addLayout(r4)

        v.addWidget(h2("Carpeta de destino"))
        r5 = QHBoxLayout()
        self.folder = QLineEdit(s.out_dir)
        self.folder.setPlaceholderText("Elige una carpeta…")
        pick = QPushButton("…")
        pick.setFixedWidth(40)
        pick.setStyleSheet("padding: 8px 0;")
        pick.clicked.connect(self._pick_folder)
        r5.addWidget(self.folder)
        r5.addWidget(pick)
        v.addLayout(r5)

        self.opt_https = QCheckBox("Agregar https:// si falta")
        self.opt_dupes = QCheckBox("Omitir links repetidos")
        self.opt_verify = QCheckBox("Leer de vuelta cada QR creado")
        self.opt_over = QCheckBox("Reemplazar archivos existentes")
        for cb, val in ((self.opt_https, s.add_https), (self.opt_dupes, s.skip_dupes),
                        (self.opt_verify, s.verify), (self.opt_over, s.overwrite)):
            cb.setChecked(val)
            v.addWidget(cb)
        v.addStretch()

        for w in (self.fg, self.bg):
            w.changed.connect(self._on_change)
        self.logo.currentIndexChanged.connect(self._on_logo)
        self.ratio.valueChanged.connect(self._on_change)
        for w in (self.size, self.err):
            w.currentIndexChanged.connect(self._on_change)
        for cb in [*self.fmt.values(), self.opt_https, self.opt_dupes, self.opt_verify, self.opt_over]:
            cb.toggled.connect(self._on_change)
        self.folder.textChanged.connect(self._on_change)
        self.refresh()

    # --- lectura del estado ---
    def logo_file(self) -> str | None:
        i = self.logo.currentIndex()
        if i == 0:
            return str(DEFAULT_LOGO)
        if i == 2 and self.s.logo_custom and Path(self.s.logo_custom).exists():
            return self.s.logo_custom
        return None

    def style(self) -> QRStyle:
        return QRStyle(fg=self.fg.color, bg=self.bg.color, scale=self.size.currentData(),
                       error=self.err.currentData(), logo=self.logo_file(), logo_ratio=self.ratio.value() / 100)

    def fmts(self) -> list[str]:
        return [f for f, cb in self.fmt.items() if cb.isChecked()]

    def out_dir(self) -> str:
        return self.folder.text().strip()

    # --- acciones ---
    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino", self.out_dir() or str(Path.home()))
        if d:
            self.folder.setText(d)

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
        s.scale, s.error = self.size.currentData(), self.err.currentData()
        s.logo_mode = ["default", "none", "custom"][self.logo.currentIndex()]
        s.logo_ratio = self.ratio.value() / 100
        s.fmts = self.fmts()
        s.out_dir = self.out_dir()
        s.add_https, s.skip_dupes = self.opt_https.isChecked(), self.opt_dupes.isChecked()
        s.verify, s.overwrite = self.opt_verify.isChecked(), self.opt_over.isChecked()
        s.save()
        self.refresh()
        self.changed.emit()

    def set_sample(self, text: str):
        self.sample = text or "https://anyelostyle.com"
        self.refresh()

    def refresh(self):
        st = self.style()
        try:
            self.preview.setPixmap(pil_to_pixmap(render_png(self.sample, st), 210))
        except Exception:
            self.preview.setText("Texto demasiado largo para esta vista previa")
        self.warn.setText("\n".join(style_warnings(st)))


# ---------- pestañas ----------

class GenerateTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.addWidget(muted("Un link por línea. Si quieres ponerle nombre al archivo, escribe «Nombre | link». "
                          "También puedes pegar dos columnas desde Excel."))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("https://anyelostyle.com\nPromo otoño | anyelostyle.com/otono?utm_source=ig\n…")
        v.addWidget(self.text, 3)
        row = QHBoxLayout()
        self.btn = QPushButton("Generar QR")
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.generate)
        self.open_btn = QPushButton("Abrir carpeta")
        self.open_btn.clicked.connect(lambda: open_folder(self.win.panel.out_dir()))
        self.count = muted("")
        row.addWidget(self.btn)
        row.addWidget(self.open_btn)
        row.addWidget(self.count, 1)
        v.addLayout(row)
        self.table = ResultsTable()
        v.addWidget(self.table, 2)

        self._timer = QTimer(singleShot=True, interval=300)
        self._timer.timeout.connect(self._sample)
        self.text.textChanged.connect(self._timer.start)
        win.panel.changed.connect(self._sample)

    def _items(self) -> list[Item]:
        return parse_lines(self.text.toPlainText(), self.win.panel.opt_https.isChecked())

    def _sample(self):
        items = self._items()
        n = len(items)
        self.count.setText(f"{n} QR en la lista" if n else "")
        self.win.panel.set_sample(items[0].data if items else "")

    def generate(self):
        items = self._items()
        if not items:
            QMessageBox.information(self, brand.APP_NAME, "Pega al menos un link.")
            return
        self.win.run_batch(items, self.table, [self.btn])


class ExcelTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.path = ""
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.addWidget(muted("Carga un Excel (.xlsx) o un CSV y dile cuál columna es el nombre y cuál es el link. "
                          "Si tu lista está en Google Sheets, descárgala como Excel o CSV."))
        top = QHBoxLayout()
        self.pick = QPushButton("Elegir archivo…")
        self.pick.clicked.connect(self.choose)
        self.file_lbl = muted("Ningún archivo cargado")
        self.sheet = QComboBox()
        self.sheet.setVisible(False)
        self.sheet.currentTextChanged.connect(self._sheet_changed)
        top.addWidget(self.pick)
        top.addWidget(self.file_lbl, 1)
        top.addWidget(self.sheet)
        v.addLayout(top)

        cols = QHBoxLayout()
        self.name_col = QComboBox()
        self.data_col = QComboBox()
        cols.addWidget(QLabel("Nombre del archivo:"))
        cols.addWidget(self.name_col, 1)
        cols.addSpacing(12)
        cols.addWidget(QLabel("Link o dato del QR:"))
        cols.addWidget(self.data_col, 1)
        v.addLayout(cols)

        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.verticalHeader().setVisible(False)
        v.addWidget(self.preview, 2)

        row = QHBoxLayout()
        self.btn = QPushButton("Generar un QR por fila")
        self.btn.setObjectName("primary")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.generate)
        self.open_btn = QPushButton("Abrir carpeta")
        self.open_btn.clicked.connect(lambda: open_folder(self.win.panel.out_dir()))
        row.addWidget(self.btn)
        row.addWidget(self.open_btn)
        row.addStretch()
        v.addLayout(row)
        self.table = ResultsTable()
        v.addWidget(self.table, 2)
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
                                self.win.panel.opt_https.isChecked())

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
        v.setContentsMargins(16, 16, 16, 16)
        self.drop = DropZone("Arrastra aquí imágenes, PDFs o carpetas con códigos QR")
        self.drop.dropped.connect(self.read)
        v.addWidget(self.drop, 1)
        row = QHBoxLayout()
        b1 = QPushButton("Elegir archivos…")
        b1.clicked.connect(self.pick_files)
        b2 = QPushButton("Elegir carpeta…")
        b2.clicked.connect(self.pick_folder)
        row.addWidget(b1)
        row.addWidget(b2)
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


# ---------- ventana ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(brand.APP_NAME)
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)
        self._job: Job | None = None
        self.settings = Settings.load()

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
        ver = QLabel(f"v{brand.VERSION} · funciona sin internet")
        ver.setObjectName("muted")
        head.addWidget(ver)
        outer.addLayout(head)

        body = QHBoxLayout()
        self.panel = StylePanel(self.settings)
        self.tabs = QTabWidget()
        self.tabs.addTab(GenerateTab(self), "Generar")
        self.tabs.addTab(ExcelTab(self), "Excel / CSV")
        self.tabs.addTab(ReadTab(self), "Leer QR")
        scroll = QScrollArea()
        scroll.setWidget(self.panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(322)
        body.addWidget(self.tabs, 1)
        body.addWidget(scroll)
        outer.addLayout(body, 1)

        foot = QHBoxLayout()
        self.status = muted("Listo")
        self.bar = QProgressBar()
        self.bar.setFixedWidth(220)
        self.bar.setVisible(False)
        foot.addWidget(self.status, 1)
        foot.addWidget(self.bar)
        outer.addLayout(foot)

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
        p = self.panel
        if not p.out_dir():
            p._pick_folder()
            if not p.out_dir():
                return
        fmts = p.fmts()
        if not fmts:
            QMessageBox.information(self, brand.APP_NAME, "Marca al menos un formato (PNG, SVG o PDF).")
            return
        style, out = p.style(), p.out_dir()
        dupes, ver, over = p.opt_dupes.isChecked(), p.opt_verify.isChecked(), p.opt_over.isChecked()

        def fn(prog):
            return generate_batch(items, out, fmts, style, ver, dupes, over, prog)

        def done(rows):
            table.show_rows(rows)
            ok = sum(r.status == "ok" for r in rows)
            bad = sum(r.status in ("aviso", "error") for r in rows)
            self.status.setText(f"{ok} QR listos" + (f" · {bad} para revisar" if bad else ""))

        self.run_job(fn, done, lock)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(brand.APP_NAME)
    app.setOrganizationName(brand.ORG)
    app.setStyleSheet(QSS)
    icon = asset("icon.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
