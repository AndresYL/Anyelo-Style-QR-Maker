# Anyelo Style QR

Generador y lector de códigos QR para Windows. Funciona sin internet y es de código abierto (MIT).

## Qué hace la versión 0.1

**Generar.** Pegas varios links (uno por línea), eliges la carpeta y se crean todos de una vez en PNG, SVG y/o PDF.
Para ponerle nombre al archivo escribe `Nombre | link`. También acepta dos columnas pegadas desde Excel.

**Excel / CSV.** Cargas un `.xlsx` o `.csv`, eliges la columna del nombre y la del link, y sale un QR por fila.

**Leer QR.** Arrastras imágenes, PDFs o carpetas enteras. Te muestra el contenido de cada código, avisa si un link
es sospechoso (acortadores, http sin cifrar, IP en vez de dominio, dominios que imitan a otros) y puedes copiar o
exportar a CSV.

**Estilo.** Colores, logo central (por defecto el de Anyelo Style, o cualquier otro), tamaño, nivel de corrección de
errores. Cada QR creado se lee de vuelta para confirmar que escanea, y la app avisa si el contraste es bajo o el logo
tapa demasiado.

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
anyelo_qr/core.py      generación, logo, lotes, verificación
anyelo_qr/reader.py    lectura de QR y chequeo de links
anyelo_qr/tabular.py   Excel y CSV
anyelo_qr/gui.py       ventana (PySide6)
tests/                 pruebas automáticas (python -m pytest)
```

## Licencias de las librerías

PySide6 (LGPL), segno (BSD), Pillow (HPND), zxing-cpp (Apache 2.0), pypdfium2 (Apache 2.0 / BSD), openpyxl (MIT).
