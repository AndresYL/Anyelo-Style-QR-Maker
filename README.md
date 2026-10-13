# Anyelo Style QR

Generador y lector de códigos QR para Windows. Funciona sin internet y es de código abierto (MIT).

## Qué hace la versión 0.3

**Diseño.** La interfaz usa el mismo lenguaje de la página de Anyelo Style: negro, hueso, crema, rojo y dorado, la
tipografía Bricolage Grotesque, el botón rojo con sombra dura, la numeración 01-02-03 y el riel lateral con marcador
dorado. Todos los colores están en `anyelo_qr/brand.py`.

**Generar, en tres pasos.** Pones los links (uno por línea; con `Nombre | link` eliges el nombre del archivo), eliges el
destino (carpeta, formatos y si se abre al terminar) y generas. "Copiar al portapapeles" y "Copiar este QR" copian el QR
sin crear ningún archivo.

**Excel / CSV.** Cargas un `.xlsx` o `.csv`, eliges la columna del nombre y la del link, y sale un QR por fila.

**UTM.** Armas el link con sus parámetros de seguimiento (con atajos para Instagram, TikTok, YouTube, WhatsApp...) y lo
sumas a la lista de QR con un clic.

**Estilo.** Selector de color propio con vista previa en vivo, forma de los cuadritos (cuadrados, redondeados, puntos,
barras), forma y color de los ojos, logo central (ninguno, el de Anyelo Style u otro) con o sin borde, tamaño exacto en
píxeles y nivel de corrección. La vista previa avisa si el QR no se lee de vuelta, y cada QR que creas se verifica solo.

**Atajo global.** Por defecto `Ctrl+Alt+Q` (si tu teclado usa esa combinación para escribir un carácter, como la «@»
del teclado latinoamericano, el programa propone `Ctrl+Shift+Q`). Abre un menú con cinco opciones: escanear una región,
escanear toda la pantalla, escanear una imagen, crear un QR (con el link copiado ya pegado) o abrir el programa. El
atajo se cambia en Ajustes grabando la combinación, y hay un botón para restablecerlo. El programa sigue activo junto al
reloj aunque cierres la ventana.

**Leer QR.** Arrastras imágenes, PDFs o carpetas enteras; copias o exportas a CSV. Antes de abrir un link te muestra a
dónde va y avisa de acortadores, http sin cifrar, IP en vez de dominio y dominios que imitan a otros.

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
anyelo_qr/widgets.py   botones, riel, selector de color, tarjetas de paso, grabador de atajo
anyelo_qr/fonts.py     tipografía Bricolage Grotesque
anyelo_qr/winfx.py     barra de título oscura y detección de AltGr (Windows)
anyelo_qr/theme.py     hoja de estilos
tests/                 pruebas automáticas (python -m pytest)
```

## Licencias de las librerías

Bricolage Grotesque (SIL OFL, ver `anyelo_qr/assets/fonts/OFL-NOTICE.txt`), PySide6 (LGPL), segno (BSD), Pillow (HPND), zxing-cpp (Apache 2.0), pypdfium2 (Apache 2.0 / BSD), openpyxl (MIT).
