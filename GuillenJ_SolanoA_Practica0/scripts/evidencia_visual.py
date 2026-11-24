"""Evidencia visual de las cuatro versiones (filtros 3x3, imagen 4000x4000).

Calcula una vez Python secuencial y PyCUDA, lee las salidas float32 de C++ y
CUDA C (resultados/referencias/*.bin, de scripts.generar_referencias), compara
antes del recorte y guarda imágenes PNG pequeñas:
  resultados/imagenes/{version}_{filtro}3_4000_reducida.png  (1000x1000)
  resultados/imagenes/{version}_{filtro}3_4000_recorte.png   (600x600 a resolución completa)
  resultados/pruebas/evidencia_visual.csv                     (errores y tolerancia)
No mide tiempos. Uso (cl.exe en el PATH):
    cmd /c "call scripts\\entorno_vs.bat && .venv\\Scripts\\python.exe -m scripts.evidencia_visual"
"""
import csv

import numpy as np
from PIL import Image

from src.pycuda.contexto_cuda import cerrar_cuda, inicializar_cuda
from src.pycuda.convolucion import calcular_gpu
from src.python.comun.configuracion import (IMAGENES, PRUEBAS, REFERENCIAS, Filtro,
                                            NOMBRE_FILTRO, ruta_imagen)
from src.python.comun.imagenes import a_bytes_visibles, leer_pgm, verificar_datos_p01
from src.python.convolucion import (comparar, convolucion_cpu, crear_mascara,
                                    tolerancia)

LADO = 4000
HILOS = 256
# Región de 600x600 con la aguja (la misma zona del recorte de P01).
RECORTE = (2675, 820, 3275, 1420)
REDUCIDA = 1000
FILTROS = (Filtro.MEDIA, Filtro.NITIDEZ, Filtro.LAPLACIANO)
COLUMNAS = ("prueba", "version", "referencia", "filtro", "mascara", "ancho", "alto",
            "hilos_bloque", "error_max", "error_medio", "tolerancia", "resultado")


def guardar(nombre, bytes_):
    imagen = Image.fromarray(bytes_.reshape(LADO, LADO))
    imagen.resize((REDUCIDA, REDUCIDA), Image.LANCZOS).save(IMAGENES / f"{nombre}_reducida.png")
    imagen.crop(RECORTE).save(IMAGENES / f"{nombre}_recorte.png")


def leer_bin(nombre):
    return np.fromfile(REFERENCIAS / nombre, dtype=np.float32)


def main():
    print(f"Datos de P01 verificados por SHA-256: {verificar_datos_p01()} archivos")
    IMAGENES.mkdir(parents=True, exist_ok=True)
    entrada, ancho, alto = leer_pgm(ruta_imagen(LADO))
    guardar("original_4000", entrada.astype(np.uint8))
    inicializar_cuda()
    filas = []
    try:
        for filtro in FILTROS:
            nombre = NOMBRE_FILTRO[filtro]
            mascara = crear_mascara(filtro, 3)
            print(f"{nombre} 3x3: Python secuencial (unos 30 s)...", flush=True)
            python = np.empty_like(entrada)
            convolucion_cpu(entrada, python, mascara, ancho, alto, 3)
            pycuda = calcular_gpu(entrada, mascara, ancho, alto, 3, HILOS)
            salidas = {
                "cpp_secuencial": leer_bin(f"cpp_secuencial_{nombre}3_{LADO}x{LADO}.bin"),
                "cuda_c": leer_bin(f"cuda_c_{nombre}3_{LADO}x{LADO}_h{HILOS}.bin"),
                "python_secuencial": python, "pycuda": pycuda}
            tol = tolerancia(mascara)
            for version, referencia in (("python_secuencial", "cpp_secuencial"),
                                        ("cuda_c", "cpp_secuencial"),
                                        ("pycuda", "cpp_secuencial"),
                                        ("pycuda", "cuda_c")):
                maximo, medio = comparar(salidas[referencia], salidas[version])
                filas.append({"prueba": "evidencia_visual", "version": version,
                              "referencia": referencia, "filtro": nombre, "mascara": 3,
                              "ancho": ancho, "alto": alto,
                              "hilos_bloque": "NA" if version == "python_secuencial" else HILOS,
                              "error_max": f"{maximo:.3e}", "error_medio": f"{medio:.3e}",
                              "tolerancia": f"{tol:.3e}",
                              "resultado": "OK" if maximo <= tol else "FALLA"})
            for version, datos in salidas.items():
                guardar(f"{version}_{nombre}3_{LADO}",
                        a_bytes_visibles(datos, filtro == Filtro.LAPLACIANO))
    finally:
        cerrar_cuda()
    with open(PRUEBAS / "evidencia_visual.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    fallas = [f for f in filas if f["resultado"] != "OK"]
    print(f"evidencia_visual.csv: {len(filas) - len(fallas)}/{len(filas)} OK")
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
