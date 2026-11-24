"""Procesamiento completo de una imagen, independiente de HTTP.

La API (``api.py``) y la ejecución directa (``scripts/experimentos.py`` y
``scripts/validar_servicio.py``) llaman a esta misma función, de modo que lo que se
compara entre «PyCUDA directo» y «servicio» es exactamente el mismo procesamiento.

Fases cronometradas con ``time.perf_counter`` (reloj monotónico de alta resolución):
- ``decodificacion_y_preparacion``: validación del formato real, decodificación,
  escala de grises, recorte/redimensión si corresponde y conversión a float32 contiguo.
- ``espera_gpu``: desde que el trabajo entra a la cola hasta que el trabajador CUDA lo toma.
- ``reserva_liberacion``: ``cuda.mem_alloc`` + ``free`` de entrada, salida y máscara.
- ``cpu_a_gpu``, ``kernel``, ``gpu_a_cpu``, ``gpu_total``: eventos CUDA (práctica 02).
- ``codificacion_y_escritura``: PNG de la entrada preparada, ``resultado.npy`` (float32
  antes del recorte, para validar) y ``resultado.png`` (recorte 0–255; laplaciano abs×4).
- ``procesamiento_total``: de la decodificación a la escritura, ambas incluidas.
"""
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np

from .errores import MemoriaServidorInsuficiente
from .filtros import crear_mascara, validar_filtro_y_mascara
from .imagenes import ImagenPreparada, guardar_resultado, preparar_imagen_subida
from .procesador_gpu import ResultadoGPU


@dataclass(frozen=True)
class ResultadoProcesamiento:
    filtro: str
    mascara: int
    preparada: ImagenPreparada
    gpu: ResultadoGPU
    tiempos_ms: dict


def _ms(inicio, fin):
    return (fin - inicio) * 1000.0


def procesar_imagen(contenido, filtro, mascara, procesador, carpeta,
                    max_pixeles, max_pixeles_entrada):
    """Decodifica ``contenido`` (bytes), convoluciona en GPU y escribe en ``carpeta``."""
    filtro, mascara = validar_filtro_y_mascara(filtro, mascara)
    inicio = time.perf_counter()
    try:
        preparada = preparar_imagen_subida(BytesIO(contenido), max_pixeles, max_pixeles_entrada)
    except MemoryError as error:
        raise MemoriaServidorInsuficiente(
            "El servidor no tuvo memoria para decodificar la imagen.") from error
    fin_decodificacion = time.perf_counter()

    resultado = procesador.procesar(preparada.datos, crear_mascara(filtro, mascara),
                                    preparada.ancho, preparada.alto, mascara)
    fin_gpu = time.perf_counter()

    carpeta = Path(carpeta)
    preparada.visible.save(carpeta / "original.png", format="PNG")
    np.save(carpeta / "resultado.npy", resultado.datos.astype(np.float32, copy=False),
            allow_pickle=False)
    guardar_resultado(carpeta / "resultado.png", resultado.datos, preparada.ancho,
                      preparada.alto, laplaciano=filtro == "laplaciano")
    fin = time.perf_counter()

    tiempos = {
        "decodificacion_y_preparacion": _ms(inicio, fin_decodificacion),
        "espera_gpu": resultado.espera_ms,
        "reserva_liberacion": resultado.reserva_liberacion_ms,
        "cpu_a_gpu": resultado.h2d_ms,
        "kernel": resultado.kernel_ms,
        "gpu_a_cpu": resultado.d2h_ms,
        "gpu_total": resultado.total_gpu_ms,
        # Llamada completa al trabajador: espera + (arranque en frío) + reserva + GPU.
        "trabajador_gpu": _ms(fin_decodificacion, fin_gpu),
        "codificacion_y_escritura": _ms(fin_gpu, fin),
        "procesamiento_total": _ms(inicio, fin),
        "inicio_frio": resultado.inicio_frio_ms,
    }
    return ResultadoProcesamiento(filtro, mascara, preparada, resultado, tiempos)
