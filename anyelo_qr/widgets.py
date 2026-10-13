"""Componentes visuales del programa, en el mismo lenguaje que la página de Anyelo Style."""
from __future__ import annotations

import io
import re
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRect, QRectF, QRegularExpression, QSize,
                            Qt, QThread, QTimer, QUrl, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRegularExpressionValidator)
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import brand
from .fonts import family, font
from .hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, format_hotkey, parse_hotkey

STATUS_COLOR = {"ok": brand.GOLD, "aviso": brand.RED_L, "error": brand.RED, "omitido": brand.MUTED}
STATUS_TEXT = {"ok": "Listo", "aviso": "Revisar", "error": "Error", "omitido": "Omitido"}


def _mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() + (cb.red() - ca.red()) * t), int(ca.green() + (cb.green() - ca.green()) * t),
                  int(ca.blue() + (cb.blue() - ca.blue()) * t))


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


# ---------- texto ----------

def eyebrow(text: str, color: str = brand.GOLD, px: int = 11) -> QLabel:
    lb = QLabel(text.upper())
    lb.setFont(font("semibold", px, 1.3))
    lb.setStyleSheet(f"color:{color};")
    return lb


def h2(text: str) -> QLabel:
    return eyebrow(text, brand.MUTED, 11)


def muted(text: str = "", px: int = 13) -> QLabel:
    lb = QLabel(text)
    lb.setFont(font("regular", px))
    lb.setStyleSheet(f"color:{brand.MUTED};")
    lb.setWordWrap(True)
    return lb


def headline(plain: str, em: str = "", tail: str = "", px: int = 32) -> QLabel:
    """Título como los de la página: pesado, con una palabra en regular y dorado."""
    xb, rg = family("xbold"), family("regular")
    html = f'<span style="font-family:\'{xb}\'">{plain}</span>'
    if em:
        html += f' <span style="font-family:\'{rg}\'; color:{brand.GOLD}">{em}</span>'
    if tail:
        sep = "" if tail[0] in "?!.,;:" else " "
        html += f'{sep}<span style="font-family:\'{xb}\'">{tail}</span>'
    lb = QLabel(html)
    f = font("xbold", px)
    f.setLetterSpacing(QFont.PercentageSpacing, 97)
    lb.setFont(f)
    lb.setStyleSheet(f"color:{brand.BONE};")
    lb.setTextFormat(Qt.RichText)
    return lb


def section(title: str) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 8, 0, 0)
    h.setSpacing(10)
    h.addWidget(h2(title))
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{brand.LINE};")
    h.addWidget(line, 1)
    return w


# ---------- botones ----------

