"""Mide ejecución PyCUDA directa o el servicio según la matriz obligatoria.

Alcance de las columnas de tiempo (todas en ms):
- t_recepcion_ms: solo servicio; lectura del cuerpo multipart en el servidor.
- t_decodificacion_ms, t_espera_ms, t_reserva_liberacion_ms, t_h2d_ms, t_kernel_ms,
  t_d2h_ms, t_gpu_total_ms, t_codificacion_ms: fases de webapp/procesamiento.py, idénticas
  en modo directo y en el servicio (H2D, kernel y D2H con eventos CUDA).
- t_servidor_ms: directo = procesamiento completo (decodificación→escritura) sin HTTP;
  servicio = recepción + procesamiento completo, medido por el servidor.
- t_cliente_ms: solo servicio; reloj del cliente desde el envío hasta descargar el PNG final.
- t_ronda_ms y rendimiento_rps: solo concurrencia; intervalo total de la ronda en el
  cliente y solicitudes exitosas / intervalo.
Nunca se restan relojes de procesos o máquinas distintos.
"""
import argparse
import csv
import hashlib
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from scripts.util_http import enviar_imagen
from webapp.procesador_gpu import ServicioGPU
from webapp.procesamiento import procesar_imagen


COLUMNAS = [
    "id_solicitud", "experimento", "modo_ejecucion", "entorno", "filtro", "mascara",
    "ancho", "alto", "sha256_entrada", "hilos", "bloques", "repeticion", "ronda",
    "concurrencia", "t_recepcion_ms", "t_decodificacion_ms", "t_espera_ms",
    "t_reserva_liberacion_ms", "t_h2d_ms", "t_kernel_ms", "t_d2h_ms", "t_gpu_total_ms",
    "t_codificacion_ms", "t_servidor_ms", "t_cliente_ms", "t_ronda_ms", "rendimiento_rps",
    "memoria_reservada_mb", "memoria_gpu_usada_mb", "unidad", "estado", "observaciones",
]
# Correspondencia columna CSV -> clave de tiempos_ms en la respuesta / procesamiento.
CAMPOS_TIEMPO = (
    ("t_recepcion_ms", "recepcion"), ("t_decodificacion_ms", "decodificacion_y_preparacion"),
    ("t_espera_ms", "espera_gpu"), ("t_reserva_liberacion_ms", "reserva_liberacion"),
    ("t_h2d_ms", "cpu_a_gpu"), ("t_kernel_ms", "kernel"), ("t_d2h_ms", "gpu_a_cpu"),
    ("t_gpu_total_ms", "gpu_total"), ("t_codificacion_ms", "codificacion_y_escritura"),
)


def sha256(ruta):
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def dimensiones(ruta):
    with Image.open(ruta) as imagen:
        return imagen.size


def configuraciones_servicio(datos, piloto):
    if piloto:
        return [("piloto", "media", 3, datos / "base_250.pgm")]
    return [
        ("resolucion", "media", 9, datos / "base_2000.pgm"),
        ("integracion|resolucion|filtros_mascara", "media", 9, datos / "base_4000.pgm"),
        ("resolucion", "media", 9, datos / "base_6000.pgm"),
        ("filtros_mascara", "media", 3, datos / "base_4000.pgm"),
        ("filtros_mascara", "media", 21, datos / "base_4000.pgm"),
        ("filtros_mascara", "nitidez", 3, datos / "base_4000.pgm"),
        ("filtros_mascara", "laplaciano", 3, datos / "base_4000.pgm"),
    ]


def fila_base(experimento, modo, entorno, filtro, mascara, ruta, repeticion,
              concurrencia=1, ronda=""):
    ancho, alto = dimensiones(ruta)
    hilos = 256
    fila = {columna: "" for columna in COLUMNAS}
    fila.update({
        "experimento": experimento, "modo_ejecucion": modo,
        "entorno": entorno, "filtro": filtro, "mascara": mascara, "ancho": ancho,
        "alto": alto, "sha256_entrada": sha256(ruta), "hilos": hilos,
        "bloques": (ancho * alto + hilos - 1) // hilos, "repeticion": repeticion,
        "ronda": ronda, "concurrencia": concurrencia, "unidad": "ms",
    })
    return fila


