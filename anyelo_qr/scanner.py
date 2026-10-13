"""Escaneo de QR desde la pantalla: menú del atajo, región, pantalla completa o archivo."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, QUrl, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QDesktopServices, QFont, QGuiApplication, QPainter, QPen, QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from . import brand
from .paths import DEFAULT_LOGO
from .reader import Found, analyze_link, is_url, read_paths, read_pil
from .widgets import muted, qimage_to_pil


def grab_screen(screen):
    """Captura una pantalla completa. Devuelve (QPixmap, imagen PIL)."""
    pix = screen.grabWindow(0)
    return pix, qimage_to_pil(pix.toImage())


def read_text_hits(pil_img, source: str) -> list[Found]:
    return [Found(source, None, t, k, analyze_link(t)) for t, k in read_pil(pil_img)]


# ---------- menú del atajo ----------

class ScanMenu(QWidget):
    chosen = Signal(str)   # region | screen | file

    OPTIONS = [
        ("region", "Escanear región", "Marca con el ratón el QR que estás viendo", "1"),
        ("screen", "Escanear pantalla completa", "Busca todos los QR visibles ahora", "2"),
        ("file", "Escanear imagen del computador", "Elige una imagen o un PDF", "3"),
    ]

    def __init__(self, hotkey_text: str = ""):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._ready = False
        QTimer.singleShot(350, lambda: setattr(self, "_ready", True))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = QFrame()
        card.setObjectName("menuCard")
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 18, 20, 16)
        v.setSpacing(10)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(DEFAULT_LOGO)).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        t = QLabel("¿Qué quieres escanear?")
        t.setObjectName("h1")
        t.setStyleSheet("font-size:17px;")
        close = QPushButton("✕")
        close.setObjectName("link")
        close.clicked.connect(self.close)
        head.addWidget(logo)
        head.addSpacing(8)
        head.addWidget(t, 1)
        head.addWidget(close)
        v.addLayout(head)

        for key, title, sub, num in self.OPTIONS:
            v.addWidget(self._choice(key, title, sub, num))

        hint = "Esc para cerrar"
        if hotkey_text:
            hint += f"  ·  Atajo: {hotkey_text}"
        hl = QLabel(hint)
        hl.setObjectName("muted")
        v.addWidget(hl, alignment=Qt.AlignHCenter)
        self.setFixedWidth(440)

        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        for key, _t, _s, num in self.OPTIONS:
            QShortcut(QKeySequence(num), self, activated=lambda k=key: self._emit(k))

    def _choice(self, key, title, sub, num) -> QPushButton:
        b = QPushButton()
        b.setObjectName("choice")
        b.setFixedHeight(64)
        b.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(b)
        lay.setContentsMargins(14, 8, 14, 8)
        k = QLabel(num)
        k.setObjectName("choiceKey")
        k.setFixedSize(26, 26)
        k.setAlignment(Qt.AlignCenter)
        col = QVBoxLayout()
        col.setSpacing(0)
        a = QLabel(title)
        a.setObjectName("choiceTitle")
        c = QLabel(sub)
        c.setObjectName("choiceSub")
        col.addWidget(a)
        col.addWidget(c)
        lay.addWidget(k)
        lay.addSpacing(6)
        lay.addLayout(col, 1)
        for w in (k, a, c):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        b.clicked.connect(lambda: self._emit(key))
        return b

    def _emit(self, key):
        self.chosen.emit(key)

    def show_centered(self):
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        self.layout().activate()
        self.adjustSize()
        self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))
        self.show()
        self.raise_()
        self.activateWindow()

    def event(self, e):
        if e.type() == QEvent.WindowDeactivate and self._ready:
            self.close()
        return super().event(e)


# ---------- selección de región ----------

class RegionOverlay(QWidget):
    done = Signal(object)    # imagen PIL recortada, o None si se canceló

    def __init__(self, screen, pix: QPixmap, pil_full):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.pix = pix
        self.pil = pil_full
        self.dpr = pix.devicePixelRatio() or 1.0
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self._finished = False

    def _sel(self) -> QRect | None:
        if self.start is None or self.end is None:
            return None
        return QRect(self.start, self.end).normalized()

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pix)
        p.fillRect(self.rect(), QColor(0, 0, 0, 140))
        sel = self._sel()
        if sel and sel.width() > 1 and sel.height() > 1:
            src = QRect(int(sel.x() * self.dpr), int(sel.y() * self.dpr), int(sel.width() * self.dpr), int(sel.height() * self.dpr))
            p.drawPixmap(sel, self.pix, src)
            p.setPen(QPen(QColor("white"), 2))
            p.drawRect(sel)
            p.setPen(QColor("white"))
            p.drawText(sel.bottomLeft() + QPoint(2, 18), f"{sel.width()} × {sel.height()}")
        else:
            f = QFont("Segoe UI", 15)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("white"))
            p.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                       "Arrastra para marcar el QR  ·  Esc para cancelar")

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self._finish(None)
            return
        self.start = e.position().toPoint()
        self.end = self.start
        self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.start is None:
            return
        sel = self._sel()
        if not sel or sel.width() < 8 or sel.height() < 8:
            self.start = self.end = None
            self.update()
            return
        pad = 14   # un margen extra ayuda a leer QR recortados muy justos
        x0 = max(int(sel.left() * self.dpr) - pad, 0)
        y0 = max(int(sel.top() * self.dpr) - pad, 0)
        x1 = min(int((sel.right() + 1) * self.dpr) + pad, self.pil.width)
        y1 = min(int((sel.bottom() + 1) * self.dpr) + pad, self.pil.height)
        self._finish(self.pil.crop((x0, y0, x1, y1)))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(None)

    def _finish(self, img):
        if self._finished:
            return
        self._finished = True
        self.close()
        self.done.emit(img)

    def show_now(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()


# ---------- resultados ----------

class ScanResultDialog(QDialog):
    def __init__(self, found: list[Found], note: str = "", parent=None):
        super().__init__(parent, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(brand.APP_NAME)
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 16)
        v.setSpacing(10)
        title = QLabel(f"{len(found)} código(s) encontrado(s)" if found else "No encontré ningún QR")
        title.setObjectName("h1")
        title.setStyleSheet("font-size:17px;")
        v.addWidget(title)
        if not found:
            v.addWidget(muted("Prueba a marcar solo el QR, con un poco de margen blanco alrededor, "
                              "o acércalo para que se vea más grande."))
        for f in found:
            v.addWidget(self._card(f))
        if note:
            v.addWidget(muted(note))
        close = QPushButton("Cerrar")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        v.addWidget(close, alignment=Qt.AlignRight)

    def _card(self, f: Found) -> QFrame:
        card = QFrame()
        card.setObjectName("resultCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        txt = QLabel(f.text)
        txt.setWordWrap(True)
        txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        txt.setStyleSheet("font-weight:600;")
        v.addWidget(txt)
        for w in f.warnings:
            lb = QLabel("⚠ " + w)
            lb.setObjectName("warn")
            lb.setWordWrap(True)
            v.addWidget(lb)
        row = QHBoxLayout()
        cp = QPushButton("Copiar")
        cp.clicked.connect(lambda: (QGuiApplication.clipboard().setText(f.text), cp.setText("Copiado ✓")))
        row.addWidget(cp)
        if is_url(f.text):
            op = QPushButton("Abrir link")
            op.clicked.connect(lambda: self._open(f))
            row.addWidget(op)
        row.addStretch()
        v.addLayout(row)
        return card

    def _open(self, f: Found):
        if f.warnings:
            r = QMessageBox.question(self, "¿Abrir este link?",
                                     f"{f.text}\n\nCuidado:\n• " + "\n• ".join(f.warnings) + "\n\n¿Abrirlo de todas formas?")
            if r != QMessageBox.Yes:
                return
        QDesktopServices.openUrl(QUrl(f.text))


# ---------- orquestador ----------

class Scanner(QObject):
    def __init__(self, main_window, hotkey_getter):
        super().__init__()
        self.main = main_window
        self.hotkey_getter = hotkey_getter
        self.menu: ScanMenu | None = None
        self.overlay: RegionOverlay | None = None
        self.dialog: ScanResultDialog | None = None
        self._main_was_visible = False
        self._busy = False

    def show_menu(self):
        if self._busy:
            return
        if self.menu is not None and self.menu.isVisible():
            self.menu.close()
        self.menu = ScanMenu(self.hotkey_getter())
        self.menu.chosen.connect(self._chosen)
        self.menu.show_centered()

    def _chosen(self, kind: str):
        if self.menu:
            self.menu.close()
        if kind == "file":
            self._pick_file()
            return
        self._busy = True
        self._main_was_visible = self.main.isVisible()
        if self._main_was_visible:
            self.main.hide()
        QTimer.singleShot(250, lambda: self._capture(kind))   # deja que desaparezcan nuestras ventanas

    def _restore(self):
        self._busy = False
        if self._main_was_visible:
            self.main.show()

    def _capture(self, kind: str):
        try:
            if kind == "screen":
                found: list[Found] = []
                for scr in QGuiApplication.screens():
                    _pix, pil = grab_screen(scr)
                    found.extend(read_text_hits(pil, "pantalla"))
                self._restore()
                self._show(found)
            else:
                scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
                pix, pil = grab_screen(scr)
                self.overlay = RegionOverlay(scr, pix, pil)
                self.overlay.done.connect(self._region_done)
                self.overlay.show_now()
        except Exception as exc:
            self._restore()
            QMessageBox.warning(None, brand.APP_NAME, f"No pude capturar la pantalla.\n\n{exc}")

    def _region_done(self, img):
        self._restore()
        if img is None:
            return
        self._show(read_text_hits(img, "región"))

    def _pick_file(self):
        fs, _ = QFileDialog.getOpenFileNames(None, "Elegir imagen o PDF", "",
                                             "Imágenes y PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.pdf)")
        if not fs:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            found, errors = read_paths(fs)
        finally:
            QApplication.restoreOverrideCursor()
        self._show(found, "; ".join(errors[:2]))

    def _show(self, found: list[Found], note: str = ""):
        if found:
            QGuiApplication.clipboard().setText(found[0].text)
            note = (note + " " if note else "") + "El primer resultado ya está copiado al portapapeles."
        self.dialog = ScanResultDialog(found, note)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
