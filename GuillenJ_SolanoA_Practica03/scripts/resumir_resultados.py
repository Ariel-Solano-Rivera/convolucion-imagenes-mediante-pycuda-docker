"""Calcula mediana e IQR de mediciones completadas."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np


CLAVES = ("experimento", "modo_ejecucion", "entorno", "filtro", "mascara",
          "ancho", "alto", "concurrencia")
TIEMPOS = ("t_recepcion_ms", "t_decodificacion_ms", "t_espera_ms",
           "t_reserva_liberacion_ms", "t_h2d_ms", "t_kernel_ms", "t_d2h_ms",
           "t_gpu_total_ms", "t_codificacion_ms", "t_servidor_ms", "t_cliente_ms",
           "t_ronda_ms", "rendimiento_rps", "memoria_reservada_mb", "memoria_gpu_usada_mb")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entradas", nargs="+", type=Path)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    grupos = defaultdict(list)
    for ruta in args.entradas:
        with open(ruta, newline="", encoding="utf-8") as archivo:
            for fila in csv.DictReader(archivo):
                if fila["estado"] == "completada":
                    grupos[tuple(fila[c] for c in CLAVES)].append(fila)
    columnas = list(CLAVES) + ["repeticiones"]
    for tiempo in TIEMPOS:
        columnas += [f"{tiempo}_mediana", f"{tiempo}_q1", f"{tiempo}_q3"]
    filas_salida = []
    for clave, filas in sorted(grupos.items()):
        salida = dict(zip(CLAVES, clave))
        salida["repeticiones"] = len(filas)
        for tiempo in TIEMPOS:
            valores = [float(f[tiempo]) for f in filas if f.get(tiempo) not in ("", None)]
            for sufijo, percentil in (("mediana", 50), ("q1", 25), ("q3", 75)):
                salida[f"{tiempo}_{sufijo}"] = (
                    f"{float(np.percentile(valores, percentil)):.6f}" if valores else "")
        filas_salida.append(salida)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas_salida)
    print(f"Resumen escrito en {args.salida}: {len(filas_salida)} configuraciones")


if __name__ == "__main__":
    main()