def completar_tiempos(fila, tiempos, memoria_reservada_mb=None, memoria_usada_mb=None):
    for destino, origen in CAMPOS_TIEMPO:
        if tiempos.get(origen) is not None:
            fila[destino] = f"{float(tiempos[origen]):.4f}"
    if memoria_reservada_mb is not None:
        fila["memoria_reservada_mb"] = f"{float(memoria_reservada_mb):.3f}"
    if memoria_usada_mb is not None:
        fila["memoria_gpu_usada_mb"] = f"{float(memoria_usada_mb):.1f}"
    if tiempos.get("inicio_frio") is not None:
        fila["observaciones"] = f"arranque_frio_ms={float(tiempos['inicio_frio']):.4f}"


def fila_respuesta(experimento, modo, entorno, filtro, mascara, ruta, repeticion,
                   respuesta, concurrencia=1, ronda=""):
    fila = fila_base(experimento, modo, entorno, filtro, mascara, ruta, repeticion,
                     concurrencia, ronda)
    cuerpo = respuesta.cuerpo
    fila["id_solicitud"] = cuerpo.get("id_solicitud", "")
    fila["t_cliente_ms"] = f"{respuesta.tiempo_cliente_ms:.4f}"
    if respuesta.estado_http != 201:
        fila["estado"] = f"error_http_{respuesta.estado_http}"
        fila["observaciones"] = cuerpo.get("error", "respuesta sin detalle")
        return fila
    tiempos = cuerpo["tiempos_ms"]
    gpu = cuerpo.get("gpu", {})
    completar_tiempos(fila, tiempos, gpu.get("memoria_reservada_mb"),
                      gpu.get("memoria_gpu_usada_mb"))
    fila["t_servidor_ms"] = f"{float(tiempos['servidor_total']):.4f}"
    fila["estado"] = "completada"
    return fila


def escribir_filas(ruta, filas):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)
            archivo.flush()


def medir_servicio(args):
    configuraciones = configuraciones_servicio(Path(args.datos), args.piloto)
    filas = []
    primera = True
    for experimento, filtro, mascara, ruta in configuraciones:
        if not ruta.exists():
            raise FileNotFoundError(ruta)
        if primera:
            respuesta_frio = enviar_imagen(args.url, ruta, filtro, mascara)
            filas.append(fila_respuesta("arranque_frio", "servicio_contenedor", args.entorno,
                                        filtro, mascara, ruta, 0, respuesta_frio))
            primera = False
        print(f"Calentamiento: {filtro} {mascara}x{mascara}, {ruta.name}", flush=True)
        enviar_imagen(args.url, ruta, filtro, mascara)
        for repeticion in range(1, args.repeticiones + 1):
            respuesta = enviar_imagen(args.url, ruta, filtro, mascara)
            fila = fila_respuesta(experimento, "servicio_contenedor", args.entorno,
                                  filtro, mascara, ruta, repeticion, respuesta)
            filas.append(fila)
            print(f"  repetición {repeticion}: {fila['estado']}", flush=True)

    if not args.piloto:
        ruta = Path(args.datos) / "base_4000.pgm"
        for concurrencia in (1, 2):
            for ronda in range(1, 6):
                inicio = time.perf_counter()
                with ThreadPoolExecutor(max_workers=concurrencia) as ejecutor:
                    futuros = [ejecutor.submit(enviar_imagen, args.url, ruta, "media", 9)
                               for _ in range(concurrencia)]
                    respuestas = [f.result() for f in futuros]
                intervalo = time.perf_counter() - inicio
                exitosas = sum(r.estado_http == 201 for r in respuestas)
                rendimiento = exitosas / intervalo if intervalo else 0.0
                for indice, respuesta in enumerate(respuestas, 1):
                    fila = fila_respuesta("concurrencia", "servicio_contenedor", args.entorno,
                                          "media", 9, ruta, indice, respuesta,
                                          concurrencia, ronda)
                    fila["t_ronda_ms"] = f"{intervalo * 1000.0:.4f}"
                    fila["rendimiento_rps"] = f"{rendimiento:.6f}"
                    filas.append(fila)
                print(f"Concurrencia {concurrencia}, ronda {ronda}: {exitosas}/"
                      f"{concurrencia} exitosas", flush=True)
    escribir_filas(args.salida, filas)
    return filas


