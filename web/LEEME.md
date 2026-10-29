# Página de descarga

Es la página del programa para anyelo.style, en el mismo estilo que las páginas de tus plugins (titular grande,
tarjetas redondeadas, una demo que se prueba ahí mismo). Pesa unos 80 KB y cabe pegada en el campo "Código de la
herramienta".

- `pagina-descarga.template.html` es la página.
- `build_page.py` le pone la librería de QR, el logo y los datos de respaldo, y deja un solo archivo:
  `web/dist/descarga-anyelo-style-qr.html`.
- `shots/` guarda las capturas del programa. La página las toma de aquí, directamente de GitHub, así que se cambian
  subiendo una imagen nueva al repositorio, sin tocar la página.
- `vendor/` trae la librería que dibuja el QR de la demo (qrcode-generator, licencia MIT).

## Publicarla por primera vez

1. **Repositorio público.** En GitHub: Settings, General, abajo "Danger Zone", "Change visibility", "Make public".
   Hasta que lo hagas, los botones de descarga y las capturas solo funcionan para ti. Antes confirma que existe al
   menos un release (pestaña Actions, "Run workflow") con `AnyeloStyleQR-Setup.exe` adentro.
2. **Página nueva.** Entradas, Añadir nueva, tipo **Herramienta**, y llena:
   - Etiqueta: `Programa gratuito para Windows`
   - Título grande: `Generador de QR *sin internet*`
   - Subtítulo: `Pega tus links, elige cómo se ven y llévate cien códigos en una carpeta. Gratis, para Windows.`
   - Título para Google: `Generador de QR gratis para Windows: sin internet, por lotes y con tu logo`
   - Código de la herramienta: abre `descarga-anyelo-style-qr.html` con el Bloc de notas, copia todo y pégalo.
     (Si el hosting no deja guardar el código, sube el archivo a la carpeta `tools` del tema y escribe su nombre,
     sin `.html`, en "Archivo de la herramienta".)
   - Dirección de la página: `qr`
   Aparece sola en el menú, dentro de "Gratis".
3. **Texto para Google.** Lo que está dentro de la herramienta no lo lee bien el buscador. En el editor de la página
   (el cuerpo, debajo de la herramienta) pega dos o tres frases: qué hace, para quién es y que es gratis y funciona
   sin internet.

## Actualizar cuando salga una versión nueva

1. Sube la versión en `anyelo_qr/brand.py`.
2. Agrega arriba en `CHANGELOG.md` una sección `## 0.5.0 — 5 de noviembre de 2026` con una línea `- ` por cambio.
3. Sube los archivos a GitHub y corre el flujo (Actions, "Run workflow").

Listo. La página lee la última versión publicada y el `CHANGELOG.md` directamente de GitHub, así que cambia sola (la
primera vez que alguien la abre cada hora). Los enlaces de descarga apuntan siempre a "la última versión", por eso nunca
hay que tocarlos. No hace falta pegar la página de nuevo.

Si cambia el diseño del programa y quieres capturas nuevas: `python web/make_shots.py`, sube la carpeta `web/shots` a
GitHub y listo. Las capturas se actualizan solas (GitHub las guarda unos minutos en memoria).

Solo hay que pegar la página otra vez si cambias su texto o su diseño: `python web/build_page.py`.

## Si cambias el nombre del repositorio

GitHub deja las direcciones viejas funcionando, pero conviene actualizar la página: cambia la línea `REPO = ...` al inicio
de `build_page.py`, corre `python web/build_page.py` y pega la página otra vez.

## Si algo falla

- Con GitHub sin respuesta, la página muestra los datos con los que se armó (versión, fecha y novedades) y los
  botones siguen funcionando. Si GitHub no entrega las capturas, esos recuadros quedan vacíos.
- Para alojar los instaladores o las capturas en tu propio sitio, cambia `URL_INSTALADOR`, `URL_PORTABLE` o `IMG` al
  inicio del bloque `<script>` (dentro de «DATOS DE LA PÁGINA»).
- La demo de QR no necesita internet: todo se dibuja en el navegador de quien visita la página.