class CtaButton(QPushButton):
    """El botón rojo de la página: sombra dura crema, se hunde al pulsarlo y se invierte al pasar el cursor."""
    OFF = 6

    def __init__(self, text: str, arrow: bool = True):
        super().__init__(text.upper())
        self.arrow = arrow
        self._h = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.valueChanged.connect(self._set_h)
        self.setFont(font("bold", 14, 1.0))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setFlat(True)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def _go(self, to: float):
        self._anim.stop()
        self._anim.setStartValue(self._h)
        self._anim.setEndValue(to)
        self._anim.start()

    def enterEvent(self, e):
        self._go(1.0)

    def leaveEvent(self, e):
        self._go(0.0)

    def sizeHint(self):
        w = QFontMetrics(self.font()).horizontalAdvance(self.text()) + 56 + (30 if self.arrow else 0)
        return QSize(w + self.OFF, 52 + self.OFF)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off = self.OFF
        W, H = self.width() - off, self.height() - off
        on = self.isEnabled()
        h = self._h if on else 0.0
        body_bg = _mix(brand.RED, brand.BONE, h) if on else QColor(brand.PANEL_2)
        shadow = _mix(brand.CREAM, brand.RED, h) if on else QColor(brand.LINE)
        fg = _mix(brand.CREAM, brand.INK, h) if on else QColor(brand.MUTED)
        shift = 4 if (self.isDown() and on) else 0
        p.fillRect(QRect(off, off, W, H), shadow)
        body = QRect(shift, shift, W, H)
        p.fillRect(body, body_bg)
        if self.hasFocus():
            p.setPen(QPen(QColor(brand.GOLD), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(body.adjusted(-3, -3, 3, 3))
        p.setFont(self.font())
        p.setPen(fg)
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(self.text())
        total = tw + (30 if self.arrow else 0)
        x = body.x() + (W - total) // 2
        p.drawText(QRect(x, body.y(), tw + 2, H), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if self.arrow:
            ax, ay = x + tw + 12, body.y() + H // 2
            pen = QPen(fg, 2)
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawLine(ax, ay, ax + 14, ay)
            p.drawLine(ax + 8, ay - 5, ax + 14, ay)
            p.drawLine(ax + 8, ay + 5, ax + 14, ay)


class Pill(QPushButton):
    """Botón secundario: contorno fino, mayúsculas, se rellena de hueso al pasar el cursor."""

    def __init__(self, text: str = ""):
        super().__init__(text.upper())
        self.setObjectName("pill")
        self.setFont(font("semibold", 12, 0.8))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)

    def setText(self, text: str):
        super().setText(text.upper())


class LinkButton(QPushButton):
    def __init__(self, text: str = ""):
        super().__init__(text.upper())
        self.setObjectName("link")
        self.setFont(font("semibold", 12, 0.8))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setFlat(True)

    def setText(self, text: str):
        super().setText(text.upper())


class NavButton(QPushButton):
    """Entrada del riel lateral: número, nombre y marcador dorado, como el riel de escenas de la página."""

    def __init__(self, number: str, label: str):
        super().__init__()
        self.number, self.label = number, label.upper()
        self._h = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.valueChanged.connect(lambda v: (setattr(self, "_h", float(v)), self.update()))
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setFixedHeight(44)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._h)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._h)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        if on:
            p.fillRect(self.rect(), QColor(255, 255, 255, 10))
            p.fillRect(0, (self.height() - 20) // 2, 3, 20, QColor(brand.GOLD))
        elif self._h > 0:
            p.fillRect(self.rect(), QColor(255, 255, 255, int(6 * self._h)))
        txt = QColor(brand.GOLD) if on else _mix(brand.MUTED, brand.BONE, self._h)
        num = QColor(brand.GOLD) if on else _mix(brand.MUTED, brand.RED_L, 0.0 + self._h * 0.6)
        p.setFont(font("semibold", 12, 1.0))
        p.setPen(num)
        p.drawText(QRect(22, 0, 30, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.number)
        p.setFont(font("semibold", 13, 1.1))
        p.setPen(txt)
        p.drawText(QRect(56, 0, self.width() - 60, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.label)


# ---------- tarjetas ----------

class CreamCard(QFrame):
    """Tarjeta crema con borde negro y sombra dura roja, como las del sitio. Aloja la vista previa del QR."""
    OFF = 8

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 14, 14 + self.OFF, 14 + self.OFF)

    def paintEvent(self, _):
        p = QPainter(self)
        off = self.OFF
        W, H = self.width() - off, self.height() - off
        p.fillRect(QRect(off, off, W, H), QColor(brand.RED))
        p.fillRect(QRect(0, 0, W, H), QColor(brand.CREAM))
        p.setPen(QPen(QColor("#111111"), 3))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRect(1, 1, W - 2, H - 2))


class StepCard(QFrame):
    def __init__(self, number: int, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("step")
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 20)
        v.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(14)
        n = QLabel(f"{number:02d}")
        n.setFont(font("semibold", 13, 1.0))
        n.setStyleSheet(f"color:{brand.RED_L};")
        n.setFixedSize(26, 26)
        n.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        tl = QVBoxLayout()
        tl.setSpacing(1)
        t = QLabel(title)
        t.setFont(font("xbold", 19, -0.3))
        t.setStyleSheet(f"color:{brand.BONE};")
        tl.addWidget(t)
        if subtitle:
            tl.addWidget(muted(subtitle, 13))
        head.addWidget(n, alignment=Qt.AlignTop)
        head.addLayout(tl, 1)
        v.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        v.addLayout(self.body)


class DestinationCard(QFrame):
    """Paso 'Destino', pensado para pasar rápido: dos renglones. Cada pestaña tiene el suyo, todos comparten ajustes."""
    changed = Signal()

    def __init__(self, s, number: int = 2):
        super().__init__()
        self.setObjectName("step")
        self.s = s
        row = QHBoxLayout(self)
        row.setContentsMargins(22, 14, 22, 14)
        row.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(0)
        n = QLabel(f"{number:02d}")
        n.setFont(font("semibold", 13, 1.0))
        n.setStyleSheet(f"color:{brand.RED_L};")
        t = QLabel("Destino")
        t.setFont(font("xbold", 19, -0.3))
        t.setStyleSheet(f"color:{brand.BONE};")
        left.addWidget(n)
        left.addWidget(t)
        left.addStretch()
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(92)
        row.addWidget(left_w)

        right = QVBoxLayout()
        right.setSpacing(8)
        r1 = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Elige la carpeta donde se guardan tus QR")
        self.pick = Pill("Elegir")
        self.pick.clicked.connect(self._pick)
        r1.addWidget(self.folder, 1)
        r1.addWidget(self.pick)
        right.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(14)
        self.fmt = {f: QCheckBox(f.upper()) for f in ("png", "svg", "pdf")}
        for cb in self.fmt.values():
            cb.setFont(font("semibold", 12, 0.6))
            r2.addWidget(cb)
            cb.toggled.connect(self._edited)
        r2.addSpacing(10)
        self.open_after = QCheckBox("Abrir la carpeta al terminar")
        self.open_after.toggled.connect(self._edited)
        r2.addWidget(self.open_after)
        r2.addStretch()
        right.addLayout(r2)
        row.addLayout(right, 1)
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


# ---------- tablas ----------

def style_table(t: QTableWidget):
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(36)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    t.setFrameShape(QFrame.NoFrame)
    t.horizontalHeader().setFont(font("semibold", 11, 1.0))
    t.horizontalHeader().setHighlightSections(False)
    t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    t.setFont(font("regular", 13))


class ResultsTable(QTableWidget):
    def __init__(self):
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["ARCHIVO", "ESTADO", "DETALLE"])
        style_table(self)
        self.setMinimumHeight(160)
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
                    it.setFont(font("semibold", 12, 0.6))
                self.setItem(i, col, it)
        self.setVisible(bool(rows))


