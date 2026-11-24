"""Versión solo paralela: los 4 experimentos de la guía con CUDA C y PyCUDA.

Para cada imagen (JPG, PNG, PGM, ...):
  1. La prepara como en la práctica 01: escala de grises, recorte cuadrado central y
     redimensión Lanczos a 2000×2000, 4000×4000 y 6000×6000 (configurable).
     Sin imagen se usan directamente datos/base_2000/4000/6000.pgm.
  2. Ejecuta los 4 experimentos (un factor a la vez; las configuraciones repetidas
     se miden una sola vez):
       Filtro      media, nitidez y laplaciano 3×3; resolución intermedia; 256 hilos
       Resolución  media 9×9; las tres resoluciones; 256 hilos
       Máscara     media 3×3, 9×9 y 21×21; resolución intermedia; 256 hilos
       Hilos       media 9×9; resolución intermedia; 128, 256 y 512 hilos
  3. CUDA C se mide con referencia.exe (bucle de P01) y PyCUDA con el mismo kernel y el
     mismo procedimiento: 2 s de calentamiento + 10 repeticiones, tiempos H2D, kernel,
     D2H y total. La salida de PyCUDA se compara con la de CUDA C antes del recorte.
Todo queda en resultados/paralelo/<nombre_imagen>/ (no toca otros resultados).

Uso (cl.exe en el PATH; lo prepara ejecutar_paralelo.bat):
    python -m scripts.ejecutar_paralelo [imagen1.jpg imagen2.png ...] [--resoluciones 2000,4000,6000]
"""
import argparse
import csv
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from src.pycuda.contexto_cuda import cerrar_cuda, inicializar_cuda
from src.pycuda.convolucion import ejecutar_gpu, liberar_memoria_gpu, reservar_memoria_gpu
from src.python.comun.configuracion import (DATOS, REFERENCIA_EXE, REPETICIONES, RESULTADOS,
                                            RAIZ, SEGUNDOS_CALENTAMIENTO_GPU, Filtro,
                                            NOMBRE_FILTRO)
from src.python.comun.imagenes import a_bytes_visibles, leer_pgm
from src.python.convolucion import comparar, crear_mascara, tolerancia

HILOS_BASE = 256
HILOS_EXPERIMENTO = (128, 256, 512)
COLUMNAS = ("version", "filtro", "mascara", "ancho", "alto", "hilos_bloque", "bloques",
            "repeticion", "t_h2d", "t_kernel", "t_d2h", "t_total", "unidad", "estado",
            "observaciones", "origen")
ETIQUETA = {Filtro.MEDIA: "Media", Filtro.NITIDEZ: "Nitidez", Filtro.LAPLACIANO: "Laplaciano"}
COLOR = {"cuda_c": "#1c2942", "pycuda": "#b5541b"}
NOMBRE_VERSION = {"cuda_c": "CUDA C", "pycuda": "PyCUDA"}


def experimentos(resoluciones):
    """Experimentos de la guía: nombre -> lista de (filtro, k, lado, hilos)."""
    base = resoluciones[len(resoluciones) // 2]  # resolución intermedia (4000 por defecto)
    return {
        "filtro": [(Filtro.MEDIA, 3, base, HILOS_BASE), (Filtro.NITIDEZ, 3, base, HILOS_BASE),
                   (Filtro.LAPLACIANO, 3, base, HILOS_BASE)],
        "resolucion": [(Filtro.MEDIA, 9, lado, HILOS_BASE) for lado in resoluciones],
        "mascara": [(Filtro.MEDIA, k, base, HILOS_BASE) for k in (3, 9, 21)],
        "hilos": [(Filtro.MEDIA, 9, base, h) for h in HILOS_EXPERIMENTO],
    }


# ---------------------------------------------------------------------------
# Preparación de las imágenes
# ---------------------------------------------------------------------------
def preparar_resoluciones(ruta, carpeta, resoluciones):
    """Mismo procedimiento que scripts/preparar_imagenes.py: gris, cuadrado central, Lanczos."""
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(ruta) as imagen:
        gris = imagen.convert("L")
    lado = min(gris.size)
    x0, y0 = (gris.width - lado) // 2, (gris.height - lado) // 2
    cuadrado = gris.crop((x0, y0, x0 + lado, y0 + lado))
    rutas = {}
    for n in resoluciones:
        destino = carpeta / f"entrada_{n}.pgm"
        cuadrado.resize((n, n), Image.LANCZOS).save(destino)  # "P5\n<n> <n>\n255\n"
        rutas[n] = destino
    return rutas, gris.size


# ---------------------------------------------------------------------------
# Medición
# ---------------------------------------------------------------------------
def referencia(*argumentos):
    comando = [str(REFERENCIA_EXE), *map(str, argumentos)]
    resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"Falló {' '.join(comando)}:\n{resultado.stderr}")


