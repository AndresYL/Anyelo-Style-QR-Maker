# Anyelo Style QR

Generador y lector de códigos QR para Windows. Funciona sin internet y es de código abierto (MIT).

## Qué hace la versión 0.2

**Generar, en tres pasos.** Pones los links (uno por línea; con `Nombre | link` eliges el nombre del archivo), eliges la
carpeta y los formatos (PNG, SVG, PDF), y generas. También puedes copiar un QR al portapapeles. Al terminar, la carpeta
se abre sola si lo dejas marcado.

**Excel / CSV.** Cargas un `.xlsx` o `.csv`, eliges la columna del nombre y la del link, y sale un QR por fila.

**UTM.** Armas el link con sus parámetros de seguimiento (con atajos para Instagram, TikTok, YouTube, WhatsApp…) y lo
sumas a la lista de QR con un clic.

**Estilo.** Colores con selector propio y vista previa en vivo, forma de los cuadritos (cuadrados, redondeados, puntos,
barras), forma y color de los ojos, logo central (ninguno, el de Anyelo Style u otro) con o sin borde, tamaño exacto en
píxeles y nivel de corrección. La vista previa avisa si el QR no se lee de vuelta, y cada QR que creas se verifica solo.

**Escanear la pantalla.** Con el atajo global (por defecto `Ctrl+Alt+Q`, se cambia en Ajustes) aparece un menú para
escanear una región, toda la pantalla o una imagen del computador. El programa sigue activo junto al reloj aunque
cierres la ventana. Antes de abrir un link te muestra a dónde va y avisa de acortadores, http sin cifrar, IP en vez de
dominio y dominios que imitan a otros.

**Leer QR.** Arrastras imágenes, PDFs o carpetas enteras; copias o exportas a CSV.

Los ajustes se guardan en `%APPDATA%\AnyeloStyleQR\settings.json`.

## Probarlo sin instalar nada raro

```bat
run_dev.bat
```

## Crear el .exe

```bat
build_windows.bat
```

El resultado queda en `dist\AnyeloStyleQR\`. La primera vez Windows puede mostrar "editor desconocido" porque el
programa no tiene firma digital; es normal en versiones de prueba.

## Cambiar la marca

Colores y nombre: `anyelo_qr/brand.py`. Logo: `anyelo_qr/assets/logo.png` (PNG con fondo transparente; si es blanco
con huecos transparentes, como el actual, la app le pone el respaldo oscuro sola). Ícono: `anyelo_qr/assets/icon.ico`.

## Estructura

```
anyelo_qr/core.py      generación (formas, ojos, logo), lotes, verificación, UTM
anyelo_qr/reader.py    lectura de QR y chequeo de links
anyelo_qr/tabular.py   Excel y CSV
anyelo_qr/gui.py       ventana principal y pestañas (PySide6)
anyelo_qr/scanner.py   menú del atajo, región, pantalla completa
anyelo_qr/hotkey.py    atajo global de Windows
anyelo_qr/widgets.py   selector de color, tarjetas de paso, tablas
anyelo_qr/theme.py     hoja de estilos
tests/                 pruebas automáticas (python -m pytest)
```

## Licencias de las librerías

PySide6 (LGPL), segno (BSD), Pillow (HPND), zxing-cpp (Apache 2.0), pypdfium2 (Apache 2.0 / BSD), openpyxl (MIT).