def fila_directa(experimento, args, filtro, mascara, ruta, repeticion, resultado):
    fila = fila_base(experimento, "pycuda_directo", args.entorno, filtro, mascara, ruta,
                     repeticion)
    gpu = resultado.gpu
    fila["id_solicitud"] = str(uuid.uuid4())
    completar_tiempos(fila, resultado.tiempos_ms, gpu.memoria_reservada_bytes / 2**20,
                      None if gpu.memoria_gpu_usada_bytes is None
                      else gpu.memoria_gpu_usada_bytes / 2**20)
    fila["t_servidor_ms"] = f"{resultado.tiempos_ms['procesamiento_total']:.4f}"
    fila["estado"] = "completada"
    return fila


def medir_directo(args):
    """Mismo procesamiento que el servicio (webapp/procesamiento.py), sin HTTP."""
    datos = Path(args.datos)
    ruta = datos / ("base_250.pgm" if args.piloto else "base_4000.pgm")
    filtro, mascara = ("media", 3) if args.piloto else ("media", 9)
    contenido = ruta.read_bytes()  # equivale al archivo ya recibido por el servidor
    servicio = ServicioGPU(args.practica02, 256, 1)
    trabajo = Path(args.directorio_trabajo)
    filas = []

    def una_ejecucion():
        carpeta = trabajo / str(uuid.uuid4())
        carpeta.mkdir(parents=True)
        try:
            return procesar_imagen(contenido, filtro, mascara, servicio, carpeta,
                                   36_000_000, 170_000_000)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    try:
        filas.append(fila_directa("arranque_frio", args, filtro, mascara, ruta, 0,
                                  una_ejecucion()))
        print("Calentamiento de PyCUDA directo", flush=True)
        una_ejecucion()
        for repeticion in range(1, args.repeticiones + 1):
            filas.append(fila_directa("piloto" if args.piloto else "integracion", args,
                                      filtro, mascara, ruta, repeticion, una_ejecucion()))
            print(f"  repetición {repeticion}: completada", flush=True)
    finally:
        servicio.cerrar()
    escribir_filas(args.salida, filas)
    return filas


def analizar_argumentos():
    raiz = Path(__file__).resolve().parents[1]
    p02 = raiz.parent / "GuillenJ_SolanoA_Practica0"
    analizador = argparse.ArgumentParser()
    sub = analizador.add_subparsers(dest="modo", required=True)
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--datos", type=Path, default=p02 / "datos")
    comun.add_argument("--repeticiones", type=int, default=5)
    comun.add_argument("--entorno", required=True)
    comun.add_argument("--salida", type=Path, required=True)
    comun.add_argument("--piloto", action="store_true")
    directo = sub.add_parser("directo", parents=[comun])
    directo.add_argument("--practica02", type=Path, default=p02)
    directo.add_argument("--directorio-trabajo", type=Path,
                         default=raiz / "runtime" / "directo",
                         help="Escritura de resultados temporales, como en el servicio")
    servicio = sub.add_parser("servicio", parents=[comun])
    servicio.add_argument("--url", default="http://127.0.0.1:8000")
    return analizador.parse_args()


def main():
    args = analizar_argumentos()
    if args.repeticiones < 1:
        raise ValueError("repeticiones debe ser al menos 1")
    filas = medir_directo(args) if args.modo == "directo" else medir_servicio(args)
    fallas = sum(f["estado"] != "completada" for f in filas)
    print(f"{len(filas)} filas escritas en {args.salida}; fallas: {fallas}")
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