def medir_cuda_c(entrada_pgm, filtro, k, hilos, csv_cuda, salida_bin):
    """Tiempos con el bucle de P01 (modo medir, sin CPU) y la salida float32."""
    referencia("medir", entrada_pgm, NOMBRE_FILTRO[filtro], k, hilos, 0, csv_cuda)
    referencia("pgm", entrada_pgm, NOMBRE_FILTRO[filtro], k, hilos, "-", salida_bin)
    salida = np.fromfile(salida_bin, dtype=np.float32)
    salida_bin.unlink()  # archivo intermedio
    return salida


def medir_pycuda(entrada, ancho, alto, filtro, k, hilos):
    """Calentamiento de 2 s y 10 repeticiones; reserva de memoria fuera de los tiempos."""
    mascara = crear_mascara(filtro, k)
    salida = np.empty_like(entrada)
    bloques = (ancho * alto + hilos - 1) // hilos
    d_entrada, d_salida, d_mascara = reservar_memoria_gpu(ancho * alto, k)
    try:
        inicio = time.perf_counter()
        while time.perf_counter() - inicio < SEGUNDOS_CALENTAMIENTO_GPU:
            ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida, d_mascara,
                         ancho, alto, k, hilos)
        filas = []
        for r in range(1, REPETICIONES + 1):
            t = ejecutar_gpu(entrada, salida, mascara, d_entrada, d_salida, d_mascara,
                             ancho, alto, k, hilos)
            filas.append({"version": "pycuda", "filtro": NOMBRE_FILTRO[filtro], "mascara": k,
                          "ancho": ancho, "alto": alto, "hilos_bloque": hilos,
                          "bloques": bloques, "repeticion": r, "t_h2d": f"{t.h2d:.4f}",
                          "t_kernel": f"{t.kernel:.4f}", "t_d2h": f"{t.d2h:.4f}",
                          "t_total": f"{t.total:.4f}", "unidad": "ms",
                          "estado": "completada", "observaciones": "NA", "origen": "nuevo"})
    finally:
        liberar_memoria_gpu(d_entrada, d_salida, d_mascara)
    return filas, salida


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------
def guardar_imagenes(carpeta, nombre, datos, lado, laplaciano, con_recorte):
    """PNG reducido a 1000 px y, si se pide, recorte central de 600×600 a resolución completa."""
    imagen = Image.fromarray(a_bytes_visibles(datos, laplaciano).reshape(lado, lado))
    imagen.resize((1000, 1000), Image.LANCZOS).save(carpeta / f"{nombre}_reducida.png")
    if con_recorte:
        c = lado // 2
        imagen.crop((c - 300, c - 300, c + 300, c + 300)).save(carpeta / f"{nombre}_recorte.png")


def leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def resumir(mediciones):
    """Medianas, IQR y CV por versión y configuración."""
    grupos = {}
    for f in mediciones:
        clave = (f["filtro"], int(f["mascara"]), int(f["ancho"]), int(f["hilos_bloque"]),
                 f["version"])
        grupos.setdefault(clave, []).append(f)
    resumen = {}
    for clave, filas in grupos.items():
        r = {c: float(np.median([float(f[f"t_{c}"]) for f in filas]))
             for c in ("h2d", "kernel", "d2h", "total")}
        kernel = np.array([float(f["t_kernel"]) for f in filas])
        q1, q3 = np.percentile(kernel, [25, 75])
        r["iqr_kernel"] = float(q3 - q1)
        r["cv_kernel"] = float(kernel.std(ddof=1) / kernel.mean())
        r["pct_transf"] = float(np.median([100 * (float(f["t_h2d"]) + float(f["t_d2h"]))
                                           / float(f["t_total"]) for f in filas]))
        r["n"] = len(filas)
        resumen[clave] = r
    return resumen


def etiqueta(experimento, filtro, k, lado, hilos):
    if experimento == "filtro":
        return f"{ETIQUETA[filtro]} 3×3"
    if experimento == "resolucion":
        return f"{lado}×{lado}"
    if experimento == "mascara":
        return f"Media {k}×{k}"
    return f"{hilos} hilos"


TITULOS = {"filtro": "Experimento Filtro (3×3, {base}², 256 hilos)",
           "resolucion": "Experimento Resolución (media 9×9, 256 hilos)",
           "mascara": "Experimento Máscara (media, {base}², 256 hilos)",
           "hilos": "Experimento Hilos por bloque (media 9×9, {base}²)"}


def grafica(resumen, experimento, configuraciones, ruta, nombre_imagen, base):
    etiquetas = [etiqueta(experimento, *c) for c in configuraciones]
    fig, ejes = plt.subplots(1, 3, figsize=(13, 4.3))
    xs = np.arange(len(configuraciones))
    paneles = (("kernel", "Kernel", 3), ("total", "H2D + kernel + D2H", 2))
    for eje, (campo, nombre, dec) in zip(ejes[:2], paneles):
        for i, version in enumerate(("cuda_c", "pycuda")):
            valores = [resumen[(NOMBRE_FILTRO[f], k, lado, h, version)][campo]
                       for f, k, lado, h in configuraciones]
            barras = eje.bar(xs + (i - 0.5) * 0.38, valores, 0.38, color=COLOR[version],
                             label=NOMBRE_VERSION[version])
            eje.bar_label(barras, [f"{v:.{dec}f}" for v in valores], fontsize=7, padding=1)
        eje.set_xticks(xs, etiquetas, fontsize=8.5)
        eje.set_ylabel("ms (mediana de 10 repeticiones)")
        eje.set_title(nombre, fontsize=10)
        eje.grid(axis="y", alpha=0.3)
        eje.set_ylim(0, eje.get_ylim()[1] * 1.18)
        eje.legend(fontsize=8, loc="upper left")
    # Tercer panel: reparto del tiempo de PyCUDA entre copias y kernel
    eje = ejes[2]
    datos = [resumen[(NOMBRE_FILTRO[f], k, lado, h, "pycuda")] for f, k, lado, h in configuraciones]
    h2d = [d["h2d"] for d in datos]
    ker = [d["kernel"] for d in datos]
    d2h = [d["d2h"] for d in datos]
    eje.bar(xs, h2d, 0.6, color="#8c96a8", label="Copia CPU→GPU")
    eje.bar(xs, ker, 0.6, bottom=h2d, color="#b5541b", label="Kernel")
    eje.bar(xs, d2h, 0.6, bottom=[a + b for a, b in zip(h2d, ker)], color="#b7bfcc",
            label="Copia GPU→CPU")
    for x, d in zip(xs, datos):
        eje.text(x, d["h2d"] + d["kernel"] + d["d2h"], f"{d['pct_transf']:.0f} %\ncopias",
                 ha="center", va="bottom", fontsize=7)
    eje.set_xticks(xs, etiquetas, fontsize=8.5)
    eje.set_title("PyCUDA: reparto del tiempo", fontsize=10)
    eje.grid(axis="y", alpha=0.3)
    eje.set_ylim(0, eje.get_ylim()[1] * 1.15)
    eje.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3,
               frameon=False)
    fig.suptitle(f"{TITULOS[experimento].format(base=base)} · {nombre_imagen}", fontsize=11)
    plt.tight_layout()
    plt.savefig(ruta, dpi=150)
    plt.close()