class DropZone(QFrame):
    dropped = Signal(list)

    def __init__(self, title: str, sub: str):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 34, 24, 34)
        v.setSpacing(6)
        t = QLabel(title)
        t.setFont(font("xbold", 24, -0.4))
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color:{brand.BONE};")
        v.addWidget(t)
        s = muted(sub, 13)
        s.setAlignment(Qt.AlignCenter)
        v.addWidget(s)

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


# ---------- navegación ----------

class Pages(QStackedWidget):
    """Páginas con una entrada suave (fundido corto)."""

    def _fade(self, w):
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", w)
        a.setDuration(200)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.finished.connect(lambda: w.setGraphicsEffect(None))
        a.start()
        self._anim = a

    def setCurrentIndex(self, i: int):
        if i == self.currentIndex():
            return
        super().setCurrentIndex(i)
        self._fade(self.widget(i))

    def setCurrentWidget(self, w):
        self.setCurrentIndex(self.indexOf(w))


class Toast(QLabel):
    """Aviso corto flotante: confirma sin interrumpir con ventanas."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFont(font("semibold", 13))
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._timer = QTimer(self, singleShot=True, interval=2800)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def reposition(self):
        p = self.parentWidget()
        if p:
            self.move((p.width() - self.width()) // 2, p.height() - self.height() - 30)

    def show_message(self, text: str, kind: str = "ok"):
        color = brand.GOLD if kind == "ok" else brand.RED_L
        self.setStyleSheet(f"background:{brand.INK}; color:{brand.BONE}; border:1px solid {color}; padding:12px 22px;")
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setDuration(180)
        self._anim.setStartValue(self._eff.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start()

    def _fade_out(self):
        self._anim.stop()
        self._anim.setDuration(320)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._hide_once)
        self._anim.start()

    def _hide_once(self):
        try:
            self._anim.finished.disconnect(self._hide_once)
        except (TypeError, RuntimeError):
            pass
        if self._eff.opacity() < 0.05:
            self.hide()


# ---------- grabador de atajo ----------

_QT_MODS = ((Qt.ControlModifier, MOD_CONTROL), (Qt.AltModifier, MOD_ALT), (Qt.ShiftModifier, MOD_SHIFT),
            (Qt.MetaModifier, MOD_WIN))


class HotkeyRecorder(QPushButton):
    """Campo que graba una combinación leyendo la tecla física (no el carácter que escribe).
    Así Ctrl+Alt+Q se graba como Q aunque el teclado la convierta en «@» (AltGr)."""
    committed = Signal(str)
    recordingChanged = Signal(bool)
    rejected = Signal(str)

    def __init__(self, value: str):
        super().__init__()
        self.setObjectName("recorder")
        self.value = value
        self._rec = False
        self.setFont(font("bold", 15, 1.0))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(360, 48)
        self.clicked.connect(self.start)
        self._refresh()

    def _refresh(self, live: str = ""):
        if self._rec:
            self.setText((live or "Presiona tu combinación…").upper() if live else "PRESIONA TU COMBINACIÓN…")
        else:
            self.setText(self.value.upper().replace("+", "  +  "))
        self.setProperty("recording", self._rec)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_value(self, v: str):
        self.value = v
        self._refresh()

    def start(self):
        if self._rec:
            return
        self._rec = True
        self.setFocus()
        self._refresh()
        self.recordingChanged.emit(True)

    def stop(self):
        if not self._rec:
            return
        self._rec = False
        self._refresh()
        self.recordingChanged.emit(False)

    def _mods(self, e) -> int:
        m = e.modifiers()
        return sum(win for qt, win in _QT_MODS if m & qt)

    @staticmethod
    def _vk(e) -> int:
        vk = e.nativeVirtualKey()
        if vk:
            return int(vk)
        k = e.key()                                   # otras plataformas: sacar el código de la tecla de Qt
        if Qt.Key_A <= k <= Qt.Key_Z or Qt.Key_0 <= k <= Qt.Key_9:
            return int(k)
        if Qt.Key_F1 <= k <= Qt.Key_F12:
            return 0x70 + int(k - Qt.Key_F1)
        return 0

    def event(self, e):
        if self._rec and e.type() == QEvent.ShortcutOverride:
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        if not self._rec:
            super().keyPressEvent(e)
            return
        if e.isAutoRepeat():
            return
        if e.key() == Qt.Key_Escape:
            self.stop()
            return
        if e.key() in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            parts = [n for n, f in (("Ctrl", MOD_CONTROL), ("Alt", MOD_ALT), ("Shift", MOD_SHIFT), ("Win", MOD_WIN))
                     if self._mods(e) & f]
            self._refresh("+".join(parts) + "+…" if parts else "")
            return
        try:
            text = format_hotkey(self._mods(e), self._vk(e))
            parse_hotkey(text)
        except ValueError as exc:
            self.rejected.emit(str(exc))
            return
        self.value = text
        self._rec = False
        self._refresh()
        self.recordingChanged.emit(False)
        self.committed.emit(text)

    def focusOutEvent(self, e):
        self.stop()
        super().focusOutEvent(e)


# ---------- selector de color ----------

class SVBox(QWidget):
    changed = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v = 0.0, 1.0, 1.0
        self.setFixedSize(280, 176)
        self.setCursor(Qt.CrossCursor)

    def set_state(self, h, s, v):
        self.h, self.s, self.v = h, s, v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        g1 = QLinearGradient(0, 0, r.width(), 0)
        g1.setColorAt(0, QColor(255, 255, 255))
        g1.setColorAt(1, QColor.fromHsvF(min(self.h, 0.999), 1, 1))
        p.fillRect(r, g1)
        g2 = QLinearGradient(0, 0, 0, r.height())
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, g2)
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
        self.setFixedSize(280, 14)
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
        p.fillRect(self.rect(), g)
        x = self.h * self.width()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 170), 1))
        p.drawEllipse(QPointF(x, 7), 9, 9)
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(QPointF(x, 7), 7, 7)

    def _pick(self, pos):
        self.h = min(max(pos.x() / self.width(), 0), 1)
        self.update()
        self.changed.emit(self.h)

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        self._pick(e.position())


PRESETS = ["#000000", "#FFFFFF", "#070707", "#EBE5CE", "#C0392B", "#D4AF37", "#1B2A6B", "#0B6E4F"]


class ColorPickerDialog(QDialog):
    """Selector propio: oscuro, con el QR en vivo mientras mueves el color."""
    colorChanged = Signal(str)

    def __init__(self, color: str, title: str, preview_fn=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.preview_fn = preview_fn
        c = QColor(color)
        self.h = max(c.hsvHueF(), 0.0)
        self.s, self.v = c.hsvSaturationF(), c.valueF()

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(eyebrow(title))
        self.sv = SVBox()
        self.hue = HueBar()
        left.addWidget(self.sv)
        left.addWidget(self.hue)

        row = QHBoxLayout()
        self.hex = QLineEdit()
        self.hex.setMaxLength(7)
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.hex.setFixedWidth(110)
        self.hex.setFont(font("semibold", 14, 0.8))
        self.swatch_old = QLabel()
        self.swatch_new = QLabel()
        for sw in (self.swatch_old, self.swatch_new):
            sw.setFixedSize(34, 34)
        self.swatch_old.setStyleSheet(f"background:{color}; border:1px solid {brand.LINE_2};")
        row.addWidget(self.hex)
        row.addStretch()
        row.addWidget(self.swatch_old)
        row.addWidget(self.swatch_new)
        left.addLayout(row)

        pr = QHBoxLayout()
        pr.setSpacing(7)
        for hx in PRESETS:
            b = QPushButton()
            b.setFixedSize(24, 24)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"background:{hx}; border:1px solid {brand.MUTED}; border-radius:12px; padding:0; min-height:0;")
            b.clicked.connect(lambda _=False, hx=hx: self.set_hex(hx))
            pr.addWidget(b)
        pr.addStretch()
        left.addLayout(pr)
        root.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(eyebrow("Así se ve tu QR", brand.MUTED), alignment=Qt.AlignHCenter)
        card = CreamCard()
        self.pv = QLabel(alignment=Qt.AlignCenter)
        self.pv.setFixedSize(170, 170)
        card.lay.addWidget(self.pv)
        right.addWidget(card, alignment=Qt.AlignHCenter)
        right.addStretch()
        ok = CtaButton("Aceptar", arrow=False)
        ok.clicked.connect(self.accept)
        cancel = Pill("Cancelar")
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
        self.swatch_new.setStyleSheet(f"background:{col}; border:1px solid {brand.LINE_2};")
        if self.preview_fn:
            try:
                self.pv.setPixmap(pil_to_pixmap(self.preview_fn(col), 166))
            except Exception:
                self.pv.clear()
        if emit:
            self.colorChanged.emit(col)


class ColorButton(QPushButton):
    """Muestra circular con aro, como los recortes de la portada."""
    changed = Signal(str)     # color definitivo (al aceptar)
    live = Signal(str)        # color provisional mientras se mueve el selector

    def __init__(self, color: str, title: str = "Elegir color", preview_fn=None):
        super().__init__()
        self.color = color
        self.title = title
        self.preview_fn = preview_fn
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.clicked.connect(self._pick)

    def set_color(self, c: str):
        self.color = c
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(brand.BONE_DIM), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(1.5, 1.5, 31, 31))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.color))
        p.drawEllipse(QRectF(6, 6, 22, 22))

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
