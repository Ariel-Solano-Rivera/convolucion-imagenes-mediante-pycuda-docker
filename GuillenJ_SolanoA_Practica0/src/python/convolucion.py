"""Convolución secuencial Python, máscaras y comparación numérica."""
import time

import numpy as np

from src.python.comun.configuracion import Filtro
from .filtros.mascaras import (crear_mascara_laplaciano, crear_mascara_media,
                               crear_mascara_nitidez)


class TiempoExcedido(Exception):
    """La convolución secuencial superó el límite configurado."""

    def __init__(self, transcurrido, filas_procesadas, limite):
        self.transcurrido = transcurrido
        self.filas_procesadas = filas_procesadas
        self.limite = limite
        super().__init__(f"límite de {limite:.0f} s excedido tras "
                         f"{transcurrido:.1f} s ({filas_procesadas} filas)")


def crear_mascara(filtro, k):
    if filtro == Filtro.MEDIA:
        return crear_mascara_media(k)
    if filtro == Filtro.NITIDEZ:
        return crear_mascara_nitidez()
    return crear_mascara_laplaciano()


def convolucion_cpu(entrada, salida, mascara, ancho, alto, k,
                    limite_segundos=None):
    """Port literal del recorrido CPU de P01 con acumulación float32."""
    radio = k // 2
    datos = list(entrada)
    coeficientes = list(mascara)
    cero = np.float32(0)
    inicio = time.perf_counter()

    for y in range(alto):
        if limite_segundos is not None:
            transcurrido = time.perf_counter() - inicio
            if transcurrido > limite_segundos:
                raise TiempoExcedido(transcurrido, y, limite_segundos)
        for x in range(ancho):
            suma = cero
            for j in range(-radio, radio + 1):
                for i in range(-radio, radio + 1):
                    yy, xx = y + j, x + i
                    if 0 <= yy < alto and 0 <= xx < ancho:
                        suma += datos[yy * ancho + xx] * \
                                coeficientes[(j + radio) * k + i + radio]
            salida[y * ancho + x] = suma


def ejecutar_cpu(entrada, salida, mascara, ancho, alto, k,
                 limite_segundos=None):
    """Mide solo la convolución secuencial, en milisegundos."""
    inicio = time.perf_counter()
    convolucion_cpu(entrada, salida, mascara, ancho, alto, k,
                    limite_segundos)
    return (time.perf_counter() - inicio) * 1000.0


UNIDAD_REDONDEO = float(np.finfo(np.float32).eps) / 2
MAXIMO_PIXEL = 255.0


def tolerancia(mascara):
    """Cota de error de float32 para un producto punto de k*k términos."""
    n = mascara.size
    gamma = n * UNIDAD_REDONDEO / (1 - n * UNIDAD_REDONDEO)
    suma_abs = MAXIMO_PIXEL * float(np.abs(mascara.astype(np.float64)).sum())
    return 2 * gamma * suma_abs


def comparar(referencia, otra):
    """Devuelve error absoluto máximo y medio antes del recorte visual."""
    error = np.abs(referencia.astype(np.float32, copy=False) -
                   otra.astype(np.float32, copy=False))
    return float(error.max()), float(error.mean(dtype=np.float64))