# ---------------------------------------------------------------------------
# Proceso de una imagen
# ---------------------------------------------------------------------------
def procesar(ruta_imagen, resoluciones):
    nombre = Path(ruta_imagen).stem if ruta_imagen else "imagenes_practica"
    carpeta = RESULTADOS / "paralelo" / nombre
    (carpeta / "imagenes").mkdir(parents=True, exist_ok=True)
    (carpeta / "graficas").mkdir(exist_ok=True)
    if ruta_imagen:
        entradas, tam = preparar_resoluciones(ruta_imagen, carpeta, resoluciones)
        descripcion = f"{Path(ruta_imagen).name} ({tam[0]}×{tam[1]})"
    else:  # imágenes de la práctica, ya preparadas
        entradas = {n: DATOS / f"base_{n}.pgm" for n in resoluciones}
        descripcion = "imágenes de la práctica (datos/)"
    print(f"\n=== {descripcion} → {', '.join(f'{n}²' for n in resoluciones)} ===", flush=True)

    exps = experimentos(resoluciones)
    base = resoluciones[len(resoluciones) // 2]
    unicas = list(dict.fromkeys(c for lista in exps.values() for c in lista))
    unicas.sort(key=lambda c: c[2])  # agrupa por resolución: cada imagen se lee una vez
    csv_cuda = carpeta / "mediciones_cuda_c.tmp.csv"
    with open(csv_cuda, "w", encoding="utf-8", newline="") as archivo:
        archivo.write(",".join(COLUMNAS) + "\n")
    filas_pycuda, validacion, cache = [], [], {}
    for filtro, k, lado, hilos in unicas:
        if lado not in cache:
            cache = {lado: leer_pgm(entradas[lado])}  # una resolución en memoria a la vez
            entrada, ancho, alto = cache[lado]
            guardar_imagenes(carpeta / "imagenes", f"original_{lado}", entrada, lado, False,
                             lado == base)
        entrada, ancho, alto = cache[lado]
        print(f"  {NOMBRE_FILTRO[filtro]} {k}x{k}, {ancho}x{alto}, {hilos} hilos ...", flush=True)
        cuda = medir_cuda_c(entradas[lado], filtro, k, hilos, csv_cuda,
                            carpeta / "salida_cuda_c.tmp.bin")
        filas, pycuda = medir_pycuda(entrada, ancho, alto, filtro, k, hilos)
        filas_pycuda += filas
        maximo, medio = comparar(cuda, pycuda)
        tol = tolerancia(crear_mascara(filtro, k))
        validacion.append({"filtro": NOMBRE_FILTRO[filtro], "mascara": k, "ancho": ancho,
                           "alto": alto, "hilos_bloque": hilos, "error_max": f"{maximo:.3e}",
                           "error_medio": f"{medio:.3e}", "tolerancia": f"{tol:.3e}",
                           "resultado": "OK" if maximo <= tol else "FALLA"})
        if hilos == HILOS_BASE:  # evidencia visual de cada filtro y máscara
            laplaciano = filtro == Filtro.LAPLACIANO
            recorte = lado == base
            for version, datos in (("cuda_c", cuda), ("pycuda", pycuda)):
                guardar_imagenes(carpeta / "imagenes", f"{version}_{NOMBRE_FILTRO[filtro]}{k}_{lado}",
                                 datos, lado, laplaciano, recorte)

    # Registros
    mediciones = leer_csv(csv_cuda) + filas_pycuda
    csv_cuda.unlink()
    for archivo_pgm in carpeta.glob("entrada_*.pgm"):  # intermedios: se regeneran
        archivo_pgm.unlink()
    with open(carpeta / "mediciones.csv", "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(mediciones)
    with open(carpeta / "validacion.csv", "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(validacion[0]))
        escritor.writeheader()
        escritor.writerows(validacion)

    resumen = resumir(mediciones)
    campos = ["experimento", "filtro", "mascara", "ancho", "alto", "hilos_bloque", "bloques"]
    for v in ("cuda_c", "pycuda"):
        campos += [f"{v}_{c}" for c in ("h2d", "kernel", "d2h", "total", "iqr_kernel",
                                         "cv_kernel", "pct_transf")]
    campos += ["pycuda_vs_cuda_c_kernel", "pycuda_vs_cuda_c_total", "unidad"]
    with open(carpeta / "resumen.csv", "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(campos)
        for experimento, lista in exps.items():
            print(f"\n  {TITULOS[experimento].format(base=base)}")
            print(f"  {'Configuración':<16}{'Kernel CUDA C':>14}{'Kernel PyCUDA':>15}"
                  f"{'Total CUDA C':>14}{'Total PyCUDA':>14}{'% copias':>10}")
            for filtro, k, lado, hilos in lista:
                cu = resumen[(NOMBRE_FILTRO[filtro], k, lado, hilos, "cuda_c")]
                pc = resumen[(NOMBRE_FILTRO[filtro], k, lado, hilos, "pycuda")]
                fila = [experimento, NOMBRE_FILTRO[filtro], k, lado, lado, hilos,
                        (lado * lado + hilos - 1) // hilos]
                for r in (cu, pc):
                    fila += [f"{r['h2d']:.4f}", f"{r['kernel']:.4f}", f"{r['d2h']:.4f}",
                             f"{r['total']:.4f}", f"{r['iqr_kernel']:.4f}",
                             f"{100 * r['cv_kernel']:.2f}", f"{r['pct_transf']:.1f}"]
                fila += [f"{pc['kernel'] / cu['kernel']:.3f}", f"{pc['total'] / cu['total']:.3f}", "ms"]
                escritor.writerow(fila)
                print(f"  {etiqueta(experimento, filtro, k, lado, hilos):<16}"
                      f"{cu['kernel']:>11.3f} ms{pc['kernel']:>12.3f} ms"
                      f"{cu['total']:>11.2f} ms{pc['total']:>11.2f} ms{pc['pct_transf']:>9.1f}%")
            grafica(resumen, experimento, lista,
                    carpeta / "graficas" / f"experimento_{experimento}.png", nombre, base)

    fallas = [v for v in validacion if v["resultado"] != "OK"]
    print(f"\n  Validación PyCUDA vs CUDA C: {len(validacion) - len(fallas)}/{len(validacion)} OK")
    print(f"  Resultados en {carpeta.relative_to(RAIZ)}")
    return carpeta, not fallas


def main():
    parser = argparse.ArgumentParser(description="4 experimentos con CUDA C y PyCUDA")
    parser.add_argument("imagenes", nargs="*",
                        help="imágenes (jpg, png, pgm, ...); sin imágenes usa datos/base_*.pgm")
    parser.add_argument("--resoluciones", default="2000,4000,6000",
                        help="lados de las imágenes cuadradas, de menor a mayor")
    args = parser.parse_args()
    resoluciones = sorted(int(n) for n in args.resoluciones.split(","))
    if len(resoluciones) < 2 or resoluciones[0] < 600:
        raise SystemExit("Indique al menos dos resoluciones de 600 px o más.")
    if not REFERENCIA_EXE.exists():
        raise SystemExit("Falta src\\cuda_c\\referencia.exe: ejecute scripts\\compilar_referencia.bat")
    for ruta in args.imagenes:
        if not Path(ruta).is_file():
            raise SystemExit(f"No existe la imagen: {ruta}")
    if not args.imagenes:
        faltan = [n for n in resoluciones if not (DATOS / f"base_{n}.pgm").exists()]
        if faltan:
            raise SystemExit(f"No hay datos/base_{faltan[0]}.pgm: indique una imagen o use "
                             "--resoluciones 2000,4000,6000")
    entorno = inicializar_cuda()  # contexto y compilación del kernel, una sola vez
    ok = True
    try:
        for ruta in args.imagenes or [None]:
            carpeta, correcto = procesar(ruta, resoluciones)
            entorno.registrar(carpeta / "inicializacion.csv")
            ok &= correcto
    finally:
        cerrar_cuda()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
