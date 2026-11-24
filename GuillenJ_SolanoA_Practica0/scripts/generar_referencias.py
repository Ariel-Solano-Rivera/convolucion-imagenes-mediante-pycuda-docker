"""Exporta salidas float32 crudas de C++ secuencial y CUDA C."""
import subprocess
import sys

import numpy as np

from src.python.comun.configuracion import (
    CONFIGURACIONES_NO_MULTIPLO, CONFIGURACIONES_PEQUENAS, HILOS_EXPERIMENTO,
    HILOS_POR_DEFECTO, NO_MULTIPLO, NOMBRE_FILTRO, RAIZ, REFERENCIA_EXE,
    REFERENCIAS, RESOLUCIONES_VALIDACION_PYTHON, configuraciones_unicas,
    ruta_imagen)
from src.python.comun.experimentos import (
    NOMBRES_MANUALES, IMAGEN_MANUAL, mascaras_manuales, ruta_referencia)

FORZAR = "--forzar" in sys.argv


def ejecutar(*argumentos):
    comando = [str(REFERENCIA_EXE), *map(str, argumentos)]
    resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"Fallo {' '.join(comando)}:\n{resultado.stderr}")


def falta(*rutas):
    return FORZAR or any(not r.exists() for r in rutas)


def exportar_pgm(imagen, filtro, k, hilos, con_cpp=True):
    """Una salida de C++ (independiente de los hilos) y una de CUDA C por cantidad de hilos."""
    from PIL import Image
    with Image.open(imagen) as im:
        ancho, alto = im.size
    cpp = ruta_referencia("cpp_secuencial", filtro, k, ancho, alto) if con_cpp else "-"
    cuda = ruta_referencia("cuda_c", filtro, k, ancho, alto, hilos)
    if falta(cuda, *([cpp] if con_cpp else [])):
        ejecutar("pgm", imagen, NOMBRE_FILTRO[filtro], k, hilos, cpp, cuda)
        print(f"  {NOMBRE_FILTRO[filtro]}{k} {ancho}x{alto} h{hilos}")


def main():
    if not REFERENCIA_EXE.exists():
        raise FileNotFoundError("Compile primero: scripts\\compilar_referencia.bat")
    REFERENCIAS.mkdir(parents=True, exist_ok=True)

    print("Mascaras de C++ (para la prueba bit a bit)...")
    ejecutar("mascaras", REFERENCIAS)

    print("Prueba manual 5x5...")
    entrada = REFERENCIAS / "manual_entrada.bin"
    IMAGEN_MANUAL.astype("<f4").tofile(entrada)
    for nombre, mascara in zip(NOMBRES_MANUALES, mascaras_manuales()):
        ruta_mascara = REFERENCIAS / f"manual_mascara_{nombre}.bin"
        np.ascontiguousarray(mascara, dtype="<f4").tofile(ruta_mascara)
        ejecutar("crudo", entrada, 5, 5, ruta_mascara, 3, 256,
                 REFERENCIAS / f"manual_{nombre}_cpp_secuencial.bin",
                 REFERENCIAS / f"manual_{nombre}_cuda_c.bin")

    print("Prueba de no multiplo (1013x757)...")
    for filtro, k in CONFIGURACIONES_NO_MULTIPLO:
        for i, hilos in enumerate(HILOS_EXPERIMENTO):
            exportar_pgm(NO_MULTIPLO, filtro, k, hilos, con_cpp=(i == 0))

    print("Imagenes pequenas (validacion de Python secuencial)...")
    for resolucion in RESOLUCIONES_VALIDACION_PYTHON:
        for filtro, k in CONFIGURACIONES_PEQUENAS:
            exportar_pgm(ruta_imagen(resolucion), filtro, k, 256)

    print("Configuraciones de los experimentos...")
    for filtro, k, resolucion, hilos in configuraciones_unicas():
        exportar_pgm(ruta_imagen(resolucion), filtro, k, hilos,
                     con_cpp=(hilos == HILOS_POR_DEFECTO))
    print(f"Referencias en {REFERENCIAS.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
