"""Pruebas de la interfaz (sin pantalla): el grabador de atajo, copiar sin archivos, menú y diseño compacto."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QApplication

from anyelo_qr.fonts import font, load_fonts
from anyelo_qr.theme import build_qss


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    load_fonts()
    a.setFont(font("regular", 13))
    a.setStyleSheet(build_qss())
    return a


@pytest.fixture()
def win(app, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from anyelo_qr.gui import MainWindow
    w = MainWindow()
    w.hotkey.unregister()
    yield w
    w.close()


def key(vk, mods, k=Qt.Key_Q, text=""):
    return QKeyEvent(QEvent.KeyPress, k, mods, 0, vk, 0, text)


def test_fonts_are_bundled(app):
    assert load_fonts()


def test_defaults(win):
    assert win.panel.logo.currentText() == "Sin logo"          # primero Sin logo, luego Anyelo Style, luego otro
    assert [win.panel.logo.itemText(i) for i in range(3)] == ["Sin logo", "Anyelo Style", "Otro logo…"]
    assert win.settings.open_after is True


def test_recorder_reads_the_physical_key_not_the_character(app):
    """En teclado latinoamericano Ctrl+Alt+Q escribe «@»: Qt entrega Key_At, pero la tecla física es la Q (0x51)."""
    from anyelo_qr.widgets import HotkeyRecorder
    rec = HotkeyRecorder("Ctrl+Shift+Q")
    got = []
    rec.committed.connect(got.append)
    rec.start()
    rec.keyPressEvent(key(0x51, Qt.ControlModifier | Qt.AltModifier, Qt.Key_At, "@"))
    assert got == ["Ctrl+Alt+Q"] and rec.value == "Ctrl+Alt+Q"
    assert not rec._rec


def test_recorder_rejects_and_cancels(app):
    from anyelo_qr.widgets import HotkeyRecorder
    rec = HotkeyRecorder("Ctrl+Alt+Q")
    bad = []
    rec.rejected.connect(bad.append)
    rec.start()
    rec.keyPressEvent(key(0x51, Qt.NoModifier))                          # sin Ctrl/Alt/Win
    assert bad and rec._rec and rec.value == "Ctrl+Alt+Q"
    rec.keyPressEvent(key(0x1B, Qt.NoModifier, Qt.Key_Escape))
    assert not rec._rec and rec.value == "Ctrl+Alt+Q"


def test_recorder_accepts_function_keys(app):
    from anyelo_qr.widgets import HotkeyRecorder
    rec = HotkeyRecorder("Ctrl+Alt+Q")
    got = []
    rec.committed.connect(got.append)
    rec.start()
    rec.keyPressEvent(key(0x78, Qt.ControlModifier | Qt.ShiftModifier, Qt.Key_F9))
    assert got == ["Ctrl+Shift+F9"]


def test_set_hotkey_keeps_old_one_when_new_fails(win, monkeypatch):
    win.settings.hotkey = "Ctrl+Alt+Q"
    calls = []

    def fake_register(text):
        calls.append(text)
        return (text != "Ctrl+Alt+Z", "ocupado" if text == "Ctrl+Alt+Z" else "")
    monkeypatch.setattr(win.hotkey, "register", fake_register)
    ok, msg = win.set_hotkey("Ctrl+Alt+Z")
    assert not ok and msg == "ocupado"
    assert win.settings.hotkey == "Ctrl+Alt+Q"                           # no se guarda un atajo que no funciona
    assert calls == ["Ctrl+Alt+Z", "Ctrl+Alt+Q"]                         # y se vuelve a registrar el anterior


def test_reset_button_goes_to_the_recommended_hotkey(win, monkeypatch):
    monkeypatch.setattr(win.hotkey, "register", lambda t: (True, ""))
    win.settings.hotkey = "Ctrl+Shift+F9"
    win.settings_tab._reset()
    from anyelo_qr.hotkey import default_hotkey
    assert win.settings.hotkey == default_hotkey()
    assert win.settings_tab.rec.value == default_hotkey()


def test_copy_preview_creates_no_files(win, tmp_path):
    out = tmp_path / "salida"
    win.settings.out_dir = str(out)
    QGuiApplication.clipboard().clear()
    win.generate_tab.text.setPlainText("https://anyelostyle.com/promo")
    win.generate_tab._sample()
    win.panel.copy_requested.emit()
    assert not QGuiApplication.clipboard().image().isNull()
    assert not out.exists()                                              # copiar no gasta espacio en disco


def test_copy_with_empty_list_just_warns(win):
    QGuiApplication.clipboard().clear()
    win.generate_tab.text.clear()
    win.generate_tab._sample()
    win.generate_tab.copy_btn.click()
    assert QGuiApplication.clipboard().image().isNull()
    assert "link" in win.toast.text().lower()


def test_copy_selected_result_row(win, tmp_path):
    from anyelo_qr.core import BatchRow
    t = win.generate_tab.table
    t.show_rows([BatchRow("uno", "https://a.com", "ok"), BatchRow("dos", "https://b.com", "ok")])
    t.selectRow(1)
    QGuiApplication.clipboard().clear()
    win.copy_qr([], t)
    assert not QGuiApplication.clipboard().image().isNull()


def test_destination_step_is_compact(win):
    h = win.generate_tab.dest.sizeHint().height()
    assert h <= 120, h                                                   # antes ocupaba ~170 px


def test_scan_menu_has_create_and_open(app):
    from anyelo_qr.scanner import ScanMenu
    keys = [k for _t, opts in ScanMenu.GROUPS for k, *_ in opts]
    assert keys == ["region", "screen", "file", "create", "open"]
    m = ScanMenu("Ctrl+Alt+Q")
    got = []
    m.chosen.connect(got.append)
    for b in m.findChildren(type(m.findChild(object, options=Qt.FindChildrenRecursively) or m)):
        pass
    from PySide6.QtWidgets import QPushButton
    btns = [b for b in m.findChildren(QPushButton) if b.objectName() == "choice"]
    assert len(btns) == 5
    btns[3].click()
    btns[4].click()
    assert got == ["create", "open"]


def test_menu_create_and_open_drive_the_main_window(win):
    from anyelo_qr.scanner import Scanner
    calls = []
    win.open_create = lambda: calls.append("create")
    win.show_window = lambda: calls.append("open")
    sc = Scanner(win, lambda: "")
    sc._chosen("create")
    sc._chosen("open")
    assert calls == ["create", "open"]


def test_open_create_pastes_a_copied_link(win):
    QGuiApplication.clipboard().setText("anyelostyle.com/promo")
    win.generate_tab.text.clear()
    win.open_create()
    assert win.generate_tab.text.toPlainText() == "https://anyelostyle.com/promo"
    assert win.pages.currentWidget() is win.generate_tab
    QGuiApplication.clipboard().setText("hola, esto no es un link")
    win.generate_tab.text.clear()
    win.open_create()
    assert win.generate_tab.text.toPlainText() == ""


def test_style_panel_only_on_pages_that_generate(win):
    win.pages.setCurrentWidget(win.excel_tab)
    assert not win.panel_scroll.isHidden()
    win.pages.setCurrentWidget(win.settings_tab)
    assert win.panel_scroll.isHidden()


# ---------- v0.4: inicio con Windows y copia única ----------

class _FakeWinreg:
    HKEY_CURRENT_USER, KEY_READ, KEY_SET_VALUE, REG_SZ = 1, 1, 2, 1

    def __init__(self):
        self.values = {}

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def OpenKey(self, root, path, res, access):
        return self._Key()

    CreateKeyEx = OpenKey

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, res, typ, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture()
def fake_windows(monkeypatch):
    import sys
    from anyelo_qr import winfx
    reg = _FakeWinreg()
    monkeypatch.setitem(sys.modules, "winreg", reg)
    monkeypatch.setattr(winfx, "IS_WIN", True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Users\Anyelo\AppData\Local\Programs\Anyelo Style QR\AnyeloStyleQR.exe")
    return reg


def test_autostart_writes_the_minimized_command(fake_windows):
    from anyelo_qr import winfx
    assert winfx.autostart_supported() and not winfx.autostart_enabled()
    assert winfx.set_autostart(True) and winfx.autostart_enabled()
    cmd = fake_windows.values[winfx.RUN_VALUE]
    assert cmd.startswith('"C:\\Users\\Anyelo') and cmd.endswith('AnyeloStyleQR.exe" --minimized')
    assert winfx.set_autostart(False) and not winfx.autostart_enabled()
    assert winfx.set_autostart(False)                                  # quitarlo dos veces no falla


def test_autostart_follows_the_program_when_it_moves(fake_windows, monkeypatch):
    import sys
    from anyelo_qr import winfx
    winfx.set_autostart(True)
    monkeypatch.setattr(sys, "executable", r"D:\Portable\AnyeloStyleQR.exe")
    winfx.refresh_autostart_path()
    assert fake_windows.values[winfx.RUN_VALUE] == '"D:\\Portable\\AnyeloStyleQR.exe" --minimized'


def test_autostart_is_off_when_running_from_source(monkeypatch):
    import sys
    from anyelo_qr import winfx
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert not winfx.autostart_supported()
    assert winfx.set_autostart(True) is False and winfx.autostart_enabled() is False


def test_autostart_checkbox_follows_the_registry(win, fake_windows):
    from anyelo_qr import winfx
    winfx.set_autostart(True)
    from anyelo_qr.gui import SettingsTab
    tab = SettingsTab(win)
    assert tab.auto.isEnabled() and tab.auto.isChecked()
    tab.auto.setChecked(False)
    assert not winfx.autostart_enabled()


def test_second_copy_brings_the_first_to_the_front(app):
    from anyelo_qr.instance import InstanceGuard
    import time
    name = f"AnyeloStyleQR-test-{os.getpid()}"
    first, second = InstanceGuard(name), InstanceGuard(name)
    assert not second.notify_running()                                 # todavía no hay nadie abierto
    shown = []
    first.listen(lambda: shown.append(1))
    assert second.notify_running()
    for _ in range(50):
        app.processEvents()
        if shown:
            break
        time.sleep(0.02)
    assert shown
    first.server.close()
