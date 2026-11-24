"""Un único trabajador CUDA: una sola cola y contexto creado en su propio hilo.

Ciclo de vida (lo exige la guía):
- Contexto: se crea manualmente (sin pycuda.autoinit) la primera vez que el trabajador
  atiende un trabajo, mediante ``inicializar_cuda`` de la práctica 02, que también compila o
  carga desde caché el kernel con ``SourceModule``. Ese tiempo se informa una sola vez como
  ``inicio_frio_ms`` y queda fuera de las mediciones estables.
- Todas las llamadas CUDA ocurren en el mismo hilo (``ThreadPoolExecutor`` de 1 trabajador),
  por lo que el contexto nunca se comparte entre hilos.
- Memoria: por solicitud se reservan entrada, salida y máscara con ``cuda.mem_alloc`` y se
  liberan en ``finally``; su tiempo se mide aparte (``reserva_liberacion_ms``).
- Transferencias síncronas desde memoria paginable de NumPy (``memcpy_htod``/``memcpy_dtoh``)
  y eventos CUDA con ``synchronize`` antes de leer el resultado (código de la práctica 02).
- Si falla el kernel o una transferencia, el contexto se descarta y se vuelve a crear en la
  siguiente solicitud. No existe ejecución sustituta en CPU.
"""
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .errores import (ColaGPULlena, ErrorProcesamientoGPU, ErrorServicio, GPUNoDisponible,
                      MemoriaGPUInsuficiente, MemoriaServidorInsuficiente)


@dataclass(frozen=True)
class ResultadoGPU:
    datos: np.ndarray
    h2d_ms: float
    kernel_ms: float
    d2h_ms: float
    total_gpu_ms: float
    espera_ms: float
    inicio_frio_ms: float | None
    reserva_liberacion_ms: float = 0.0
    memoria_reservada_bytes: int = 0
    memoria_gpu_usada_bytes: int | None = None
    memoria_gpu_total_bytes: int | None = None
    bloques: int = 0
    hilos: int = 0


def bytes_requeridos(n, k):
    """Entrada y salida float32 de n píxeles más la máscara k×k float32."""
    return 2 * n * 4 + k * k * 4


def _es_memoria_cuda(error):
    try:
        import pycuda.driver as cuda
    except Exception:  # pylint: disable=broad-except
        return "out of memory" in str(error).lower()
    return isinstance(error, cuda.MemoryError) or "out of memory" in str(error).lower()


