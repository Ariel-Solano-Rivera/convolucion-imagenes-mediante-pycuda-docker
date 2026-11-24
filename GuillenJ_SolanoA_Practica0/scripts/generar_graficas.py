"""Genera gráficas de C++, CUDA C, Python secuencial y PyCUDA."""
import csv
from pathlib import Path
from statistics import median, stdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

RAIZ = Path(__file__).resolve().parent.parent
MED_C = RAIZ / "resultados" / "mediciones" / "mediciones.csv"
MED_PY = RAIZ / "resultados" / "mediciones" / "mediciones_python_pycuda.csv"
SALIDA = RAIZ / "resultados" / "graficas"


def leer(ruta):
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar():
    filas = []
    for f in leer(MED_C):
        filas.append({"version": "cpp_secuencial" if f["implementacion"] == "CPU" else "cuda_c",
                      "estado": "medido", "filtro": f["filtro"], "mascara": f["mascara"],
                      "ancho": f["ancho"], "alto": f["alto"], "hilos_bloque": f["hilos_bloque"],
                      "t_h2d_ms": f["t_h2d"], "t_kernel_ms": f["t_kernel"],
                      "t_d2h_ms": f["t_d2h"], "t_total_ms": f["t_total"],
                      "estimacion_total_ms": ""})
    return filas + leer(MED_PY)


def buscar(filas, version, filtro, k, ancho, hilos=None):
    return [f for f in filas if f["version"] == version and f["filtro"] == filtro and
            int(f["mascara"]) == k and int(f["ancho"]) == ancho and
            (hilos is None or f["hilos_bloque"] == str(hilos))]


def resumen(filas, columna, estimar=False):
    valores = [float(f[columna]) for f in filas if f["estado"] == "medido" and f[columna]]
    if valores:
        return median(valores), stdev(valores) if len(valores) > 1 else 0.0, False
    valores = [float(f["estimacion_total_ms"]) for f in filas
               if estimar and f["estado"] == "estimado"]
    if valores:
        return median(valores), 0.0, True
    raise ValueError(f"Faltan datos para {columna}")


def guardar(nombre):
    plt.tight_layout()
    plt.savefig(SALIDA / nombre, dpi=180, bbox_inches="tight")
    plt.close()


def comparacion(filas, nombre, titulo, configuraciones):
    series = (("C++ secuencial", "cpp_secuencial", "t_total_ms", None, False),
              ("CUDA C: kernel", "cuda_c", "t_kernel_ms", 256, False),
              ("CUDA C: total", "cuda_c", "t_total_ms", 256, False),
              ("Python secuencial", "python_secuencial", "t_total_ms", 256, True),
              ("PyCUDA: kernel", "pycuda", "t_kernel_ms", 256, False),
              ("PyCUDA: total", "pycuda", "t_total_ms", 256, False))
    colores = ("#4c78a8", "#f58518", "#ffbf79", "#54a24b", "#b279a2", "#e5c1e9")
    posiciones, ancho = list(range(len(configuraciones))), .82 / len(series)
    plt.figure(figsize=(13, 6))
    hay_estimado = False
    for indice, (etiqueta, version, columna, hilos, permite_estimado) in enumerate(series):
        datos = [resumen(buscar(filas, version, filtro, k, resolucion, hilos), columna,
                         permite_estimado) for _, filtro, k, resolucion in configuraciones]
        x = [p + (indice - (len(series) - 1) / 2) * ancho for p in posiciones]
        barras = plt.bar(x, [d[0] for d in datos], ancho, yerr=[d[1] for d in datos],
                         capsize=2, color=colores[indice], label=etiqueta)
        for barra, dato in zip(barras, datos):
            if dato[2]:
                barra.set_hatch("//")
                hay_estimado = True
    plt.xticks(posiciones, [c[0] for c in configuraciones])
    plt.yscale("log")
    plt.ylabel("Tiempo (ms, escala logarítmica)")
    plt.title(titulo)
    plt.grid(axis="y", alpha=.25)
    manejadores, etiquetas = plt.gca().get_legend_handles_labels()
    if hay_estimado:
        manejadores.append(Patch(facecolor="#54a24b", hatch="//"))
        etiquetas.append("Python: estimación tras corte a 120 s")
    plt.legend(manejadores, etiquetas, fontsize=8, ncol=2)
    guardar(nombre)


def grafica_hilos(filas):
    hilos = (128, 256, 512)
    series = (("CUDA C: kernel", "cuda_c", "t_kernel_ms"), ("CUDA C: total", "cuda_c", "t_total_ms"),
              ("PyCUDA: kernel", "pycuda", "t_kernel_ms"), ("PyCUDA: total", "pycuda", "t_total_ms"))
    plt.figure(figsize=(10, 5)); ancho = .8 / len(series)
    for indice, (etiqueta, version, columna) in enumerate(series):
        valores = [resumen(buscar(filas, version, "media", 9, 4000, h), columna)[0] for h in hilos]
        x = [p + (indice - 1.5) * ancho for p in range(len(hilos))]
        plt.bar(x, valores, ancho, label=etiqueta)
    plt.xticks(range(len(hilos)), hilos); plt.xlabel("Hilos por bloque")
    plt.ylabel("Tiempo (ms)"); plt.title("Hilos: media 9×9, 4000×4000")
    plt.legend(fontsize=8); plt.grid(axis="y", alpha=.25); guardar("comparacion_hilos.png")


