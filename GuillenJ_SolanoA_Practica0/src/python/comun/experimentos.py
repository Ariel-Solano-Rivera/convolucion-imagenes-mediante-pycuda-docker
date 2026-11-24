"""Pruebas, validacion y experimentos de la practica."""
import csv

import numpy as np

from .configuracion import (CONFIGURACIONES_NO_MULTIPLO, CONFIGURACIONES_PEQUENAS,
                            HILOS_EXPERIMENTO, HILOS_POR_DEFECTO, NO_MULTIPLO,
                            NOMBRE_FILTRO, PRUEBAS, REFERENCIAS,
                            RESOLUCIONES_VALIDACION_PYTHON, Filtro,
                            configuraciones_unicas, ruta_imagen)

# Prueba manual: matriz 5x5 y mascara de la figura 1 de la guia (pruebaManual de P01).
IMAGEN_MANUAL = np.array([35, 40, 41, 45, 50,
                          40, 40, 42, 46, 52,
                          42, 46, 50, 55, 55,
                          48, 52, 56, 58, 60,
                          56, 60, 65, 70, 75], dtype=np.float32)
MASCARA_FIGURA1 = np.array([-2, -1, 0, -1, 1, 1, 0, 1, 2], dtype=np.float32)
NOMBRES_MANUALES = ("figura1", "media", "nitidez", "laplaciano")
# (indice de mascara, fila, columna, esperado). Los cocientes se hacen en float32 como 155.f / 9.
CASOS_MANUALES = (
    (0, 1, 1, np.float32(78)), (0, 1, 2, np.float32(87)),
    (1, 0, 0, np.float32(155) / np.float32(9)), (1, 2, 2, np.float32(445) / np.float32(9)),
    (1, 4, 4, np.float32(263) / np.float32(9)), (2, 0, 0, np.float32(95)),
    (2, 1, 1, np.float32(32)), (2, 2, 2, np.float32(51)),
    (3, 0, 0, np.float32(-60)), (3, 1, 1, np.float32(8)),
    (3, 2, 2, np.float32(-1)), (3, 4, 4, np.float32(-170)),
)
TOLERANCIA_MANUAL = 1e-3  # la misma de pruebaManual en P01


def mascaras_manuales():
    """Las cuatro mascaras de la prueba manual, en el orden de NOMBRES_MANUALES."""
    from src.python.convolucion import crear_mascara
    return (MASCARA_FIGURA1, crear_mascara(Filtro.MEDIA, 3),
            crear_mascara(Filtro.NITIDEZ, 3), crear_mascara(Filtro.LAPLACIANO, 3))


# ---------------------------------------------------------------------------
# Referencias de C++ secuencial y CUDA C (resultados/referencias/*.bin, float32 crudo)
# ---------------------------------------------------------------------------
def ruta_referencia(version, filtro, k, ancho, alto, hilos=None):
    sufijo = f"_h{hilos}" if version == "cuda_c" else ""
    return REFERENCIAS / f"{version}_{NOMBRE_FILTRO[filtro]}{k}_{ancho}x{alto}{sufijo}.bin"


def leer_referencia(ruta, n):
    if not ruta.exists():
        raise FileNotFoundError(f"Falta {ruta.name}: ejecute python -m scripts.generar_referencias")
    datos = np.fromfile(ruta, dtype="<f4")
    if datos.size != n:
        raise ValueError(f"{ruta.name} tiene {datos.size} valores; se esperaban {n}")
    return datos.astype(np.float32, copy=False)


