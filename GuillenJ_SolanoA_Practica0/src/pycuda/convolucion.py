"""Reserva de memoria y ejecución del kernel mediante PyCUDA."""
from typing import NamedTuple

import numpy as np
import pycuda.driver as cuda

from .contexto_cuda import kernel_convolucion


class TiemposGPU(NamedTuple):
    h2d: float
    kernel: float
    d2h: float
    total: float


def verificar_arreglo(arreglo, nombre):
    if arreglo.dtype != np.float32:
        raise TypeError(f"{nombre} debe ser float32, no {arreglo.dtype}")
    if not arreglo.flags.c_contiguous:
        raise TypeError(f"{nombre} debe ser contiguo")


def escalares_kernel(ancho, alto, k):
    return np.int32(ancho), np.int32(alto), np.int32(k)


def reservar_memoria_gpu(n, k):
    bytes_imagen = n * np.dtype(np.float32).itemsize
    bytes_mascara = k * k * np.dtype(np.float32).itemsize
    return (cuda.mem_alloc(bytes_imagen), cuda.mem_alloc(bytes_imagen),
            cuda.mem_alloc(bytes_mascara))


def liberar_memoria_gpu(*punteros):
    for puntero in punteros:
        puntero.free()


def ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida, d_mascara,
                 ancho, alto, k, hilos):
    """Mide H2D, kernel, D2H y total con eventos CUDA."""
    for arreglo, nombre in ((entrada, "entrada"), (salida, "salida"),
                            (mascara, "mascara")):
        verificar_arreglo(arreglo, nombre)
    bloques = (ancho * alto + hilos - 1) // hilos
    ancho_k, alto_k, k_k = escalares_kernel(ancho, alto, k)
    kernel = kernel_convolucion()
    e = [cuda.Event() for _ in range(4)]

    e[0].record()
    cuda.memcpy_htod(d_entrada, entrada)
    cuda.memcpy_htod(d_mascara, mascara)
    e[1].record()
    kernel(d_entrada, d_salida, d_mascara, ancho_k, alto_k, k_k,
           block=(hilos, 1, 1), grid=(bloques, 1))
    e[2].record()
    cuda.memcpy_dtoh(salida, d_salida)
    e[3].record()
    e[3].synchronize()

    return TiemposGPU(e[0].time_till(e[1]), e[1].time_till(e[2]),
                      e[2].time_till(e[3]), e[0].time_till(e[3]))


def calcular_gpu(entrada, mascara, ancho, alto, k, hilos,
                 salida_inicial=None):
    """Calcula una vez en GPU con una reserva temporal propia."""
    n = ancho * alto
    salida = np.empty(n, dtype=np.float32)
    d_entrada, d_salida, d_mascara = reservar_memoria_gpu(n, k)
    try:
        if salida_inicial is not None:
            cuda.memcpy_htod(d_salida, salida_inicial)
        ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida,
                     d_mascara, ancho, alto, k, hilos)
    finally:
        liberar_memoria_gpu(d_entrada, d_salida, d_mascara)
    return salida
