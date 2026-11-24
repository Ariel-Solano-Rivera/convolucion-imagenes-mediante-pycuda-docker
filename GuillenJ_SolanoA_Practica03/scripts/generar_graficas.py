"""Genera gráficas solo desde el CSV resumido de la práctica 03 (medianas; barras = IQR)."""
import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Fases del servidor en el orden en que ocurren (mismo alcance en directo y servicio).
FASES = (
    ("t_recepcion_ms", "Recepción HTTP", "#9ecae1"),
    ("t_decodificacion_ms", "Decodificación y preparación", "#6baed6"),
    ("t_espera_ms", "Espera en cola", "#c6dbef"),
    ("t_reserva_liberacion_ms", "Reserva/liberación GPU", "#fdae6b"),
    ("t_h2d_ms", "CPU→GPU", "#fd8d3c"),
    ("t_kernel_ms", "Kernel", "#e6550d"),
    ("t_d2h_ms", "GPU→CPU", "#a63603"),
    ("t_codificacion_ms", "Codificación y escritura", "#756bb1"),
)


def leer(ruta):
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def numero(fila, columna):
    valor = fila.get(columna, "")
    return float(valor) if valor not in ("", None) else 0.0


def barras_error(filas, columna):
    medianas = [numero(f, f"{columna}_mediana") for f in filas]
    inferior = [m - numero(f, f"{columna}_q1") for m, f in zip(medianas, filas)]
    superior = [numero(f, f"{columna}_q3") - m for m, f in zip(medianas, filas)]
    return medianas, [inferior, superior]


def guardar_barras(filas, etiquetas, columna, titulo, ylabel, destino):
    if not filas:
        return
    figura, eje = plt.subplots(figsize=(9, 5))
    medianas, error = barras_error(filas, columna)
    eje.bar([etiquetas(f) for f in filas], medianas, yerr=error, capsize=4, color="#2b8cbe")
    eje.set_title(titulo)
    eje.set_ylabel(ylabel)
    eje.tick_params(axis="x", rotation=20)
    eje.grid(axis="y", alpha=.25)
    figura.tight_layout()
    figura.savefig(destino, dpi=160)
    plt.close(figura)


def guardar_distribucion(filas, etiquetas, titulo, destino):
    """Barras apiladas por fase del servidor + barra del cliente (relojes separados)."""
    if not filas:
        return
    figura, eje = plt.subplots(figsize=(11, 5.5))
    nombres = [etiquetas(f) for f in filas]
    posiciones = range(len(filas))
    base = [0.0] * len(filas)
    for columna, nombre, color in FASES:
        valores = [numero(f, f"{columna}_mediana") for f in filas]
        eje.bar([p - 0.2 for p in posiciones], valores, width=0.4, bottom=base,
                label=nombre, color=color)
        base = [b + v for b, v in zip(base, valores)]
    cliente = [numero(f, "t_cliente_ms_mediana") for f in filas]
    eje.bar([p + 0.2 for p in posiciones], cliente, width=0.4, color="#636363",
            label="Cliente total (otro reloj)")
    eje.set_xticks(list(posiciones), nombres, rotation=15)
    eje.set_ylabel("Mediana (ms)")
    eje.set_title(titulo)
    eje.legend(fontsize=8, ncol=2)
    eje.grid(axis="y", alpha=.25)
    figura.tight_layout()
    figura.savefig(destino, dpi=160)
    plt.close(figura)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("resumen", type=Path)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    filas = leer(args.resumen)
    args.salida.mkdir(parents=True, exist_ok=True)
    servicio = [f for f in filas if f["modo_ejecucion"] == "servicio_contenedor"
                and f["concurrencia"] == "1" and f["experimento"] not in
                ("arranque_frio", "concurrencia")]
    resolucion = sorted([f for f in servicio if "resolucion" in f["experimento"]],
                        key=lambda f: int(f["ancho"]))
    guardar_barras(resolucion, lambda f: f'{f["ancho"]}×{f["alto"]}', "t_cliente_ms",
                   "Latencia total del cliente por resolución (media 9×9)",
                   "Tiempo del cliente (ms)", args.salida / "resolucion_cliente.png")
    guardar_barras(resolucion, lambda f: f'{f["ancho"]}×{f["alto"]}', "t_kernel_ms",
                   "Tiempo de kernel por resolución (media 9×9, servicio)",
                   "Kernel (ms, eventos CUDA)", args.salida / "resolucion_kernel.png")
    guardar_distribucion(resolucion, lambda f: f'{f["ancho"]}×{f["alto"]}',
                         "Distribución del tiempo por resolución (servicio, media 9×9)",
                         args.salida / "distribucion_resolucion.png")
    filtros = [f for f in servicio if "filtros_mascara" in f["experimento"]]
    guardar_barras(filtros, lambda f: f'{f["filtro"]} {f["mascara"]}×{f["mascara"]}',
                   "t_servidor_ms", "Procesamiento del servidor por filtro (4000×4000)",
                   "Servidor (ms)", args.salida / "filtros_servicio.png")
    guardar_barras(filtros, lambda f: f'{f["filtro"]} {f["mascara"]}×{f["mascara"]}',
                   "t_kernel_ms", "Tiempo de kernel por filtro y máscara (4000×4000)",
                   "Kernel (ms, eventos CUDA)", args.salida / "filtros_kernel.png")
    guardar_distribucion(filtros, lambda f: f'{f["filtro"]} {f["mascara"]}×{f["mascara"]}',
                         "Distribución del tiempo por filtro (servicio, 4000×4000)",
                         args.salida / "distribucion_filtros.png")
    integracion = [f for f in filas if "integracion" in f["experimento"]]
    guardar_barras(integracion, lambda f: f'{f["modo_ejecucion"]}\n{f["entorno"]}',
                   "t_gpu_total_ms", "PyCUDA directo (anfitrión/contenedor) y servicio",
                   "GPU total: H2D + kernel + D2H (ms)", args.salida / "integracion.png")
    guardar_distribucion(integracion, lambda f: f'{f["modo_ejecucion"]}\n{f["entorno"]}',
                         "Distribución del tiempo: directo vs servicio (media 9×9, 4000²)",
                         args.salida / "distribucion_integracion.png")
    concurrencia = [f for f in filas if f["experimento"] == "concurrencia"]
    guardar_barras(concurrencia, lambda f: f'{f["concurrencia"]} cliente(s)', "t_cliente_ms",
                   "Latencia individual con solicitudes concurrentes",
                   "Tiempo del cliente (ms)", args.salida / "concurrencia.png")
    guardar_barras(concurrencia, lambda f: f'{f["concurrencia"]} cliente(s)',
                   "rendimiento_rps", "Solicitudes exitosas por segundo (por ronda)",
                   "Solicitudes/s", args.salida / "concurrencia_rendimiento.png")
    guardar_barras(concurrencia, lambda f: f'{f["concurrencia"]} cliente(s)', "t_espera_ms",
                   "Espera en la cola del trabajador CUDA", "Espera (ms)",
                   args.salida / "concurrencia_espera.png")
    print(f"Gráficas disponibles en {args.salida}")


if __name__ == "__main__":
    main()
