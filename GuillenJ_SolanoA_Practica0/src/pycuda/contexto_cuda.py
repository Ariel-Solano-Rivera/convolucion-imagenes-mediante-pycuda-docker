"""Contexto CUDA manual y carga del kernel con SourceModule, medidos aparte."""
import csv
import os
import time
import warnings
from datetime import datetime
from pathlib import Path

import pycuda.driver as cuda
from pycuda.compiler import SourceModule

from src.python.comun.configuracion import (ARQUITECTURA, KERNEL,
                                                       MEDICIONES, OPCIONES_NVCC)

NOMBRE_KERNEL = "convolucionGPU"
# nvcc (via cl.exe) solo imprime el nombre del archivo "kernel.cu"; no es un error.
warnings.filterwarnings("ignore", message="The CUDA compiler succeeded")
COLUMNAS_INICIALIZACION = ["fecha", "version", "etapa", "tiempo", "unidad", "uso_cache",
                           "observaciones"]

_activo = None  # entorno CUDA del proceso; se crea una sola vez


def _carpeta_cache():
    """Misma carpeta de cache que usa pycuda.compiler por defecto."""
    if "PYCUDA_CACHE_DIR" in os.environ:
        return Path(os.environ["PYCUDA_CACHE_DIR"])
    import platformdirs
    return Path(platformdirs.user_cache_dir("pycuda", "pycuda")) / "compiler-cache-v1"


def _ms(inicio):
    return (time.perf_counter() - inicio) * 1000.0


class EntornoCUDA:
    """Contexto creado a mano (sin pycuda.autoinit) y kernel compilado una sola vez."""

    def __init__(self):
        self.tiempos = []  # filas para inicializacion.csv

        # 1) Inicializacion del contexto.
        inicio = time.perf_counter()
        cuda.init()
        self.dispositivo = cuda.Device(0)
        self.contexto = self.dispositivo.make_context()
        self._anotar("contexto", _ms(inicio), "NA", "cuda.init + Device(0).make_context")

        codigo = KERNEL.read_text(encoding="utf-8")

        # 2) Compilacion real con nvcc (sin cache), con los flags de P01.
        inicio = time.perf_counter()
        SourceModule(codigo, options=OPCIONES_NVCC, arch=ARQUITECTURA, cache_dir=False)
        self._anotar("compilacion_sin_cache", _ms(inicio), "no",
                     f"nvcc {' '.join(OPCIONES_NVCC)} -arch {ARQUITECTURA}")

        # 3) Carga con la cache de PyCUDA (este es el modulo que se usa).
        cache = _carpeta_cache()
        antes = set(cache.glob("*.cubin")) if cache.exists() else set()
        inicio = time.perf_counter()
        self.modulo = SourceModule(codigo, options=OPCIONES_NVCC, arch=ARQUITECTURA)
        t_carga = _ms(inicio)
        uso_cache = "si" if set(cache.glob("*.cubin")) == antes else "no"
        self._anotar("carga_con_cache", t_carga, uso_cache,
                     "acierto de cache" if uso_cache == "si" else "primera vez: compilo y guardo")

        # 4) Obtencion de la funcion del kernel.
        inicio = time.perf_counter()
        self.kernel = self.modulo.get_function(NOMBRE_KERNEL)
        self._anotar("get_function", _ms(inicio), "NA", NOMBRE_KERNEL)

    def _anotar(self, etapa, tiempo, uso_cache, observaciones):
        self.tiempos.append({"fecha": datetime.now().isoformat(timespec="seconds"),
                             "version": "pycuda", "etapa": etapa, "tiempo": f"{tiempo:.4f}",
                             "unidad": "ms", "uso_cache": uso_cache,
                             "observaciones": observaciones})

    def registrar(self, ruta=None):
        """Agrega estos tiempos a inicializacion.csv (una vez por proceso)."""
        ruta = ruta or MEDICIONES / "inicializacion.csv"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not ruta.exists()
        with open(ruta, "a", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_INICIALIZACION)
            if nuevo:
                escritor.writeheader()
            escritor.writerows(self.tiempos)

    def cerrar(self):
        self.contexto.pop()


def inicializar_cuda():
    """Crea el contexto y carga el kernel la primera vez; despues reutiliza el mismo."""
    global _activo
    if _activo is None:
        _activo = EntornoCUDA()
    return _activo


def kernel_convolucion():
    if _activo is None:
        raise RuntimeError("Llame primero a inicializar_cuda()")
    return _activo.kernel


def cerrar_cuda():
    global _activo
    if _activo is not None:
        _activo.cerrar()
        _activo = None
