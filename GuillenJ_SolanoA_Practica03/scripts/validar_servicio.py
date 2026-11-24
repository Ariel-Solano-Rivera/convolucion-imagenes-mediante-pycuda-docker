"""Valida manualmente, numéricamente y con errores controlados el servicio HTTP."""
import argparse
import csv
import shutil
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.util_http import (descargar, enviar_bytes, enviar_imagen,
                               enviar_longitud_excesiva)
from webapp.filtros import crear_mascara
from webapp.procesador_gpu import ServicioGPU
from webapp.procesamiento import procesar_imagen

HILOS = 256
# Configuraciones de máscara que el servicio permite.
CONFIGURACIONES = (("media", 3), ("media", 9), ("media", 21), ("nitidez", 3),
                   ("laplaciano", 3))


def escribir_csv(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


def cargar_npy(url, relativa):
    return np.load(BytesIO(descargar(url, relativa)), allow_pickle=False)


def guardar_evidencia_visual(args, filtro, cuerpo):
    destino = args.salida.parent / "evidencia" / "visual"
    destino.mkdir(parents=True, exist_ok=True)
    if not (destino / "original.png").exists():
        (destino / "original.png").write_bytes(descargar(args.url, cuerpo["original_url"]))
    resultado = destino / f"{filtro}.png"
    resultado.write_bytes(descargar(args.url, cuerpo["resultado_url"]))
    with Image.open(resultado) as imagen:
        lado = min(600, imagen.width, imagen.height)
        izquierda = (imagen.width - lado) // 2
        superior = (imagen.height - lado) // 2
        imagen.crop((izquierda, superior, izquierda + lado, superior + lado)).save(
            destino / f"{filtro}_recorte.png")
    original = destino / "original.png"
    recorte_original = destino / "original_recorte.png"
    if not recorte_original.exists():
        with Image.open(original) as imagen:
            lado = min(600, imagen.width, imagen.height)
            izquierda = (imagen.width - lado) // 2
            superior = (imagen.height - lado) // 2
            imagen.crop((izquierda, superior, izquierda + lado, superior + lado)).save(
                recorte_original)


def procesar_directo(procesador, contenido, filtro, k, trabajo):
    """PyCUDA directo con la misma función que usa el servicio (sin HTTP)."""
    carpeta = Path(trabajo) / str(uuid.uuid4())
    carpeta.mkdir(parents=True)
    try:
        return procesar_imagen(contenido, filtro, k, procesador, carpeta,
                               36_000_000, 170_000_000)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def validar_equivalencia(args):
    ruta = Path(args.imagen)
    contenido = ruta.read_bytes()
    procesador = ServicioGPU(args.practica02, HILOS, 1)
    filas = []
    try:
        for filtro, k in (("media", 3), ("nitidez", 3), ("laplaciano", 3)):
            directo_completo = procesar_directo(procesador, contenido, filtro, k,
                                                args.directorio_trabajo)
            directo = directo_completo.gpu
            ancho, alto = directo_completo.preparada.ancho, directo_completo.preparada.alto
            respuesta = enviar_imagen(args.url, ruta, filtro, k)
            if respuesta.estado_http != 201:
                filas.append({
                    "prueba": "directo_servicio", "filtro": filtro, "mascara": k,
                    "ancho": ancho, "alto": alto, "error_max": "", "error_medio": "",
                    "tolerancia": args.tolerancia, "resultado": "FALLA",
                    "observaciones": respuesta.cuerpo.get("error", "error HTTP"),
                })
                continue
            servicio = cargar_npy(args.url, respuesta.cuerpo["resultado_crudo_url"])
            guardar_evidencia_visual(args, filtro, respuesta.cuerpo)
            diferencia = np.abs(directo.datos.astype(np.float32) - servicio.astype(np.float32))
            maximo = float(np.max(diferencia))
            medio = float(np.mean(diferencia, dtype=np.float64))
            filas.append({
                "prueba": "directo_servicio", "filtro": filtro, "mascara": k,
                "ancho": ancho, "alto": alto, "error_max": f"{maximo:.8e}",
                "error_medio": f"{medio:.8e}", "tolerancia": args.tolerancia,
                "resultado": "OK" if maximo <= args.tolerancia else "FALLA",
                "observaciones": f"solicitud={respuesta.cuerpo['id_solicitud']}",
            })
    finally:
        procesador.cerrar()
    escribir_csv(args.salida / "validacion_directo_servicio.csv",
                 list(filas[0].keys()), filas)
    return filas


def referencia_cpu(imagen, mascara, k):
    """Convolución de referencia en CPU, float32, extensión con ceros y orden j→i del kernel.

    Solo valida resultados (no es una versión medida): cada término se acumula en float32
    en el mismo orden que el kernel, por lo que la diferencia esperada es del orden del
    redondeo de float32 (contracción FMA en la GPU).
    """
    alto, ancho = imagen.shape
    radio = k // 2
    extendida = np.zeros((alto + 2 * radio, ancho + 2 * radio), dtype=np.float32)
    extendida[radio:radio + alto, radio:radio + ancho] = imagen
    suma = np.zeros((alto, ancho), dtype=np.float32)
    for j in range(-radio, radio + 1):
        for i in range(-radio, radio + 1):
            coeficiente = mascara[(j + radio) * k + i + radio]
            suma += extendida[radio + j:radio + j + alto, radio + i:radio + i + ancho] * coeficiente
    return suma.reshape(-1)


def validar_bordes_y_cobertura(args):
    """Imagen 1013×757 (n no múltiplo de 256): toda la imagen, bordes y último bloque."""
    ruta = Path(args.imagen)
    with Image.open(ruta) as imagen:
        entrada = np.asarray(imagen.convert("L"), dtype=np.uint8).astype(np.float32)
    alto, ancho = entrada.shape
    n = ancho * alto
    bloques = (n + HILOS - 1) // HILOS
    inicio_ultimo_bloque = (bloques - 1) * HILOS
    mascara_bordes = np.zeros((alto, ancho), dtype=bool)
    mascara_bordes[[0, -1], :] = True
    mascara_bordes[:, [0, -1]] = True
    regiones = {
        "imagen_completa": np.ones(n, dtype=bool),
        "bordes": mascara_bordes.reshape(-1),
        "ultimo_bloque": np.arange(n) >= inicio_ultimo_bloque,
    }
    filas = []
    for filtro, k in CONFIGURACIONES:
        respuesta = enviar_imagen(args.url, ruta, filtro, k)
        if respuesta.estado_http != 201:
            filas.append({"filtro": filtro, "mascara": k, "region": "solicitud",
                          "pixeles": n, "bloques": bloques, "hilos_bloque": HILOS,
                          "hilos_sobrantes": bloques * HILOS - n, "pixeles_finitos": "",
                          "error_max": "", "error_medio": "", "tolerancia": args.tolerancia,
                          "resultado": "FALLA",
                          "observaciones": respuesta.cuerpo.get("error", "error HTTP")})
            continue
        servicio = cargar_npy(args.url, respuesta.cuerpo["resultado_crudo_url"])
        referencia = referencia_cpu(entrada, crear_mascara(filtro, k), k)
        finitos = int(np.isfinite(servicio).sum())
        for region, seleccion in regiones.items():
            diferencia = np.abs(servicio[seleccion] - referencia[seleccion])
            maximo = float(np.max(diferencia))
            correcto = (servicio.size == n and finitos == n and maximo <= args.tolerancia)
            filas.append({
                "filtro": filtro, "mascara": k, "region": region,
                "pixeles": int(seleccion.sum()), "bloques": bloques, "hilos_bloque": HILOS,
                "hilos_sobrantes": bloques * HILOS - n, "pixeles_finitos": finitos,
                "error_max": f"{maximo:.8e}",
                "error_medio": f"{float(np.mean(diferencia, dtype=np.float64)):.8e}",
                "tolerancia": args.tolerancia, "resultado": "OK" if correcto else "FALLA",
                "observaciones": f"solicitud={respuesta.cuerpo['id_solicitud']}; "
                                 "referencia CPU float32 antes del recorte",
            })
    escribir_csv(args.salida / "bordes_cobertura.csv", list(filas[0].keys()), filas)
    return filas


def validar_manual(args):
    ruta_p02 = str(Path(args.practica02))
    if ruta_p02 not in sys.path:
        sys.path.insert(0, ruta_p02)
    from src.python.comun.experimentos import CASOS_MANUALES, IMAGEN_MANUAL

    imagen = Image.fromarray(IMAGEN_MANUAL.astype(np.uint8).reshape(5, 5), mode="L")
    memoria = BytesIO()
    imagen.save(memoria, format="PNG")
    contenido = memoria.getvalue()
    indices = {"media": 1, "nitidez": 2, "laplaciano": 3}
    filas = []
    for filtro, indice in indices.items():
        respuesta = enviar_bytes(args.url, "matriz_5x5.png", contenido, filtro, 3)
        if respuesta.estado_http != 201:
            filas.append({"filtro": filtro, "fila": "", "columna": "", "esperado": "",
                          "obtenido": "", "error": "", "resultado": "FALLA"})
            continue
        salida = cargar_npy(args.url, respuesta.cuerpo["resultado_crudo_url"])
        for mascara_indice, fila, columna, esperado in CASOS_MANUALES:
            if mascara_indice != indice:
                continue
            obtenido = float(salida[fila * 5 + columna])
            error = abs(obtenido - float(esperado))
            filas.append({
                "filtro": filtro, "fila": fila, "columna": columna,
                "esperado": f"{float(esperado):.6f}", "obtenido": f"{obtenido:.6f}",
                "error": f"{error:.8e}", "resultado": "OK" if error <= 1e-3 else "FALLA",
            })
    escribir_csv(args.salida / "prueba_manual_servicio.csv", list(filas[0].keys()), filas)
    return filas


def probar_entradas_invalidas(args):
    imagen_valida = Path(args.imagen).read_bytes()
    casos = [
        ("archivo_no_valido", enviar_bytes(args.url, "falso.png", b"no es imagen", "media", 3), 400),
        ("filtro_desconocido", enviar_bytes(args.url, "entrada.pgm", imagen_valida, "otro", 3), 400),
        ("mascara_no_permitida", enviar_bytes(args.url, "entrada.pgm", imagen_valida, "media", 5), 400),
    ]
    if not args.omitir_archivo_grande:
        casos.append(("archivo_supera_limite",
                      enviar_longitud_excesiva(args.url, args.limite_bytes + 1), 413))
    filas = [{
        "caso": nombre, "http_esperado": esperado, "http_obtenido": respuesta.estado_http,
        "resultado": "OK" if respuesta.estado_http == esperado else "FALLA",
        "mensaje": respuesta.cuerpo.get("error", ""),
    } for nombre, respuesta, esperado in casos]
    escribir_csv(args.salida / "entradas_invalidas.csv", list(filas[0].keys()), filas)
    return filas


def probar_aislamiento(args):
    ruta = Path(args.imagen)
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        futuros = [
            ejecutor.submit(enviar_imagen, args.url, ruta, "media", 3),
            ejecutor.submit(enviar_imagen, args.url, ruta, "laplaciano", 3),
        ]
        respuestas = [f.result() for f in futuros]
    ids = [r.cuerpo.get("id_solicitud", "") for r in respuestas]
    rutas = [r.cuerpo.get("resultado_crudo_url", "") for r in respuestas]
    correcto = (all(r.estado_http == 201 for r in respuestas) and len(set(ids)) == 2
                and len(set(rutas)) == 2)
    filas = [{
        "cliente": indice + 1, "http": respuesta.estado_http, "id_solicitud": ids[indice],
        "resultado_url": rutas[indice], "aislamiento": "OK" if correcto else "FALLA",
    } for indice, respuesta in enumerate(respuestas)]
    escribir_csv(args.salida / "aislamiento_solicitudes.csv", list(filas[0].keys()), filas)
    return filas


def rafaga_cola(args, clientes):
    """Envía `clientes` solicitudes a la vez y devuelve [(cliente, respuesta)]."""
    ruta = Path(args.imagen_cola)
    barrera = threading.Barrier(clientes)

    def enviar(indice):
        barrera.wait()
        return indice, enviar_imagen(args.url, ruta, "media", 21)

    with ThreadPoolExecutor(max_workers=clientes) as ejecutor:
        futuros = [ejecutor.submit(enviar, indice) for indice in range(1, clientes + 1)]
        return sorted(f.result() for f in futuros)


def probar_limite_cola(args, clientes=4, max_rondas=5):
    """Satura el servicio real y exige al menos un rechazo HTTP 429 controlado.

    El cupo se toma después de recibir y decodificar la imagen, así que el límite solo se
    alcanza si tres solicitudes coinciden en la fase de GPU; eso depende de cuánto tarden la
    subida y la GPU en ese momento. Por eso la ráfaga se repite hasta `max_rondas` veces,
    se registran todas las rondas y la prueba termina en la primera que produce un 429.
    Cualquier respuesta distinta de 201 o 429 es una falla.
    """
    filas = []
    for ronda in range(1, max_rondas + 1):
        respuestas = rafaga_cola(args, clientes)
        conteo = Counter(respuesta.estado_http for _indice, respuesta in respuestas)
        filas.extend({
            "ronda": ronda,
            "cliente": indice,
            "http": respuesta.estado_http,
            "id_solicitud": respuesta.cuerpo.get("id_solicitud", ""),
            "mensaje": respuesta.cuerpo.get("error", ""),
            "aceptadas": conteo[201],
            "rechazadas_429": conteo[429],
        } for indice, respuesta in respuestas)
        if conteo[429] >= 1 or set(conteo) - {201, 429}:
            break
    inesperadas = [f for f in filas if f["http"] not in (201, 429)]
    alcanzado = any(f["http"] == 429 for f in filas)
    resultado = "OK" if alcanzado and not inesperadas else "FALLA"
    for fila in filas:
        fila["resultado"] = resultado
    escribir_csv(args.salida / "cola_solicitudes.csv", list(filas[0].keys()), filas)
    print(f"Límite de cola: {len(filas) // clientes} ronda(s); "
          f"{'se alcanzó (HTTP 429)' if alcanzado else 'no se alcanzó'}")
    return filas


def argumentos():
    raiz = Path(__file__).resolve().parents[1]
    p02 = raiz.parent / "GuillenJ_SolanoA_Practica0"
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--practica02", type=Path, default=p02)
    parser.add_argument("--imagen", type=Path, default=p02 / "datos" / "no_multiplo_1013x757.pgm")
    parser.add_argument("--imagen-cola", type=Path, default=p02 / "datos" / "base_6000.pgm")
    parser.add_argument("--salida", type=Path, default=raiz / "resultados" / "pruebas")
    parser.add_argument("--tolerancia", type=float, default=1e-2)
    parser.add_argument("--limite-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--omitir-archivo-grande", action="store_true")
    parser.add_argument("--omitir-cola", action="store_true")
    parser.add_argument("--directorio-trabajo", type=Path, default=raiz / "runtime" / "directo")
    return parser.parse_args()


def main():
    args = argumentos()
    grupos = [validar_manual(args), validar_bordes_y_cobertura(args),
              validar_equivalencia(args), probar_entradas_invalidas(args),
              probar_aislamiento(args)]
    if not args.omitir_cola:
        grupos.append(probar_limite_cola(args))
    filas = [fila for grupo in grupos for fila in grupo]
    fallas = sum(fila.get("resultado", fila.get("aislamiento")) == "FALLA" for fila in filas)
    print(f"Validación terminada: {len(filas)} comprobaciones, {fallas} fallas")
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
