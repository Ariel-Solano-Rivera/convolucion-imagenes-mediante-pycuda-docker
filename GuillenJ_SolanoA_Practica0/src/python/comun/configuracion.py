"""Parametros generales de las mediciones, filtros y rutas."""
from enum import IntEnum
from pathlib import Path

# Mismos valores que configuracion.h de P01.
REPETICIONES = 10
SEGUNDOS_CALENTAMIENTO_GPU = 2.0
# Tolerancia fija de P01. En P02 la validacion usa ademas la cota de float32 por
# configuracion (convolucion.tolerancia); ver README.
TOLERANCIA = 1e-2
# Python secuencial: minimo de la guia (P01 no tenia esta version).
REPETICIONES_PYTHON = 5
# Máximo por ejecución de Python secuencial. Si se alcanza, se registra una
# estimación basada en las filas ya procesadas, nunca como tiempo medido.
LIMITE_PYTHON_SEGUNDOS = 120
HILOS_POR_DEFECTO = 256
HILOS_EXPERIMENTO = (128, 256, 512)


class Filtro(IntEnum):
    MEDIA = 0
    NITIDEZ = 1
    LAPLACIANO = 2


NOMBRE_FILTRO = {Filtro.MEDIA: "media", Filtro.NITIDEZ: "nitidez",
                 Filtro.LAPLACIANO: "laplaciano"}

# Compilacion del kernel: mismos flags que compilar.bat de P01, sin --use_fast_math.
ARQUITECTURA = "sm_86"
OPCIONES_NVCC = ["-O3"]

# Rutas relativas a la carpeta unificada de la práctica.
RAIZ = Path(__file__).resolve().parents[3]
RAIZ_REPO = RAIZ.parent
P01 = RAIZ  # código C/CUDA de la práctica 01 (los tests comparan con sus fuentes)
DATOS = RAIZ / "datos"
RESULTADOS = RAIZ / "resultados"
MEDICIONES = RESULTADOS / "mediciones"
PRUEBAS = RESULTADOS / "pruebas"
IMAGENES = RESULTADOS / "imagenes"
REFERENCIAS = RESULTADOS / "referencias"
KERNEL = RAIZ / "src" / "pycuda" / "kernels" / "convolucion.cu"

# Imagenes de P01 (datos/): se comprueban por SHA-256, no se regeneran a mano.
IMAGENES_P01 = {
    2000: DATOS / "base_2000.pgm",
    4000: DATOS / "base_4000.pgm",
    6000: DATOS / "base_6000.pgm",
}
NO_MULTIPLO = DATOS / "no_multiplo_1013x757.pgm"
HASHES_P01 = DATOS / "hashes_p01.json"

# Herramienta de referencias C++/CUDA C, dentro del código CUDA C.
REFERENCIA_EXE = RAIZ / "src" / "cuda_c" / "referencia.exe"
VERSIONES = ("cpp_secuencial", "cuda_c", "python_secuencial", "pycuda")

# Experimentos obligatorios: (filtro, k, resolucion, hilos). Un factor a la vez; hilos fijos
# en 256 fuera del experimento de hilos. Las configuraciones repetidas comparten mediciones.
EXPERIMENTOS = {
    "filtros": [(Filtro.MEDIA, 3, 4000, 256), (Filtro.NITIDEZ, 3, 4000, 256),
                (Filtro.LAPLACIANO, 3, 4000, 256)],
    "resolucion": [(Filtro.MEDIA, 9, 2000, 256), (Filtro.MEDIA, 9, 4000, 256),
                   (Filtro.MEDIA, 9, 6000, 256)],
    "mascara": [(Filtro.MEDIA, 3, 4000, 256), (Filtro.MEDIA, 9, 4000, 256),
                (Filtro.MEDIA, 21, 4000, 256)],
    "hilos": [(Filtro.MEDIA, 9, 4000, h) for h in HILOS_EXPERIMENTO],  # solo GPU
}
# Prueba de limites de P01 (pruebaNoMultiplo): media 3, nitidez 3, laplaciano 3 y media 9.
CONFIGURACIONES_NO_MULTIPLO = [(Filtro.MEDIA, 3), (Filtro.NITIDEZ, 3),
                               (Filtro.LAPLACIANO, 3), (Filtro.MEDIA, 9)]
# Configuraciones evaluadas en imagenes pequenas (validacion de Python secuencial).
CONFIGURACIONES_PEQUENAS = [(Filtro.MEDIA, 3), (Filtro.NITIDEZ, 3), (Filtro.LAPLACIANO, 3),
                            (Filtro.MEDIA, 9), (Filtro.MEDIA, 21)]
RESOLUCIONES_VALIDACION_PYTHON = (250,)


def ruta_imagen(resolucion):
    """Imagenes de P01 desde su carpeta; las nuevas desde datos/ de P02."""
    return IMAGENES_P01.get(resolucion, DATOS / f"base_{resolucion}.pgm")


def configuraciones_unicas():
    """(filtro, k, resolucion, hilos) sin repetir, en orden de aparicion."""
    vistas = []
    for configuraciones in EXPERIMENTOS.values():
        for configuracion in configuraciones:
            if configuracion not in vistas:
                vistas.append(configuracion)
    return vistas
