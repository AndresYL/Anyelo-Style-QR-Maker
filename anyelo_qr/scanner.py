"""Menú del atajo global: escanear (región, pantalla completa, archivo) o crear / abrir el programa."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QCursor, QDesktopServices, QGuiApplication, QKeySequence, QPainter, QPen, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QVBoxLayout, QWidget)

from . import brand
from .fonts import font
from .paths import DEFAULT_LOGO
from .reader import Found, analyze_link, is_url, read_paths, read_pil
from .widgets import CtaButton, LinkButton, Pill, eyebrow, headline, muted, qimage_to_pil, section


def grab_screen(screen):
    """Captura una pantalla completa. Devuelve (QPixmap, imagen PIL)."""
    pix = screen.grabWindow(0)
    return pix, qimage_to_pil(pix.toImage())


def read_text_hits(pil_img, source: str) -> list[Found]:
    return [Found(source, None, t, k, analyze_link(t)) for t, k in read_pil(pil_img)]


# ---------- menú del atajo ----------

class ScanMenu(QWidget):
    chosen = Signal(str)   # region | screen | file | create | open

    GROUPS = [
        ("Escanear", [
            ("region", "Escanear región", "Marca con el ratón el QR que estás viendo", "1"),
            ("screen", "Pantalla completa", "Busca todos los QR visibles ahora", "2"),
            ("file", "Imagen del computador", "Elige una imagen o un PDF", "3"),
        ]),
        ("Crear", [
            ("create", "Crear un QR", "Abre el programa listo para tus links", "4"),
            ("open", "Abrir el programa", "Ir a la ventana principal", "5"),
        ]),
    ]

    def __init__(self, hotkey_text: str = ""):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._ready = False
        QTimer.singleShot(400, lambda: setattr(self, "_ready", True))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        card = QFrame()
        card.setObjectName("menuCard")
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(22, 20, 14, 8)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(DEFAULT_LOGO)).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        close = LinkButton("×")
        close.clicked.connect(self.close)
        head.addWidget(logo)
        head.addSpacing(10)
        head.addWidget(headline("¿Qué quieres", "hacer", "?", px=22), 1)
        head.addWidget(close)
        v.addLayout(head)

        keys = []
        for title, options in self.GROUPS:
            sec = section(title)
            sec.layout().setContentsMargins(22, 14, 22, 4)
            v.addWidget(sec)
            for key, name, sub, num in options:
                v.addWidget(self._choice(key, name, sub, num))
                keys.append((key, num))

        hint = "ESC para cerrar"
        if hotkey_text:
            hint += f"  ·  Atajo {hotkey_text}"
        hl = eyebrow(hint, brand.MUTED, 10)
        hl.setContentsMargins(22, 14, 22, 16)
        v.addWidget(hl)
        self.setFixedWidth(460)

        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        for key, num in keys:
            QShortcut(QKeySequence(num), self, activated=lambda k=key: self.chosen.emit(k))

    def _choice(self, key, title, sub, num):
        from PySide6.QtWidgets import QPushButton
        b = QPushButton()
        b.setObjectName("choice")
        b.setFixedHeight(60)
        b.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(b)
        lay.setContentsMargins(19, 6, 22, 6)
        k = QLabel(num)
        k.setObjectName("choiceKey")
        k.setFont(font("semibold", 13, 0.8))
        k.setStyleSheet(f"color:{brand.RED_L};")
        k.setFixedSize(26, 22)
        col = QVBoxLayout()
        col.setSpacing(0)
        a = QLabel(title)
        a.setObjectName("choiceTitle")
        a.setFont(font("xbold", 16, -0.2))
        c = QLabel(sub)
        c.setObjectName("choiceSub")
        c.setFont(font("regular", 12))
        c.setStyleSheet(f"color:{brand.MUTED};")
        col.addWidget(a)
        col.addWidget(c)
        lay.addWidget(k, alignment=Qt.AlignTop)
        lay.addLayout(col, 1)
        for w in (k, a, c):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        b.clicked.connect(lambda: self.chosen.emit(key))
        return b

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
        p.fillRect(self.rect(), QColor(7, 7, 7, 170))
        sel = self._sel()
        if sel and sel.width() > 1 and sel.height() > 1:
            src = QRect(int(sel.x() * self.dpr), int(sel.y() * self.dpr), int(sel.width() * self.dpr), int(sel.height() * self.dpr))
            p.drawPixmap(sel, self.pix, src)
            p.setPen(QPen(QColor(brand.GOLD), 2))
            p.drawRect(sel)
            p.setFont(font("semibold", 12, 0.8))
            p.setPen(QColor(brand.GOLD))
            p.drawText(sel.bottomLeft() + QPoint(2, 20), f"{sel.width()} × {sel.height()}")
        else:
            p.setFont(font("xbold", 22, -0.3))
            p.setPen(QColor(brand.BONE))
            p.drawText(self.rect().adjusted(0, 46, 0, 0), Qt.AlignHCenter | Qt.AlignTop, "Arrastra para marcar el QR")
            p.setFont(font("semibold", 12, 1.2))
            p.setPen(QColor(brand.GOLD))
            p.drawText(self.rect().adjusted(0, 84, 0, 0), Qt.AlignHCenter | Qt.AlignTop, "ESC PARA CANCELAR")

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
        self.setMinimumWidth(500)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 24, 26, 22)
        v.setSpacing(12)
        if found:
            v.addWidget(eyebrow("Resultado"))
            n = len(found)
            v.addWidget(headline(f"{n} código{'s' if n != 1 else ''}", "encontrado" + ("s" if n != 1 else ""), px=26))
        else:
            v.addWidget(eyebrow("Resultado"))
            v.addWidget(headline("No encontré", "ningún QR", px=26))
            v.addWidget(muted("Prueba a marcar solo el QR, con un poco de margen blanco alrededor, "
                              "o acércalo para que se vea más grande."))
        for f in found:
            v.addWidget(self._card(f))
        if note:
            v.addWidget(muted(note, 12))
        close = CtaButton("Cerrar", arrow=False)
        close.clicked.connect(self.accept)
        v.addSpacing(4)
        v.addWidget(close, alignment=Qt.AlignRight)

    def _card(self, f: Found) -> QFrame:
        card = QFrame()
        card.setObjectName("resultCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(6)
        txt = QLabel(f.text)
        txt.setFont(font("semibold", 14))
        txt.setWordWrap(True)
        txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(txt)
        for w in f.warnings:
            lb = QLabel("!  " + w)
            lb.setFont(font("regular", 12))
            lb.setStyleSheet(f"color:{brand.RED_L};")
            lb.setWordWrap(True)
            v.addWidget(lb)
        row = QHBoxLayout()
        row.setSpacing(8)
        cp = Pill("Copiar")
        cp.clicked.connect(lambda: (QGuiApplication.clipboard().setText(f.text), cp.setText("Copiado")))
        row.addWidget(cp)
        if is_url(f.text):
            op = Pill("Abrir link")
            op.clicked.connect(lambda: self._open(f))
            row.addWidget(op)
        row.addStretch()
        v.addSpacing(4)
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
        if kind == "create":
            self.main.open_create()
            return
        if kind == "open":
            self.main.show_window()
            return
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
