"""Componentes reutilizables: tareas en segundo plano, selector de color, tarjetas de paso, tablas."""
from __future__ import annotations

import colorsys
import io
import re
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QThread, Qt, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRegularExpressionValidator)
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import brand

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


def pil_to_qimage(img) -> QImage:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG")
    return QImage.fromData(buf.getvalue(), "PNG")


def pil_to_pixmap(img, size: int) -> QPixmap:
    pm = QPixmap.fromImage(pil_to_qimage(img))
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def qimage_to_pil(qimg: QImage):
    from PIL import Image
    q = qimg.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes("RGBA", (q.width(), q.height()), bytes(q.constBits()))


def h2(text: str) -> QLabel:
    lb = QLabel(text.upper())
    lb.setObjectName("h2")
    return lb


def muted(text: str = "") -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("muted")
    lb.setWordWrap(True)
    return lb


def open_folder(path: str):
    if path and Path(path).exists():
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def scrolled(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.viewport().setObjectName("scrollViewport")
    widget.setObjectName("scrollPage")
    sa.setWidget(widget)
    return sa


# ---------- selector de color ----------

class SVBox(QWidget):
    changed = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v = 0.0, 1.0, 1.0
        self.setFixedSize(270, 170)
        self.setCursor(Qt.CrossCursor)

    def set_state(self, h, s, v):
        self.h, self.s, self.v = h, s, v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        p.setClipPath(path)
        g1 = QLinearGradient(0, 0, r.width(), 0)
        g1.setColorAt(0, QColor(255, 255, 255))
        g1.setColorAt(1, QColor.fromHsvF(min(self.h, 0.999), 1, 1))
        p.fillRect(r, g1)
        g2 = QLinearGradient(0, 0, 0, r.height())
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, g2)
        p.setClipping(False)
        pt = QPointF(self.s * r.width(), (1 - self.v) * r.height())
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 170), 1))
        p.drawEllipse(pt, 9, 9)
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(pt, 7, 7)

    def _pick(self, pos):
        s = min(max(pos.x() / self.width(), 0), 1)
        v = 1 - min(max(pos.y() / self.height(), 0), 1)
        self.s, self.v = s, v
        self.update()
        self.changed.emit(s, v)

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        self._pick(e.position())


class HueBar(QWidget):
    changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.h = 0.0
        self.setFixedSize(270, 16)
        self.setCursor(Qt.PointingHandCursor)

    def set_hue(self, h):
        self.h = h
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), 0)
        for i in range(7):
            g.setColorAt(i / 6, QColor.fromHsvF(min(i / 6, 0.999), 1, 1))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        x = self.h * self.width()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 170), 1))
        p.drawEllipse(QPointF(x, 8), 9, 9)
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(QPointF(x, 8), 7, 7)

    def _pick(self, pos):
        self.h = min(max(pos.x() / self.width(), 0), 1)
        self.update()
        self.changed.emit(self.h)

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        self._pick(e.position())


PRESETS = ["#000000", "#FFFFFF", "#111111", "#1B2A6B", "#0B6E4F", "#B00020", "#D4AF37", "#7A3EF0"]


