"""Interfaz de linea de comandos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import (
    EXTENSIONES,
    ORIENTACIONES,
    PAPEL_ORIGINAL,
    PAPELES,
    POR_HOJA_VALIDOS,
    Opciones,
    buscar_imagenes,
    crear_pdf,
)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagenes-a-pdf",
        description="Junta todas las imagenes de una carpeta en un PDF, una por pagina.",
    )
    parser.add_argument("carpeta", type=Path, help="carpeta con las imagenes")
    parser.add_argument("salida", type=Path, help="archivo PDF a crear")
    parser.add_argument(
        "-p", "--papel",
        choices=[*PAPELES, PAPEL_ORIGINAL],
        default="carta",
        help="tamano de hoja (por defecto: carta). 'original' = cada pagina del tamano de su imagen",
    )
    parser.add_argument(
        "-n", "--por-hoja",
        type=int,
        choices=POR_HOJA_VALIDOS,
        default=1,
        help="cuantas imagenes acomodar en cada hoja (por defecto: 1)",
    )
    parser.add_argument(
        "-o", "--orientacion",
        choices=ORIENTACIONES,
        default="auto",
        help="orientacion de la hoja (por defecto: auto, la que deja las imagenes mas grandes)",
    )
    parser.add_argument(
        "--margen",
        type=float,
        default=10.0,
        metavar="MM",
        help="margen de la hoja en milimetros (por defecto: 10)",
    )
    parser.add_argument(
        "-f", "--forzar",
        action="store_true",
        help="sobrescribir el PDF de salida si ya existe",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    try:
        opciones = Opciones(
            papel=args.papel,
            por_hoja=args.por_hoja,
            orientacion=args.orientacion,
            margen_mm=args.margen,
        )
    except ValueError as e:
        parser.error(str(e))  # imprime el uso y sale con codigo 2

    try:
        imagenes = buscar_imagenes(args.carpeta)
    except NotADirectoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not imagenes:
        print(f"No encontre imagenes en {args.carpeta}", file=sys.stderr)
        print(f"Extensiones que busco: {', '.join(sorted(EXTENSIONES))}", file=sys.stderr)
        return 1

    if args.salida.exists() and not args.forzar:
        print(f"Error: {args.salida} ya existe. Usa --forzar para sobrescribirlo.", file=sys.stderr)
        return 1

    print(f"Encontre {len(imagenes)} imagenes:")
    for i, ruta in enumerate(imagenes, start=1):
        print(f"  {i:>3}. {ruta.name}")

    print(f"\nCreando {args.salida} ...")
    try:
        paginas = crear_pdf(imagenes, args.salida, opciones)
    except Exception as e:
        print(f"Error al crear el PDF: {e}", file=sys.stderr)
        return 1

    tamano_mb = args.salida.stat().st_size / 1_000_000
    print(f"Listo. {args.salida} ({tamano_mb:.1f} MB, {paginas} paginas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
