"""Parámetros permitidos y máscaras idénticas a las de la práctica 02."""
import numpy as np

from .errores import EntradaInvalida

FILTROS = ("media", "nitidez", "laplaciano")
MASCARAS_MEDIA = (3, 9, 21)


def validar_filtro_y_mascara(filtro, mascara):
    filtro = (filtro or "").strip().lower()
    if filtro not in FILTROS:
        raise EntradaInvalida("El filtro debe ser media, nitidez o laplaciano.")
    try:
        mascara = int(mascara) if mascara is not None else 3
    except (TypeError, ValueError) as error:
        raise EntradaInvalida("El tamaño de máscara debe ser un entero.") from error
    if filtro == "media" and mascara not in MASCARAS_MEDIA:
        raise EntradaInvalida("Para media se permiten máscaras 3, 9 o 21.")
    if filtro != "media" and mascara != 3:
        raise EntradaInvalida(f"{filtro} usa únicamente máscara 3×3.")
    return filtro, mascara


def crear_mascara(filtro, mascara):
    """Conserva los coeficientes y precisión float32 de la práctica 02."""
    if filtro == "media":
        valor = np.float32(1.0) / np.float32(mascara * mascara)
        return np.full(mascara * mascara, valor, dtype=np.float32)
    if filtro == "nitidez":
        return np.array([0, -1, 0, -1, 5, -1, 0, -1, 0], dtype=np.float32)
    return np.array([0, 1, 0, 1, -4, 1, 0, 1, 0], dtype=np.float32)