class ColorPickerDialog(QDialog):
    """Selector de color propio: se ve bien con el tema oscuro y muestra el QR en vivo."""
    colorChanged = Signal(str)

    def __init__(self, color: str, title: str, preview_fn=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.preview_fn = preview_fn
        self.original = color
        c = QColor(color)
        self.h = max(c.hsvHueF(), 0.0)
        self.s, self.v = c.hsvSaturationF(), c.valueF()

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(10)
        self.sv = SVBox()
        self.hue = HueBar()
        left.addWidget(self.sv)
        left.addWidget(self.hue)

        row = QHBoxLayout()
        self.hex = QLineEdit()
        self.hex.setMaxLength(7)
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.hex.setFixedWidth(100)
        self.swatch_new = QLabel()
        self.swatch_old = QLabel()
        for sw in (self.swatch_new, self.swatch_old):
            sw.setFixedSize(34, 34)
        self.swatch_old.setStyleSheet(f"background:{color}; border:1px solid {brand.MUTED}; border-radius:8px;")
        row.addWidget(QLabel("Hex"))
        row.addWidget(self.hex)
        row.addStretch()
        row.addWidget(self.swatch_old)
        row.addWidget(self.swatch_new)
        left.addLayout(row)

        pr = QHBoxLayout()
        pr.setSpacing(6)
        for hx in PRESETS:
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setStyleSheet(f"background:{hx}; border:1px solid {brand.MUTED}; border-radius:13px; padding:0;")
            b.clicked.connect(lambda _=False, hx=hx: self.set_hex(hx))
            pr.addWidget(b)
        pr.addStretch()
        left.addLayout(pr)
        root.addLayout(left)

        right = QVBoxLayout()
        right.addWidget(QLabel("Así se ve tu QR"), alignment=Qt.AlignHCenter)
        self.pv = QLabel(alignment=Qt.AlignCenter)
        self.pv.setFixedSize(190, 190)
        right.addWidget(self.pv)
        right.addStretch()
        ok = QPushButton("Aceptar")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        right.addWidget(ok)
        right.addWidget(cancel)
        root.addLayout(right)

        self.sv.changed.connect(self._sv)
        self.hue.changed.connect(self._hue)
        self.hex.textEdited.connect(self._hex_edited)
        self._sync(emit=False)

    @property
    def color(self) -> str:
        return QColor.fromHsvF(min(self.h, 0.999), self.s, self.v).name().upper()

    def _sv(self, s, v):
        self.s, self.v = s, v
        self._sync()

    def _hue(self, h):
        self.h = h
        self._sync()

    def set_hex(self, hx: str):
        c = QColor(hx)
        if c.isValid():
            if c.hsvSaturationF() > 0:
                self.h = c.hsvHueF()
            self.s, self.v = c.hsvSaturationF(), c.valueF()
            self._sync()

    def _hex_edited(self, text: str):
        t = text if text.startswith("#") else "#" + text
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", t):
            c = QColor(t)
            if c.hsvSaturationF() > 0:
                self.h = c.hsvHueF()
            self.s, self.v = c.hsvSaturationF(), c.valueF()
            self._sync(update_hex=False)

    def _sync(self, emit=True, update_hex=True):
        self.sv.set_state(self.h, self.s, self.v)
        self.hue.set_hue(self.h)
        col = self.color
        if update_hex:
            self.hex.setText(col)
        self.swatch_new.setStyleSheet(f"background:{col}; border:1px solid {brand.MUTED}; border-radius:8px;")
        if self.preview_fn:
            try:
                self.pv.setPixmap(pil_to_pixmap(self.preview_fn(col), 186))
            except Exception:
                self.pv.clear()
        if emit:
            self.colorChanged.emit(col)


class ColorButton(QPushButton):
    changed = Signal(str)     # color definitivo (al aceptar)
    live = Signal(str)        # color provisional mientras se mueve el selector

    def __init__(self, color: str, title: str = "Elegir color", preview_fn=None):
        super().__init__()
        self.color = color
        self.title = title
        self.preview_fn = preview_fn
        self.setFixedSize(46, 30)
        self._paint()
        self.clicked.connect(self._pick)

    def _paint(self):
        self.setStyleSheet(f"background:{self.color}; border:1px solid {brand.MUTED}; border-radius:7px; padding:0;")

    def set_color(self, c: str):
        self.color = c
        self._paint()

    def _pick(self):
        old = self.color
        dlg = ColorPickerDialog(old, self.title, self.preview_fn, self.window())
        dlg.colorChanged.connect(lambda c: (self.set_color(c), self.live.emit(c)))
        if dlg.exec():
            self.set_color(dlg.color)
            self.changed.emit(self.color)
        else:
            self.set_color(old)
            self.live.emit(old)


# ---------- tarjetas de paso ----------

class StepCard(QFrame):
    def __init__(self, number: int, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("step")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 16)
        v.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(12)
        badge = QLabel(str(number))
        badge.setObjectName("badge")
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)
        tl = QVBoxLayout()
        tl.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("stepTitle")
        tl.addWidget(t)
        if subtitle:
            tl.addWidget(muted(subtitle))
        head.addWidget(badge, alignment=Qt.AlignTop)
        head.addLayout(tl, 1)
        v.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        v.addLayout(self.body)


class DestinationCard(StepCard):
    """Paso 'Elige el destino'. Cada pestaña tiene el suyo y todos comparten los mismos ajustes."""
    changed = Signal()

    def __init__(self, s, number: int = 2):
        super().__init__(number, "Elige el destino", "Aquí se guardan los QR que crees.")
        self.s = s
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Elige una carpeta…")
        self.pick = QPushButton("Elegir carpeta…")
        self.pick.clicked.connect(self._pick)
        row.addWidget(self.folder, 1)
        row.addWidget(self.pick)
        self.body.addLayout(row)

        fr = QHBoxLayout()
        fr.addWidget(QLabel("Formatos:"))
        self.fmt = {f: QCheckBox(f.upper()) for f in ("png", "svg", "pdf")}
        for cb in self.fmt.values():
            fr.addWidget(cb)
            cb.toggled.connect(self._edited)
        fr.addStretch()
        self.body.addLayout(fr)
        self.open_after = QCheckBox("Abrir la carpeta cuando termine")
        self.open_after.toggled.connect(self._edited)
        self.body.addWidget(self.open_after)
        self.folder.textEdited.connect(self._edited)
        self.load()

    def load(self):
        s = self.s
        for w in (self.folder, self.open_after, *self.fmt.values()):
            w.blockSignals(True)
        self.folder.setText(s.out_dir)
        self.open_after.setChecked(s.open_after)
        for f, cb in self.fmt.items():
            cb.setChecked(f in s.fmts)
        for w in (self.folder, self.open_after, *self.fmt.values()):
            w.blockSignals(False)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino", self.s.out_dir or str(Path.home()))
        if d:
            self.folder.setText(d)
            self._edited()

    def _edited(self, *_):
        s = self.s
        s.out_dir = self.folder.text().strip()
        s.fmts = [f for f, cb in self.fmt.items() if cb.isChecked()]
        s.open_after = self.open_after.isChecked()
        s.save()
        self.changed.emit()


# ---------- tabla de resultados ----------

class ResultsTable(QTableWidget):
    def __init__(self):
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["Archivo", "Estado", "Detalle"])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setMinimumHeight(150)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        self.setVisible(False)

    def show_rows(self, rows):
        self.setRowCount(0)
        for r in rows:
            i = self.rowCount()
            self.insertRow(i)
            detail = r.note or (", ".join(f.suffix.lstrip(".") for f in r.files) if r.files else "")
            for col, txt in enumerate([r.name, STATUS_TEXT[r.status], detail]):
                it = QTableWidgetItem(txt)
                if col == 0:
                    it.setData(Qt.UserRole, r.data)
                if col == 1:
                    it.setForeground(QColor(STATUS_COLOR[r.status]))
                self.setItem(i, col, it)
        self.setVisible(bool(rows))


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
