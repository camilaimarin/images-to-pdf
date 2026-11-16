"""
Logica principal: buscar imagenes y acomodarlas en un PDF.

Este modulo no imprime nada ni lee argumentos de la terminal. Solo recibe
datos y devuelve resultados (o lanza excepciones). Asi lo pueden usar por
igual la linea de comandos (cli.py) y, mas adelante, una interfaz grafica.

Como funciona:
  1. img2pdf convierte cada imagen en un PDF de una pagina. Los JPEG y PNG
     entran tal cual, sin recomprimirse, asi que no pierden calidad.
  2. pikepdf toma esas paginas y las coloca, escaladas, dentro de hojas de
     tamano estandar (Carta, A4...), una o varias por hoja en cuadricula.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import img2pdf
import pikepdf
from PIL import Image

# Extensiones que aceptamos.
EXTENSIONES = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp"})


def _mm(valor: float) -> float:
    """Milimetros a puntos PDF (1 pt = 1/72 de pulgada)."""
    return valor * 72 / 25.4


# Tamanos de hoja en mm (ancho, alto) en vertical.
PAPELES: dict[str, tuple[float, float]] = {
    "carta": (215.9, 279.4),
    "a4": (210.0, 297.0),
    "oficio": (215.9, 340.0),  # oficio mexicano
}
# "original" no es una hoja: cada pagina toma el tamano de su imagen.
PAPEL_ORIGINAL = "original"

POR_HOJA_VALIDOS = (1, 2, 4, 6)
ORIENTACIONES = ("auto", "vertical", "horizontal")


@dataclass(frozen=True)
class Opciones:
    papel: str = "carta"
    por_hoja: int = 1
    orientacion: str = "auto"
    margen_mm: float = 10.0
    separacion_mm: float = 5.0

    def __post_init__(self):
        if self.papel not in PAPELES and self.papel != PAPEL_ORIGINAL:
            raise ValueError(f"Papel desconocido: {self.papel}")
        if self.por_hoja not in POR_HOJA_VALIDOS:
            raise ValueError(f"por_hoja debe ser uno de {POR_HOJA_VALIDOS}")
        if self.orientacion not in ORIENTACIONES:
            raise ValueError(f"orientacion debe ser una de {ORIENTACIONES}")
        if self.papel == PAPEL_ORIGINAL and self.por_hoja != 1:
            raise ValueError("Con papel 'original' solo cabe una imagen por pagina.")


# ---------------------------------------------------------------- busqueda


def clave_orden_natural(ruta: Path) -> list:
    """
    Clave para ordenar nombres como lo haria una persona.

    El orden alfabetico normal pone 'img10' antes de 'img2'. Partimos el
    nombre en trozos de texto y de numero, y convertimos los numeros a int,
    asi que 'img2' queda antes de 'img10'.
    """
    partes = re.split(r"(\d+)", ruta.name.lower())
    return [int(p) if p.isdigit() else p for p in partes]


def buscar_imagenes(carpeta: Path) -> list[Path]:
    """Devuelve las imagenes de la carpeta (sin subcarpetas), ya ordenadas."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise NotADirectoryError(f"No existe la carpeta: {carpeta}")

    encontradas = [
        archivo
        for archivo in carpeta.iterdir()
        if archivo.is_file()
        and archivo.suffix.lower() in EXTENSIONES
        and not archivo.name.startswith(".")  # ignora ocultos como ._foto.jpg de macOS
    ]
    encontradas.sort(key=clave_orden_natural)
    return encontradas


# ---------------------------------------------------------------- imagenes


def _imagen_a_pdf(ruta: Path) -> bytes:
    """
    Convierte una imagen a un PDF de una pagina del tamano de la imagen.

    img2pdf se niega a meter imagenes con transparencia (PDF las trataria
    distinto segun el visor). En ese caso la aplanamos sobre fondo blanco,
    que es como se veria impresa.
    """
    try:
        return img2pdf.convert(str(ruta))
    except img2pdf.AlphaChannelError:
        with Image.open(ruta) as im:
            im = im.convert("RGBA")
            fondo = Image.new("RGB", im.size, "white")
            fondo.paste(im, mask=im.getchannel("A"))
            buffer = io.BytesIO()
            fondo.save(buffer, format="PNG", dpi=im.info.get("dpi", (96, 96)))
        return img2pdf.convert(buffer.getvalue())


def _tamano_visible(pagina: pikepdf.Page) -> tuple[float, float]:
    """Ancho y alto de la pagina tal como se ve (respetando /Rotate de EXIF)."""
    caja = pagina.mediabox
    ancho, alto = float(caja[2]) - float(caja[0]), float(caja[3]) - float(caja[1])
    if int(pagina.obj.get("/Rotate", 0)) % 180:
        ancho, alto = alto, ancho
    return ancho, alto


# ---------------------------------------------------------------- acomodo


