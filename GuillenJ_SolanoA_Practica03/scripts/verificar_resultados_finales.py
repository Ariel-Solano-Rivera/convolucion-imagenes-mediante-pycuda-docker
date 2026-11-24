"""Comprueba que la corrida final contiene exactamente la matriz exigida."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def leer_csv(ruta):
    if not ruta.is_file():
        raise AssertionError(f"No existe {ruta}")
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def exigir(condicion, mensaje):
    if not condicion:
        raise AssertionError(mensaje)


COLUMNAS_OBLIGATORIAS = ("t_decodificacion_ms", "t_espera_ms", "t_reserva_liberacion_ms",
                         "t_h2d_ms", "t_kernel_ms", "t_d2h_ms", "t_gpu_total_ms",
                         "t_codificacion_ms", "t_servidor_ms", "memoria_reservada_mb",
                         "memoria_gpu_usada_mb")


def validar_completadas(filas, nombre):
    fallas = [f for f in filas if f.get("estado") != "completada"]
    exigir(not fallas, f"{nombre}: hay {len(fallas)} filas no completadas")
    for columna in COLUMNAS_OBLIGATORIAS:
        exigir(all(f.get(columna) not in ("", None) for f in filas),
               f"{nombre}: la columna {columna} tiene valores vacíos")
    ids = [f.get("id_solicitud", "") for f in filas]
    exigir(all(ids), f"{nombre}: hay identificadores de solicitud vacios")
    exigir(len(ids) == len(set(ids)), f"{nombre}: hay identificadores repetidos")


def validar_directo(ruta, entorno):
    filas = leer_csv(ruta)
    exigir(len(filas) == 6, f"{ruta.name}: se esperaban 6 filas (frio + 5), hay {len(filas)}")
    validar_completadas(filas, ruta.name)
    frio = [f for f in filas if f["experimento"] == "arranque_frio"]
    estable = [f for f in filas if f["experimento"] == "integracion"]
    exigir(len(frio) == 1 and len(estable) == 5,
           f"{ruta.name}: debe contener un arranque frio y cinco repeticiones")
    for fila in filas:
        exigir(fila["modo_ejecucion"] == "pycuda_directo", f"{ruta.name}: modo incorrecto")
        exigir(fila["entorno"] == entorno, f"{ruta.name}: entorno incorrecto")
        exigir((fila["filtro"], fila["mascara"], fila["ancho"], fila["alto"], fila["hilos"])
               == ("media", "9", "4000", "4000", "256"),
               f"{ruta.name}: configuracion de integracion incorrecta")


def validar_servicio(ruta):
    filas = leer_csv(ruta)
    exigir(len(filas) == 51,
           f"{ruta.name}: se esperaban 51 filas (1 frio + 35 matriz + 15 concurrencia), hay {len(filas)}")
    validar_completadas(filas, ruta.name)
    exigir(all(f.get("t_recepcion_ms") and f.get("t_cliente_ms") for f in filas),
           f"{ruta.name}: faltan tiempos de recepción o del cliente")
    frio = [f for f in filas if f["experimento"] == "arranque_frio"]
    concurrencia = [f for f in filas if f["experimento"] == "concurrencia"]
    exigir(all(f.get("t_ronda_ms") and f.get("rendimiento_rps") for f in concurrencia),
           f"{ruta.name}: concurrencia sin intervalo de ronda o rendimiento")
    matriz = [f for f in filas if f["experimento"] not in ("arranque_frio", "concurrencia")]
    exigir(len(frio) == 1, f"{ruta.name}: debe existir un unico arranque frio")
    exigir(len(matriz) == 35, f"{ruta.name}: la matriz estable debe tener 35 filas")
    exigir(len(concurrencia) == 15, f"{ruta.name}: concurrencia debe tener 15 filas")

    esperadas = Counter({
        ("media", "9", "2000", "2000"): 5,
        ("media", "9", "4000", "4000"): 5,
        ("media", "9", "6000", "6000"): 5,
        ("media", "3", "4000", "4000"): 5,
        ("media", "21", "4000", "4000"): 5,
        ("nitidez", "3", "4000", "4000"): 5,
        ("laplaciano", "3", "4000", "4000"): 5,
    })
    obtenidas = Counter((f["filtro"], f["mascara"], f["ancho"], f["alto"]) for f in matriz)
    exigir(obtenidas == esperadas,
           f"{ruta.name}: la matriz de resoluciones/filtros no coincide: {dict(obtenidas)}")
    cantidades_concurrencia = Counter(f["concurrencia"] for f in concurrencia)
    exigir(cantidades_concurrencia == Counter({"1": 5, "2": 10}),
           f"{ruta.name}: rondas de concurrencia incorrectas: {dict(cantidades_concurrencia)}")
    for nivel in ("1", "2"):
        rondas = Counter(f["ronda"] for f in concurrencia if f["concurrencia"] == nivel)
        exigir(rondas == Counter({str(i): int(nivel) for i in range(1, 6)}),
               f"{ruta.name}: rondas incorrectas para concurrencia {nivel}: {dict(rondas)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resultados", type=Path,
                        default=Path(__file__).resolve().parents[1] / "resultados")
    parser.add_argument("--sin-copia-limpia", action="store_true")
    args = parser.parse_args()
    mediciones = args.resultados / "mediciones"
    validar_directo(mediciones / "directo_anfitrion.csv", "anfitrion")
    validar_directo(mediciones / "directo_contenedor.csv", "contenedor")
    validar_servicio(mediciones / "servicio.csv")
    resumen = leer_csv(mediciones / "resumen.csv")
    exigir(resumen, "resumen.csv esta vacio")
    graficas = args.resultados / "graficas"
    for nombre in ("resolucion_cliente.png", "resolucion_kernel.png",
                   "distribucion_resolucion.png", "filtros_servicio.png",
                   "filtros_kernel.png", "distribucion_filtros.png", "integracion.png",
                   "distribucion_integracion.png", "concurrencia.png",
                   "concurrencia_rendimiento.png", "concurrencia_espera.png"):
        ruta = graficas / nombre
        exigir(ruta.is_file() and ruta.stat().st_size > 0, f"Falta la grafica {ruta}")

    commits = set()
    for nombre in ("entorno_anfitrion_final.json", "entorno_contenedor_final.json"):
        ruta = mediciones / nombre
        exigir(ruta.is_file(), f"Falta {ruta}")
        entorno = json.loads(ruta.read_text(encoding="utf-8-sig"))
        commits.add(entorno["repositorio"]["commit_practica03"])
        exigir(entorno["equipo"].get("ram_total_gib"), f"{nombre}: falta la RAM")
        exigir(entorno["repositorio"]["arbol_limpio"] is True,
               f"{nombre}: el árbol no quedó verificado como limpio")
        exigir(entorno["repositorio"]["commit_practica03"] not in ("", "NO_DECLARADO"),
               f"{nombre}: falta commit de práctica 03")
        exigir(entorno["repositorio"]["commit_origen_practica02"] not in ("", "NO_DECLARADO"),
               f"{nombre}: falta commit de práctica 02")

    exigir(len(commits) == 1, f"Los entornos registran commits distintos: {commits}")
    commit = commits.pop()
    contenedor = json.loads((mediciones / "entorno_contenedor_final.json")
                            .read_text(encoding="utf-8-sig"))
    exigir(contenedor["contenedor"].get("commit_en_imagen") == commit,
           "La imagen no fue construida con el commit medido (etiqueta COMMIT_PRACTICA03)")

    pruebas = args.resultados / "pruebas"
    for ruta in pruebas.glob("*.csv"):
        filas = leer_csv(ruta)
        exigir(not any(f.get("resultado") == "FALLA" or f.get("aislamiento") == "FALLA"
                       for f in filas), f"{ruta.name}: contiene fallas")
    invalidas = leer_csv(pruebas / "entradas_invalidas.csv")
    exigir(any(f["caso"] == "archivo_supera_limite" and f["http_obtenido"] == "413"
               for f in invalidas), "Falta evidencia HTTP 413")
    cola = leer_csv(pruebas / "cola_solicitudes.csv")
    exigir(any(f["http"] == "429" for f in cola), "Falta evidencia HTTP 429")

    bordes = leer_csv(pruebas / "bordes_cobertura.csv")
    exigir({f["region"] for f in bordes} == {"imagen_completa", "bordes", "ultimo_bloque"},
           "bordes_cobertura.csv no cubre imagen completa, bordes y último bloque")

    evidencia_dir = args.resultados / "evidencia"
    for nombre in ("construccion_docker.txt", "imagen_docker.json", "salud_servicio.json",
                   "contenedor_en_ejecucion.txt", "nvidia_smi_contenedor.txt",
                   "log_contenedor_final.txt", "log_sin_gpu.txt"):
        ruta = evidencia_dir / nombre
        exigir(ruta.is_file() and ruta.stat().st_size > 0, f"Falta la evidencia {ruta}")
    sin_gpu = json.loads((evidencia_dir / "sin_gpu.json").read_text(encoding="utf-8-sig"))
    exigir(sin_gpu.get("resultado") == "OK", "La prueba sin GPU no dio el diagnóstico 503")
    if not args.sin_copia_limpia:
        copia = json.loads((evidencia_dir / "copia_limpia.json").read_text(encoding="utf-8-sig"))
        exigir(copia.get("resultado") == "OK" and copia.get("commit_clonado") == commit,
               "La construcción desde copia limpia no corresponde al commit medido")

    cliente = args.resultados / "evidencia" / "cliente_distinto.json"
    exigir(cliente.is_file(), "Falta evidencia del cliente distinto")
    evidencia = json.loads(cliente.read_text(encoding="utf-8-sig"))
    exigir(evidencia.get("resultado") == "OK" and evidencia.get("http") == 201,
           "La demostración desde cliente distinto no fue exitosa")
    print("OK: 63 mediciones con fases y memoria, validaciones (manual, bordes, 413/429), "
          "cliente distinto, sin GPU, copia limpia, entornos, resumen y gráficas.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(f"FALLA: {error}") from error
