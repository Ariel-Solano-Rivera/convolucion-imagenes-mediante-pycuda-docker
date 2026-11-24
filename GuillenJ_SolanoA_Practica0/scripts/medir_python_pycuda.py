"""Mide Python y PyCUDA; Python se corta a los 120 s y deja una estimación clara."""
import csv
import sys
import time

import numpy as np

from src.pycuda.contexto_cuda import cerrar_cuda, inicializar_cuda
from src.pycuda.convolucion import ejecutar_gpu, liberar_memoria_gpu, reservar_memoria_gpu
from src.python.comun.configuracion import (EXPERIMENTOS, HILOS_POR_DEFECTO,
                                            LIMITE_PYTHON_SEGUNDOS, MEDICIONES,
                                            NOMBRE_FILTRO, REPETICIONES,
                                            REPETICIONES_PYTHON,
                                            SEGUNDOS_CALENTAMIENTO_GPU, ruta_imagen)
from src.python.comun.imagenes import leer_pgm
from src.python.convolucion import TiempoExcedido, crear_mascara, ejecutar_cpu

COLUMNAS = ("version", "estado", "filtro", "mascara", "ancho", "alto", "hilos_bloque",
            "repeticion", "t_h2d_ms", "t_kernel_ms", "t_d2h_ms", "t_total_ms",
            "limite_s", "filas_procesadas", "estimacion_total_ms", "observaciones")


def configuraciones():
    """Configuraciones sin repetir, conservando el orden de los experimentos."""
    return list(dict.fromkeys(c for grupo in EXPERIMENTOS.values() for c in grupo))


def fila(version, estado, filtro, k, ancho, alto, hilos, repeticion, tiempos=None,
         limite="", filas="", estimacion="", observaciones=""):
    h2d = kernel = d2h = total = ""
    if tiempos is not None:
        h2d, kernel, d2h, total = (f"{x:.4f}" for x in tiempos)
    return {"version": version, "estado": estado, "filtro": NOMBRE_FILTRO[filtro],
            "mascara": k, "ancho": ancho, "alto": alto, "hilos_bloque": hilos,
            "repeticion": repeticion, "t_h2d_ms": h2d, "t_kernel_ms": kernel,
            "t_d2h_ms": d2h, "t_total_ms": total, "limite_s": limite,
            "filas_procesadas": filas, "estimacion_total_ms": estimacion,
            "observaciones": observaciones}


def medir_python(entrada, ancho, alto, filtro, k, hilos):
    """Cinco repeticiones si termina; una estimación proporcional si llega al límite."""
    mascara = crear_mascara(filtro, k)
    salida = np.empty_like(entrada)
    filas = []
    for repeticion in range(1, REPETICIONES_PYTHON + 1):
        try:
            tiempo = ejecutar_cpu(entrada, salida, mascara, ancho, alto, k,
                                  LIMITE_PYTHON_SEGUNDOS)
        except TiempoExcedido as error:
            procesadas = max(error.filas_procesadas, 1)
            estimacion = error.transcurrido * alto / procesadas * 1000
            filas.append(fila("python_secuencial", "estimado", filtro, k, ancho, alto,
                              hilos, repeticion, limite=LIMITE_PYTHON_SEGUNDOS,
                              tiempos=(0, error.transcurrido * 1000, 0,
                                       error.transcurrido * 1000),
                              filas=error.filas_procesadas,
                              estimacion=f"{estimacion:.4f}", observaciones=(
                                  "Corte a 120 s; estimación = tiempo parcial × alto / filas procesadas")))
            break
        filas.append(fila("python_secuencial", "medido", filtro, k, ancho, alto, hilos,
                          repeticion, tiempos=(0, tiempo, 0, tiempo)))
    return filas


def medir_pycuda(entrada, ancho, alto, filtro, k, hilos):
    """Diez repeticiones completas; reserva de memoria fuera de los tiempos."""
    mascara = crear_mascara(filtro, k)
    salida = np.empty_like(entrada)
    d_entrada, d_salida, d_mascara = reservar_memoria_gpu(ancho * alto, k)
    try:
        # Calentamiento por tiempo, igual que P01: ejecuciones completas no
        # registradas durante SEGUNDOS_CALENTAMIENTO_GPU, para medir con la GPU
        # a frecuencia de trabajo (sale de reposo tras las corridas de Python).
        inicio = time.perf_counter()
        while time.perf_counter() - inicio < SEGUNDOS_CALENTAMIENTO_GPU:
            ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida, d_mascara,
                         ancho, alto, k, hilos)
        return [fila("pycuda", "medido", filtro, k, ancho, alto, hilos, r,
                     tiempos=ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida,
                                          d_mascara, ancho, alto, k, hilos))
                for r in range(1, REPETICIONES + 1)]
    finally:
        liberar_memoria_gpu(d_entrada, d_salida, d_mascara)


def filas_python_existentes(filtro, k, ancho, alto, hilos):
    """Filas de Python secuencial ya registradas para esta configuración."""
    ruta = MEDICIONES / "mediciones_python_pycuda.csv"
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return [f for f in csv.DictReader(archivo)
                if f["version"] == "python_secuencial" and f["filtro"] == NOMBRE_FILTRO[filtro]
                and int(f["mascara"]) == k and int(f["ancho"]) == ancho
                and int(f["alto"]) == alto and int(f["hilos_bloque"]) == hilos]


def main():
    # --solo-pycuda: repite PyCUDA y conserva las filas de Python secuencial del CSV.
    solo_pycuda = "--solo-pycuda" in sys.argv
    MEDICIONES.mkdir(parents=True, exist_ok=True)
    filas, imagenes = [], {}
    entorno = inicializar_cuda()
    try:
        for filtro, k, resolucion, hilos in configuraciones():
            if resolucion not in imagenes:
                imagenes[resolucion] = leer_pgm(ruta_imagen(resolucion))
            entrada, ancho, alto = imagenes[resolucion]
            print(f"{NOMBRE_FILTRO[filtro]} {k}x{k}, {ancho}x{alto}, {hilos} hilos", flush=True)
            if solo_pycuda:
                filas += filas_python_existentes(filtro, k, ancho, alto, hilos)
            else:
                filas += medir_python(entrada, ancho, alto, filtro, k, hilos)
            filas += medir_pycuda(entrada, ancho, alto, filtro, k, hilos)
    finally:
        cerrar_cuda()
    with open(MEDICIONES / "mediciones_python_pycuda.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Resultados guardados en {MEDICIONES / 'mediciones_python_pycuda.csv'}")


if __name__ == "__main__":
    main()