def distribucion(filas):
    configuraciones = (("Media 3×3", "media", 3), ("Nitidez 3×3", "nitidez", 3),
                        ("Laplaciano 3×3", "laplaciano", 3), ("Media 9×9", "media", 9),
                        ("Media 21×21", "media", 21))
    figura, ejes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for eje, version, titulo in zip(ejes, ("cuda_c", "pycuda"), ("CUDA C", "PyCUDA")):
        h2d, kernel, d2h = [], [], []
        for _, filtro, k in configuraciones:
            datos = buscar(filas, version, filtro, k, 4000, 256)
            partes = [resumen(datos, c)[0] for c in ("t_h2d_ms", "t_kernel_ms", "t_d2h_ms")]
            total = sum(partes); h2d.append(100 * partes[0] / total)
            kernel.append(100 * partes[1] / total); d2h.append(100 * partes[2] / total)
        x = list(range(len(configuraciones))); eje.bar(x, h2d, label="CPU→GPU")
        eje.bar(x, kernel, bottom=h2d, label="Kernel")
        eje.bar(x, d2h, bottom=[a + b for a, b in zip(h2d, kernel)], label="GPU→CPU")
        eje.set_xticks(x, [c[0] for c in configuraciones], rotation=18); eje.set_title(titulo)
        eje.set_ylim(0, 100)
    ejes[0].set_ylabel("Porcentaje del tiempo total"); ejes[1].legend()
    guardar("distribucion_tiempo_gpu.png")


def aceleracion(filas, nombre, titulo, origen, destino, configuraciones):
    kernel, total, etiquetas = [], [], []
    for etiqueta, filtro, k, resolucion in configuraciones:
        hilos_origen = None if origen == "cpp_secuencial" else 256
        try:
            cpu = resumen(buscar(filas, origen, filtro, k, resolucion, hilos_origen),
                          "t_total_ms")[0]
            gpu = buscar(filas, destino, filtro, k, resolucion, 256)
            kernel.append(cpu / resumen(gpu, "t_kernel_ms")[0])
            total.append(cpu / resumen(gpu, "t_total_ms")[0])
        except ValueError:
            continue  # No se calculan aceleraciones con estimaciones de Python.
        etiquetas.append(etiqueta)
    plt.figure(figsize=(10, 5)); x = list(range(len(etiquetas)))
    plt.bar([p - .2 for p in x], kernel, .4, label="Solo kernel")
    plt.bar([p + .2 for p in x], total, .4, label="Con transferencias")
    plt.xticks(x, etiquetas); plt.ylabel("Aceleración (veces)"); plt.title(titulo)
    plt.legend(); plt.grid(axis="y", alpha=.25); guardar(nombre)


def main():
    if not MED_C.exists() or not MED_PY.exists():
        raise FileNotFoundError("Faltan mediciones de C++/CUDA C o de Python/PyCUDA.")
    SALIDA.mkdir(parents=True, exist_ok=True); filas = cargar()
    comparacion(filas, "comparacion_filtros.png", "Cuatro versiones: filtros, 4000×4000",
                (("Media 3×3", "media", 3, 4000), ("Nitidez 3×3", "nitidez", 3, 4000),
                 ("Laplaciano 3×3", "laplaciano", 3, 4000)))
    comparacion(filas, "comparacion_resolucion.png", "Cuatro versiones: media 9×9",
                (("2000×2000", "media", 9, 2000), ("4000×4000", "media", 9, 4000),
                 ("6000×6000", "media", 9, 6000)))
    comparacion(filas, "comparacion_mascaras.png", "Cuatro versiones: máscara, 4000×4000",
                (("3×3", "media", 3, 4000), ("9×9", "media", 9, 4000),
                 ("21×21", "media", 21, 4000)))
    grafica_hilos(filas); distribucion(filas)
    configuraciones = (("Media 3×3\n4000", "media", 3, 4000),
                       ("Nitidez 3×3\n4000", "nitidez", 3, 4000),
                       ("Laplaciano 3×3\n4000", "laplaciano", 3, 4000),
                       ("Media 9×9\n2000", "media", 9, 2000),
                       ("Media 9×9\n4000", "media", 9, 4000),
                       ("Media 9×9\n6000", "media", 9, 6000),
                       ("Media 21×21\n4000", "media", 21, 4000))
    aceleracion(filas, "aceleracion_cuda_c.png", "C++ secuencial frente a CUDA C",
                "cpp_secuencial", "cuda_c", configuraciones)
    aceleracion(filas, "aceleracion_pycuda.png", "Python secuencial frente a PyCUDA",
                "python_secuencial", "pycuda", configuraciones)
    print(f"Gráficas guardadas en: {SALIDA}")


if __name__ == "__main__":
    main()