class ServicioGPU:
    """Serializa PyCUDA; el segundo trabajo espera y no comparte contexto indebidamente."""

    # El contexto de la práctica 02 es único por proceso: solo un trabajador puede usarlo.
    _propietario = None
    _candado_propietario = threading.Lock()

    def __init__(self, practica02, hilos, limite_trabajos=2):
        self._practica02_raiz = Path(practica02)
        self._hilos = hilos
        self._cupos = threading.BoundedSemaphore(limite_trabajos)
        self._limite = limite_trabajos
        self._ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cuda")
        self._practica02 = None
        self._modulo_contexto = None
        self._inicio_frio_registrado = False
        self._diagnostico = None

    # ------------------------------------------------------------------ API pública
    def procesar(self, entrada, mascara, ancho, alto, k):
        if not self._cupos.acquire(blocking=False):
            raise ColaGPULlena("La GPU tiene el máximo de solicitudes pendientes. Intente de nuevo.")
        enviado = time.perf_counter()
        try:
            futuro = self._ejecutor.submit(self._procesar_en_hilo_cuda,
                                           entrada, mascara, ancho, alto, k, enviado)
            return futuro.result()
        except ErrorServicio:
            raise
        except Exception as error:  # pylint: disable=broad-except
            raise ErrorProcesamientoGPU(f"Error inesperado al procesar en GPU: {error}") from error
        finally:
            self._cupos.release()

    def diagnosticar(self):
        """Comprueba controlador, dispositivo y código de P02 sin crear el contexto."""
        if self._diagnostico is None:
            self._diagnostico = self._ejecutor.submit(self._diagnosticar_en_hilo).result()
        return dict(self._diagnostico, contexto_creado=self._inicio_frio_registrado,
                    politica="1 trabajador CUDA; máximo "
                             f"{self._limite} solicitudes entre ejecución y espera; "
                             "el resto recibe HTTP 429")

    def cerrar(self):
        """Libera el contexto en el mismo hilo que lo creó."""
        if self._practica02 is not None and self._inicio_frio_registrado:
            self._ejecutor.submit(self._cerrar_en_hilo_cuda).result()
        self._ejecutor.shutdown(wait=True)

    # ------------------------------------------------------- dentro del hilo CUDA
    def _cargar_practica02(self):
        if self._practica02 is not None:
            return self._practica02
        if not self._practica02_raiz.is_dir():
            raise GPUNoDisponible(f"No existe la práctica 02 en {self._practica02_raiz}.")
        ruta_texto = str(self._practica02_raiz)
        if ruta_texto not in sys.path:
            sys.path.insert(0, ruta_texto)
        try:
            import src.pycuda.contexto_cuda as modulo_contexto
            from src.pycuda.convolucion import ejecutar_gpu, liberar_memoria_gpu, reservar_memoria_gpu
        except ImportError as error:
            raise GPUNoDisponible(
                "No se pudo importar PyCUDA o el código de la práctica 02 "
                f"(¿falta libcuda / el contenedor se inició sin --gpus?): {error}") from error
        except Exception as error:  # pylint: disable=broad-except
            raise GPUNoDisponible(f"PyCUDA no pudo cargarse: {error}") from error
        self._modulo_contexto = modulo_contexto
        self._practica02 = (modulo_contexto.inicializar_cuda, modulo_contexto.cerrar_cuda,
                            ejecutar_gpu, liberar_memoria_gpu, reservar_memoria_gpu)
        return self._practica02

    def _diagnosticar_en_hilo(self):
        try:
            import pycuda
            import pycuda.driver as cuda
        except Exception as error:  # pylint: disable=broad-except
            raise GPUNoDisponible(
                f"PyCUDA no puede cargarse (controlador o libcuda ausente): {error}") from error
        try:
            cuda.init()
            cantidad = cuda.Device.count()
        except Exception as error:  # pylint: disable=broad-except
            raise GPUNoDisponible(f"El controlador CUDA no responde: {error}") from error
        if cantidad < 1:
            raise GPUNoDisponible("No hay ninguna GPU NVIDIA visible para el proceso.")
        dispositivo = cuda.Device(0)
        kernel = self._practica02_raiz / "src" / "pycuda" / "kernels" / "convolucion.cu"
        if not kernel.is_file():
            raise GPUNoDisponible(f"No existe el kernel propio en {kernel}.")
        version = cuda.get_driver_version()
        return {
            "gpu": dispositivo.name(),
            "compute_capability": "%d.%d" % dispositivo.compute_capability(),
            "memoria_total_mb": round(dispositivo.total_memory() / 2**20, 1),
            "cuda_controlador": f"{version // 1000}.{(version % 1000) // 10}",
            "pycuda": pycuda.VERSION_TEXT,
            "kernel": str(kernel),
            "hilos_por_bloque": self._hilos,
        }

    @staticmethod
    def _memoria_gpu():
        """(libre, total) del dispositivo con las reservas de la solicitud ya hechas."""
        try:
            import pycuda.driver as cuda
            return cuda.mem_get_info()
        except Exception:  # pylint: disable=broad-except
            return None, None

    def _reiniciar_contexto(self):
        """Descarta un contexto que pudo quedar inválido tras un error del kernel."""
        try:
            self._practica02[1]()
        except Exception:  # pylint: disable=broad-except
            pass
        if self._modulo_contexto is not None:
            self._modulo_contexto._activo = None  # pylint: disable=protected-access
        self._liberar_propiedad()

    def _liberar_propiedad(self):
        self._inicio_frio_registrado = False
        with ServicioGPU._candado_propietario:
            if ServicioGPU._propietario is self:
                ServicioGPU._propietario = None

    def _procesar_en_hilo_cuda(self, entrada, mascara, ancho, alto, k, enviado):
        # La espera termina cuando el trabajador toma el trabajo; la importación de PyCUDA
        # y del código de P02 (solo la primera vez) forma parte del arranque en frío.
        inicio_ejecucion = time.perf_counter()
        inicializar, _cerrar, ejecutar, liberar, reservar = self._cargar_practica02()
        inicio_frio_ms = None
        if not self._inicio_frio_registrado:
            inicio_contexto = inicio_ejecucion
            with ServicioGPU._candado_propietario:
                if ServicioGPU._propietario not in (None, self):
                    raise GPUNoDisponible(
                        "Ya existe otro trabajador CUDA en este proceso; el contexto no se comparte.")
                ServicioGPU._propietario = self
            try:
                inicializar()
            except Exception as error:  # pylint: disable=broad-except
                self._reiniciar_contexto()
                raise GPUNoDisponible(
                    f"No se pudo crear el contexto CUDA o compilar/cargar el kernel: {error}"
                ) from error
            inicio_frio_ms = (time.perf_counter() - inicio_contexto) * 1000.0
            self._inicio_frio_registrado = True

        n = ancho * alto
        try:
            salida = np.empty(n, dtype=np.float32)
        except MemoryError as error:
            raise MemoriaServidorInsuficiente("No hay RAM para el arreglo de salida.") from error

        inicio_reserva = time.perf_counter()
        try:
            punteros = reservar(n, k)
        except Exception as error:  # pylint: disable=broad-except
            if _es_memoria_cuda(error):
                raise MemoriaGPUInsuficiente(
                    f"La GPU no tiene {bytes_requeridos(n, k) / 2**20:.1f} MiB libres "
                    f"para una imagen de {ancho}×{alto}.") from error
            self._reiniciar_contexto()
            raise ErrorProcesamientoGPU(f"Fallo al reservar memoria en GPU: {error}") from error
        reserva_ms = (time.perf_counter() - inicio_reserva) * 1000.0
        libre, total = self._memoria_gpu()

        try:
            tiempos = ejecutar(entrada, salida, mascara, *punteros, ancho, alto, k, self._hilos)
        except Exception as error:  # pylint: disable=broad-except
            try:
                liberar(*punteros)
            except Exception:  # pylint: disable=broad-except
                pass
            self._reiniciar_contexto()
            raise ErrorProcesamientoGPU(
                f"Fallo en transferencia, kernel o sincronización: {error}") from error
        inicio_liberacion = time.perf_counter()
        liberar(*punteros)
        liberacion_ms = (time.perf_counter() - inicio_liberacion) * 1000.0

        return ResultadoGPU(
            salida, tiempos.h2d, tiempos.kernel, tiempos.d2h, tiempos.total,
            (inicio_ejecucion - enviado) * 1000.0, inicio_frio_ms,
            reserva_liberacion_ms=reserva_ms + liberacion_ms,
            memoria_reservada_bytes=bytes_requeridos(n, k),
            memoria_gpu_usada_bytes=None if total is None else int(total - libre),
            memoria_gpu_total_bytes=None if total is None else int(total),
            bloques=(n + self._hilos - 1) // self._hilos,
            hilos=self._hilos,
        )

    def _cerrar_en_hilo_cuda(self):
        _inicializar, cerrar, _ejecutar, _liberar, _reservar = self._cargar_practica02()
        cerrar()
        self._liberar_propiedad()
