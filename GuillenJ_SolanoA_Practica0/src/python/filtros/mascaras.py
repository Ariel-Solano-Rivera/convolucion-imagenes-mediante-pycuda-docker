"""Declaraciones de las tres mascaras de convolucion."""
from .laplaciano import crear_mascara_laplaciano
from .media import crear_mascara_media
from .nitidez import crear_mascara_nitidez

__all__ = ["crear_mascara_media", "crear_mascara_nitidez", "crear_mascara_laplaciano"]