def _cuadriculas(n: int) -> list[tuple[int, int]]:
    """Formas posibles (columnas, filas) de acomodar n imagenes."""
    return [(c, n // c) for c in range(1, n + 1) if n % c == 0]


def _escala_cuadricula(
    proporciones: list[float], hoja: tuple[float, float], cols: int, filas: int, opc: Opciones
) -> float:
    """
    Que tan grandes quedarian las imagenes con esta cuadricula: suma del area
    que ocupa cada una dentro de su celda. Mas alto es mejor.
    """
    margen, sep = _mm(opc.margen_mm), _mm(opc.separacion_mm)
    celda_w = (hoja[0] - 2 * margen - (cols - 1) * sep) / cols
    celda_h = (hoja[1] - 2 * margen - (filas - 1) * sep) / filas
    if celda_w <= 0 or celda_h <= 0:
        return 0.0
    area = 0.0
    for p in proporciones:  # p = ancho / alto de la imagen
        w = min(celda_w, celda_h * p)
        area += w * (w / p)
    return area


def _elegir_hoja_y_cuadricula(
    proporciones: list[float], opc: Opciones
) -> tuple[tuple[float, float], int, int]:
    """Elige orientacion y cuadricula que dejan las imagenes mas grandes."""
    ancho_mm, alto_mm = PAPELES[opc.papel]
    vertical = (_mm(ancho_mm), _mm(alto_mm))
    horizontal = (vertical[1], vertical[0])
    hojas = {"vertical": [vertical], "horizontal": [horizontal]}.get(
        opc.orientacion, [vertical, horizontal]
    )
    candidatos = [
        (_escala_cuadricula(proporciones, hoja, c, f, opc), hoja, c, f)
        for hoja in hojas
        for c, f in _cuadriculas(opc.por_hoja)
    ]
    # max() se queda con el primero en caso de empate: vertical gana.
    _, hoja, cols, filas = max(candidatos, key=lambda x: x[0])
    return hoja, cols, filas


def _celdas(hoja: tuple[float, float], cols: int, filas: int, opc: Opciones):
    """Rectangulos de cada celda, de izquierda a derecha y de arriba abajo."""
    margen, sep = _mm(opc.margen_mm), _mm(opc.separacion_mm)
    celda_w = (hoja[0] - 2 * margen - (cols - 1) * sep) / cols
    celda_h = (hoja[1] - 2 * margen - (filas - 1) * sep) / filas
    for f in range(filas):
        for c in range(cols):
            x = margen + c * (celda_w + sep)
            # En PDF el eje Y crece hacia arriba, asi que la fila 0 va al tope.
            y = hoja[1] - margen - (f + 1) * celda_h - f * sep
            yield pikepdf.Rectangle(x, y, x + celda_w, y + celda_h)


# ---------------------------------------------------------------- principal


def crear_pdf(imagenes: list[Path], salida: Path, opciones: Opciones | None = None) -> int:
    """
    Escribe el PDF y devuelve cuantas paginas tiene.

    Con papel 'original' cada pagina mide lo mismo que su imagen. Con una hoja
    estandar, las imagenes se acomodan centradas, sin recortarse, de
    `opciones.por_hoja` en `opciones.por_hoja`.
    """
    opc = opciones or Opciones()
    if not imagenes:
        raise ValueError("La lista de imagenes esta vacia, no hay nada que convertir.")

    salida_pdf = pikepdf.new()
    fuentes = []  # mantenemos abiertos los PDF de cada imagen hasta guardar
    for inicio in range(0, len(imagenes), opc.por_hoja):
        grupo = imagenes[inicio : inicio + opc.por_hoja]
        paginas = []
        for ruta in grupo:
            fuente = pikepdf.open(io.BytesIO(_imagen_a_pdf(ruta)))
            fuentes.append(fuente)
            paginas.append(fuente.pages[0])

        if opc.papel == PAPEL_ORIGINAL:
            # La pagina de img2pdf ya mide lo mismo que la imagen: se copia tal cual.
            salida_pdf.pages.append(paginas[0])
            continue

        proporciones = [w / h for w, h in map(_tamano_visible, paginas)]
        hoja, cols, filas = _elegir_hoja_y_cuadricula(proporciones, opc)

        salida_pdf.add_blank_page(page_size=hoja)
        hoja_pdf = salida_pdf.pages[-1]
        for pagina, celda in zip(paginas, _celdas(hoja, cols, filas, opc)):
            # add_overlay escala la imagen para que quepa en la celda,
            # conservando su proporcion y centrandola.
            hoja_pdf.add_overlay(pagina, celda)

    # Igual que antes: si algo falla arriba, no dejamos un PDF a medias.
    buffer = io.BytesIO()
    salida_pdf.save(buffer)
    for fuente in fuentes:
        fuente.close()
    Path(salida).write_bytes(buffer.getvalue())
    return len(salida_pdf.pages)
