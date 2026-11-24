"""Errores de dominio que se convierten en respuestas HTTP claras.

Cada error lleva un código estable (campo ``codigo`` del JSON) y el estado HTTP con
que se responde, para que la interfaz y los scripts distingan la causa.
"""


class ErrorServicio(Exception):
    codigo = "error_servicio"
    http = 500


class EntradaInvalida(ErrorServicio, ValueError):
    """La imagen o los parámetros de la solicitud no son válidos."""
    codigo = "entrada_invalida"
    http = 400


class ColaGPULlena(ErrorServicio, RuntimeError):
    """El límite de trabajos en ejecución y espera fue alcanzado."""
    codigo = "cola_llena"
    http = 429


class GPUNoDisponible(ErrorServicio, RuntimeError):
    """PyCUDA, el controlador o la GPU no están disponibles (sin respaldo en CPU)."""
    codigo = "gpu_no_disponible"
    http = 503


class MemoriaGPUInsuficiente(ErrorServicio, RuntimeError):
    """cuda.mem_alloc no pudo reservar la memoria que requiere la imagen."""
    codigo = "memoria_gpu_insuficiente"
    http = 503


class MemoriaServidorInsuficiente(ErrorServicio, RuntimeError):
    """El anfitrión no tuvo RAM para decodificar o preparar la imagen."""
    codigo = "memoria_servidor_insuficiente"
    http = 503


class ErrorProcesamientoGPU(ErrorServicio, RuntimeError):
    """Fallo del kernel, de una transferencia o de la sincronización."""
    codigo = "error_procesamiento_gpu"
    http = 500
