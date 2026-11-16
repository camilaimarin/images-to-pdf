# imagenes-a-pdf

Junta todas las imágenes de una carpeta en un solo PDF, una imagen por página.

- Ordena los archivos como lo haría una persona: `foto2` va antes de `foto10`.
- JPEG y PNG entran sin recomprimirse, así que no pierden calidad.
- Hojas listas para imprimir (Carta, A4 u Oficio), con una o varias imágenes por hoja.
- Elige sola la orientación de la hoja que deja las imágenes más grandes.
- Respeta la rotación de las fotos de celular y aplana los PNG con transparencia sobre blanco.

Formatos aceptados: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.gif`, `.bmp`.

## Uso

Necesitas [uv](https://docs.astral.sh/uv/).

```bash
git clone <url-del-repo>
cd images-to-pdf
uv run imagenes-a-pdf ~/Desktop/mis_fotos album.pdf
```

Ejemplos:

```bash
# Hojas Carta, una imagen por hoja (lo predeterminado)
uv run imagenes-a-pdf mis_fotos album.pdf

# Dos capturas por hoja en A4
uv run imagenes-a-pdf mis_fotos album.pdf --papel a4 --por-hoja 2

# Cada página del tamaño exacto de su imagen (para ver en pantalla, no imprimir)
uv run imagenes-a-pdf mis_fotos album.pdf --papel original
```

Opciones:

| Opción | Qué hace |
| --- | --- |
| `-p`, `--papel` | `carta` (predeterminado), `a4`, `oficio` u `original` |
| `-n`, `--por-hoja` | Imágenes por hoja: `1` (predeterminado), `2`, `4` o `6` |
| `-o`, `--orientacion` | `auto` (predeterminado), `vertical` u `horizontal` |
| `--margen MM` | Margen de la hoja en milímetros (predeterminado: 10) |
| `-f`, `--forzar` | Sobrescribe el PDF de salida si ya existe |
| `--version` | Muestra la versión |
| `-h`, `--help` | Muestra la ayuda |

## Desarrollo

```bash
uv sync          # crea .venv e instala dependencias
uv run pytest    # corre las pruebas
```

Estructura:

```
src/imagenes_a_pdf/
  core.py      # lógica: buscar imágenes y acomodarlas en hojas (no imprime nada)
  cli.py       # interfaz de línea de comandos
  __main__.py  # permite `python -m imagenes_a_pdf`
tests/         # pruebas con pytest
```

`core.py` no depende de la terminal, así que una interfaz gráfica puede usarlo directamente.

## Hoja de ruta

- [x] Línea de comandos
- [ ] Interfaz gráfica
- [ ] Aplicación descargable para macOS y Windows (PyInstaller + GitHub Releases)