def escribir_csv(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


# ---------------------------------------------------------------------------
# Prueba manual 5x5 en las cuatro versiones
# ---------------------------------------------------------------------------
COLUMNAS_MANUAL = ["version", "mascara", "fila", "columna", "esperado_manual", "obtenido",
                   "resultado"]


def prueba_manual():
    from src.python.convolucion import convolucion_cpu
    from src.pycuda.convolucion import calcular_gpu
    filas = []
    for indice, (nombre, mascara) in enumerate(zip(NOMBRES_MANUALES, mascaras_manuales())):
        python = np.zeros(25, dtype=np.float32)
        convolucion_cpu(IMAGEN_MANUAL, python, mascara, 5, 5, 3)
        salidas = {
            "cpp_secuencial": leer_referencia(
                REFERENCIAS / f"manual_{nombre}_cpp_secuencial.bin", 25),
            "cuda_c": leer_referencia(REFERENCIAS / f"manual_{nombre}_cuda_c.bin", 25),
            "python_secuencial": python,
            "pycuda": calcular_gpu(IMAGEN_MANUAL, mascara, 5, 5, 3, HILOS_POR_DEFECTO),
        }
        for m, fila, columna, esperado in CASOS_MANUALES:
            if m != indice:
                continue
            for version, salida in salidas.items():
                valor = salida[fila * 5 + columna]
                ok = abs(float(valor) - float(esperado)) <= TOLERANCIA_MANUAL
                filas.append({"version": version, "mascara": nombre, "fila": fila,
                              "columna": columna, "esperado_manual": f"{esperado:.4f}",
                              "obtenido": f"{valor:.4f}",
                              "resultado": "OK" if ok else "FALLA"})
    escribir_csv(PRUEBAS / "prueba_manual_python_pycuda.csv", COLUMNAS_MANUAL, filas)
    return filas


# ---------------------------------------------------------------------------
# Validacion numerica contra C++ secuencial (antes del recorte)
# ---------------------------------------------------------------------------
COLUMNAS_VALIDACION = ["prueba", "version", "referencia", "filtro", "mascara", "ancho", "alto",
                       "hilos_bloque", "error_max", "error_medio", "tolerancia", "resultado"]


def fila_validacion(prueba, version, referencia, filtro, k, ancho, alto, hilos,
                    datos_ref, datos, mascara):
    from src.python.convolucion import comparar, tolerancia
    maximo, medio = comparar(datos_ref, datos)
    tol = tolerancia(mascara)
    return {"prueba": prueba, "version": version, "referencia": referencia,
            "filtro": NOMBRE_FILTRO[filtro], "mascara": k, "ancho": ancho, "alto": alto,
            "hilos_bloque": hilos, "error_max": f"{maximo:.3e}",
            "error_medio": f"{medio:.3e}", "tolerancia": f"{tol:.3e}",
            "resultado": "OK" if maximo <= tol else "FALLA"}


def validar_configuracion(prueba, entrada, ancho, alto, filtro, k, lista_hilos, con_python):
    """Compara Python secuencial, CUDA C y PyCUDA contra C++; y PyCUDA contra CUDA C."""
    from src.python.convolucion import (convolucion_cpu,
                                                         crear_mascara)
    from src.pycuda.convolucion import calcular_gpu
    n = ancho * alto
    mascara = crear_mascara(filtro, k)
    cpp = leer_referencia(ruta_referencia("cpp_secuencial", filtro, k, ancho, alto), n)
    filas = []
    if con_python:
        python = np.zeros(n, dtype=np.float32)
        convolucion_cpu(entrada, python, mascara, ancho, alto, k)
        filas.append(fila_validacion(prueba, "python_secuencial", "cpp_secuencial", filtro, k,
                                     ancho, alto, "NA", cpp, python, mascara))
    for hilos in lista_hilos:
        cuda_c = leer_referencia(ruta_referencia("cuda_c", filtro, k, ancho, alto, hilos), n)
        # Salida inicial NaN: si algun pixel no se escribe, el error sale NaN y la fila FALLA.
        pycuda = calcular_gpu(entrada, mascara, ancho, alto, k, hilos,
                              salida_inicial=np.full(n, np.nan, dtype=np.float32))
        for version, datos, referencia, ref in (("cuda_c", cuda_c, "cpp_secuencial", cpp),
                                                ("pycuda", pycuda, "cpp_secuencial", cpp),
                                                ("pycuda", pycuda, "cuda_c", cuda_c)):
            filas.append(fila_validacion(prueba, version, referencia, filtro, k, ancho, alto,
                                         hilos, ref, datos, mascara))
    return filas


def prueba_no_multiplo():
    """1013x757 con 128, 256 y 512 hilos (pruebaNoMultiplo de P01), en las cuatro versiones."""
    from .imagenes import leer_pgm
    entrada, ancho, alto = leer_pgm(NO_MULTIPLO)
    filas = []
    for filtro, k in CONFIGURACIONES_NO_MULTIPLO:
        filas += validar_configuracion("no_multiplo", entrada, ancho, alto, filtro, k,
                                       HILOS_EXPERIMENTO, con_python=True)
    return filas


def validar_imagenes_pequenas():
    """Python secuencial frente a C++ en imagenes pequenas (los 3 filtros y las 3 mascaras)."""
    from .imagenes import leer_pgm
    filas = []
    for resolucion in RESOLUCIONES_VALIDACION_PYTHON:
        entrada, ancho, alto = leer_pgm(ruta_imagen(resolucion))
        for filtro, k in CONFIGURACIONES_PEQUENAS:
            filas += validar_configuracion("pequena", entrada, ancho, alto, filtro, k,
                                           [HILOS_POR_DEFECTO], con_python=True)
    return filas


def validar_experimentos():
    """CUDA C y PyCUDA frente a C++ en las configuraciones de los experimentos.

    Python secuencial se valida aqui solo en imagenes pequenas; en las grandes se valida
    con la salida de cada corrida completada durante las mediciones.
    """
    from .imagenes import leer_pgm
    filas, imagenes = [], {}
    for filtro, k, resolucion, hilos in configuraciones_unicas():
        if resolucion not in imagenes:
            imagenes = {resolucion: leer_pgm(ruta_imagen(resolucion))}  # una imagen en memoria
        entrada, ancho, alto = imagenes[resolucion]
        filas += validar_configuracion("experimento", entrada, ancho, alto, filtro, k,
                                       [hilos], con_python=False)
    return filas


def validacion_completa():
    filas = prueba_no_multiplo() + validar_imagenes_pequenas() + validar_experimentos()
    escribir_csv(PRUEBAS / "validacion_python_pycuda.csv", COLUMNAS_VALIDACION, filas)
    return filas
