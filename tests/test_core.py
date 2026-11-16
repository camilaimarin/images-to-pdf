import re
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from imagenes_a_pdf.cli import main
from imagenes_a_pdf.core import Opciones, buscar_imagenes, crear_pdf


def _crear_imagen(ruta: Path, tamano=(40, 30)) -> Path:
    Image.new("RGB", tamano, "red").save(ruta)
    return ruta


def _contar_paginas(pdf: Path) -> int:
    # Cuenta objetos "/Type /Page" (sin contar el "/Type /Pages" del indice).
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf.read_bytes()))


def test_orden_natural(tmp_path):
    for nombre in ["img10.png", "img2.png", "IMG1.png"]:
        _crear_imagen(tmp_path / nombre)
    nombres = [p.name for p in buscar_imagenes(tmp_path)]
    assert nombres == ["IMG1.png", "img2.png", "img10.png"]


def test_ignora_otros_archivos_y_ocultos(tmp_path):
    _crear_imagen(tmp_path / "a.jpg")
    (tmp_path / "notas.txt").write_text("hola")
    (tmp_path / "._a.jpg").write_bytes(b"basura de macOS")
    (tmp_path / "sub.png").mkdir()
    assert [p.name for p in buscar_imagenes(tmp_path)] == ["a.jpg"]


def test_carpeta_inexistente(tmp_path):
    with pytest.raises(NotADirectoryError):
        buscar_imagenes(tmp_path / "no-existe")


def test_lista_vacia(tmp_path):
    with pytest.raises(ValueError):
        crear_pdf([], tmp_path / "x.pdf")


def _tamanos_mm(pdf: Path) -> list[tuple[int, int]]:
    with pikepdf.open(pdf) as p:
        return [
            (round(float(pg.mediabox[2]) / 72 * 25.4), round(float(pg.mediabox[3]) / 72 * 25.4))
            for pg in p.pages
        ]


@pytest.mark.parametrize("papel", ["carta", "a4", "oficio", "original"])
def test_crea_pdf_cada_papel(tmp_path, papel):
    imagenes = [_crear_imagen(tmp_path / f"{i}.png") for i in range(3)]
    salida = tmp_path / "out.pdf"
    assert crear_pdf(imagenes, salida, Opciones(papel=papel)) == 3
    assert salida.read_bytes().startswith(b"%PDF")
    assert _contar_paginas(salida) == 3


def test_carta_por_defecto(tmp_path):
    salida = tmp_path / "out.pdf"
    crear_pdf([_crear_imagen(tmp_path / "a.png", (60, 130))], salida)
    assert _tamanos_mm(salida) == [(216, 279)]


def test_original_respeta_tamano_imagen(tmp_path):
    ruta = tmp_path / "a.png"
    Image.new("RGB", (720, 360), "red").save(ruta, dpi=(72, 72))  # 10 x 5 pulgadas
    salida = tmp_path / "out.pdf"
    crear_pdf([ruta], salida, Opciones(papel="original"))
    assert _tamanos_mm(salida) == [(254, 127)]


@pytest.mark.parametrize("n, total, paginas", [(2, 5, 3), (4, 5, 2), (6, 6, 1)])
def test_varias_por_hoja(tmp_path, n, total, paginas):
    imagenes = [_crear_imagen(tmp_path / f"{i}.png", (60, 130)) for i in range(total)]
    salida = tmp_path / "out.pdf"
    assert crear_pdf(imagenes, salida, Opciones(por_hoja=n)) == paginas
    assert _contar_paginas(salida) == paginas


@pytest.mark.parametrize(
    "tamano, por_hoja, esperado",
    [
        ((300, 100), 1, (279, 216)),  # foto horizontal -> hoja horizontal
        ((100, 300), 1, (216, 279)),  # foto vertical -> hoja vertical
        ((60, 130), 2, (216, 279)),   # 2 capturas altas -> lado a lado en vertical
        ((200, 100), 2, (216, 279)),  # 2 fotos 2:1 -> una arriba de otra en vertical
    ],
)
def test_orientacion_auto(tmp_path, tamano, por_hoja, esperado):
    imagenes = [_crear_imagen(tmp_path / f"{i}.png", tamano) for i in range(por_hoja)]
    salida = tmp_path / "out.pdf"
    crear_pdf(imagenes, salida, Opciones(por_hoja=por_hoja))
    assert _tamanos_mm(salida) == [esperado]


def test_orientacion_forzada(tmp_path):
    salida = tmp_path / "out.pdf"
    crear_pdf([_crear_imagen(tmp_path / "a.png", (300, 100))], salida, Opciones(orientacion="vertical"))
    assert _tamanos_mm(salida) == [(216, 279)]


def test_png_con_transparencia(tmp_path):
    ruta = tmp_path / "alfa.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(ruta)
    salida = tmp_path / "out.pdf"
    assert crear_pdf([ruta], salida) == 1


def test_foto_rotada_por_exif(tmp_path):
    # Foto guardada "acostada" (200x100) con EXIF que dice "girala 90 grados",
    # como hacen los celulares. Visualmente es vertical: debe ir en hoja vertical.
    ruta = tmp_path / "rotada.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (200, 100), "blue").save(ruta, exif=exif)
    salida = tmp_path / "out.pdf"
    crear_pdf([ruta], salida)
    assert _tamanos_mm(salida) == [(216, 279)]


def test_opciones_invalidas():
    with pytest.raises(ValueError):
        Opciones(papel="servilleta")
    with pytest.raises(ValueError):
        Opciones(por_hoja=3)
    with pytest.raises(ValueError):
        Opciones(papel="original", por_hoja=2)


def test_cli_no_sobrescribe_sin_forzar(tmp_path):
    _crear_imagen(tmp_path / "a.png")
    salida = tmp_path / "out.pdf"
    salida.write_text("existente")
    assert main([str(tmp_path), str(salida)]) == 1
    assert salida.read_text() == "existente"
    assert main([str(tmp_path), str(salida), "--forzar"]) == 0
    assert salida.read_bytes().startswith(b"%PDF")
