"""Convierte una carpeta de imagenes en un PDF."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("imagenes-a-pdf")
except PackageNotFoundError:  # p. ej. dentro de un ejecutable de PyInstaller
    __version__ = "0.0.0"
