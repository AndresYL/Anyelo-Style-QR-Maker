"""Genera las imágenes de la página de descarga a partir del programa real (capturas sin pantalla).
Uso, desde la raíz del proyecto:   python web/make_shots.py
Cuando cambie la interfaz, se vuelve a correr y luego `python web/build_page.py`."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp()

from PIL import Image, ImageDraw, ImageFilter
from PySide6.QtWidgets import QApplication

from anyelo_qr import brand, gui
from anyelo_qr.core import QRStyle, render_png
from anyelo_qr.fonts import font, load_fonts
from anyelo_qr.paths import DEFAULT_LOGO
from anyelo_qr.reader import Found
from anyelo_qr.scanner import ScanMenu, ScanResultDialog
from anyelo_qr.theme import build_qss

OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(exist_ok=True)
SITE = "https://anyelo.style"

app = QApplication([])
load_fonts()
app.setFont(font("regular", 13))
app.setStyleSheet(build_qss())


def pump(n=60, pause=0.25):
    for _ in range(n):
        app.processEvents()
    time.sleep(pause)
    for _ in range(40):
        app.processEvents()


def save(img: Image.Image, name: str, width: int = 1200, quality: int = 84):
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(OUT / f"{name}.webp", "WEBP", quality=quality, method=6)
    print(name, img.size, round((OUT / f"{name}.webp").stat().st_size / 1024), "KB")


def grab(widget) -> Image.Image:
    widget.show()
    pump()
    path = OUT / "_tmp.png"
    widget.grab().save(str(path))
    im = Image.open(path).convert("RGBA")
    im.load()
    path.unlink()
    return im


# ---------- ventana principal ----------
w = gui.MainWindow()
w.hotkey.unregister()
w.resize(1320, 940)
w.settings.out_dir = r"C:\Users\Anyelo\Documents\QR Anyelo Style"
w.settings.open_after = False
for d in w._destinations:
    d.load()
p = w.panel
p.logo.setCurrentIndex(1)
p.shape.setCurrentIndex(p.shape.findData("rounded"))
p.eye.setCurrentIndex(p.eye.findData("circle"))

gt = w.generate_tab
gt.text.setPlainText(
    "Instagram | anyelo.style/ig\n"
    "Música nueva | anyelo.style/musica\n"
    "Libro | anyelo.style/elprimersegundo\n"
    "Sticker Good Vibes | anyelo.style/gvo\n"
)
tmp_out = tempfile.mkdtemp()
w.settings.out_dir = tmp_out
for d in w._destinations:
    d.load()
w.show()
pump()
gt.generate()
t0 = time.time()
while (w._job is None or w._job.isRunning()) and time.time() - t0 < 30:
    app.processEvents()
pump(80)
# la ruta que se ve en pantalla es la de un usuario real, no la carpeta temporal
for d in w._destinations:
    d.folder.setText(r"C:\Users\Anyelo\Documents\QR Anyelo Style")
w.toast.hide()
w.pages.setCurrentIndex(0)
pump()
save(grab(w), "generar", 1280)

# ---------- Excel ----------
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "Links"
ws.append(["Nombre", "Link", "Campaña"])
rows = [("Bio de Instagram", "anyelo.style/ig", "perfil"), ("Música nueva", "anyelo.style/musica", "lanzamiento"),
        ("Libro El Primer Segundo", "anyelo.style/elprimersegundo", "libro"), ("Sticker Good Vibes", "anyelo.style/gvo", "stickers"),
        ("Rastreador de hábitos", "anyelo.style/habitos", "herramientas"), ("Calculadora 6 Jarrones", "anyelo.style/6jarrones", "herramientas"),
        ("Playlist en Spotify", "anyelo.style/playlist", "musica"), ("Contacto", "anyelo.style/contacto", "perfil")]
for r in rows:
    ws.append(list(r))
xlsx = Path(tmp_out) / "lista.xlsx"
wb.save(xlsx)
w.pages.setCurrentIndex(1)
w.excel_tab.load(str(xlsx))
w.resize(1320, 940)
pump()
w.toast.hide()
save(grab(w), "excel", 1280)

# ---------- UTM ----------
u = w.utm_tab
w.pages.setCurrentIndex(2)
u.base.setText("anyelo.style/musica")
u._preset("instagram", "social")
u.fields["campaign"].setText("Lanzamiento otoño")
w.panel_scroll.hide()
w.resize(1320, 940)
pump()
w.toast.hide()
shot = grab(w)
# el panel de estilo no aparece en esta página: se recorta el ancho que ocupa en las otras
save(shot, "utm", 1280)

# ---------- ajustes ----------
w.pages.setCurrentIndex(4)
pump()
w.toast.hide()
save(grab(w), "ajustes", 1280)

# ---------- menú del atajo sobre un escritorio de ejemplo ----------
menu = ScanMenu("Ctrl+Alt+Q")
menu.layout().activate()
menu.adjustSize()
m = grab(menu)
H = 600
bg = Image.new("RGB", (1280, H), "#0b0b0b")
d = ImageDraw.Draw(bg)
for y in range(H):                        # degradado suave
    c = int(11 + 14 * (y / H))
    d.line([(0, y), (1280, y)], fill=(c, c, c))
sample = render_png(SITE, QRStyle(fg="#070707", bg="#FAEDD3", size=360, shape="rounded", eye_shape="rounded"))
# una "ventana" de video con el QR, como el que alguien vería en una llamada o una presentación
win = Image.new("RGB", (560, 390), "#161616")
wd = ImageDraw.Draw(win)
wd.rectangle((0, 0, 559, 26), fill="#0e0e0e")
for i, c in enumerate(("#3a3a3a", "#3a3a3a", "#3a3a3a")):
    wd.ellipse((12 + i * 18, 8, 22 + i * 18, 18), fill=c)
win.paste(sample.resize((330, 330)), (115, 42))
wy = (H - 390) // 2
bg.paste(win, (660, wy))
bd = ImageDraw.Draw(bg)
bd.rectangle((660, wy, 660 + 559, wy + 389), outline="#2a2a2a")
# recuadro dorado de "región" alrededor del QR
bd.rectangle((660 + 105, wy + 32, 660 + 105 + 350, wy + 32 + 350), outline="#d4af37", width=3)
mx, my = 90, (H - m.height) // 2
bg_rgba = bg.convert("RGBA")
shadow = Image.new("RGBA", bg_rgba.size, (0, 0, 0, 0))
shadow.paste((0, 0, 0, 170), (mx + 6, my + 10, mx + m.width - 6, my + m.height))
shadow = shadow.filter(ImageFilter.GaussianBlur(18))
bg_rgba.alpha_composite(shadow)
bg_rgba.alpha_composite(m, (mx, my))
save(bg_rgba, "atajo", 1280)
menu.close()

# ---------- resultado del escaneo ----------
found = [Found("pantalla", None, SITE + "/musica", "QRCode", []),
         Found("pantalla", None, "http://bit.ly/3xZ9kQ", "QRCode", ["Usa http sin cifrar", "Acortador: el destino final queda oculto"])]
dlg = ScanResultDialog(found, "El primer resultado ya está copiado al portapapeles.")
dlg.setMinimumWidth(560)
r = grab(dlg)
bg2 = Image.new("RGB", (r.width + 120, r.height + 100), "#0b0b0b")
bg2.paste(r.convert("RGB"), (60, 50))
save(bg2, "resultado", 900)
dlg.close()

os._exit(0)
