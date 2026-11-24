"""Contrato HTTP de procesamiento de imágenes (solo HTTP; el cálculo está en procesamiento.py)."""
import shutil
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory, url_for
from werkzeug.exceptions import HTTPException

from .almacenamiento import id_solicitud_valido, limpiar_resultados_expirados, nuevo_id_solicitud
from .errores import EntradaInvalida, ErrorServicio
from .procesamiento import procesar_imagen
from .sistema import datos_equipo

api = Blueprint("api", __name__, url_prefix="/api")


def respuesta_error(error, solicitud_id=None):
    cuerpo = {"error": str(error), "codigo": error.codigo}
    if solicitud_id:
        cuerpo["id_solicitud"] = solicitud_id
    return jsonify(cuerpo), error.http


@api.post("/convoluciones")
def convolucionar():
    """Procesa una imagen y entrega URLs de los resultados aislados por solicitud."""
    inicio = time.perf_counter()
    solicitud_id = nuevo_id_solicitud()
    carpeta = Path(current_app.config["DIRECTORIO_RESULTADOS"]) / solicitud_id
    try:
        limpiar_resultados_expirados(current_app.config["DIRECTORIO_RESULTADOS"],
                                     current_app.config["RETENCION_RESULTADOS_SEGUNDOS"])
        # Leer request.files obliga a recibir y analizar el cuerpo multipart completo.
        archivo = request.files.get("imagen")
        filtro = request.form.get("filtro")
        mascara = request.form.get("mascara")
        if archivo is None:
            raise EntradaInvalida("Debe enviar el campo de archivo 'imagen'.")
        contenido = archivo.read()
        fin_recepcion = time.perf_counter()
        carpeta.mkdir(parents=True, exist_ok=False)
        resultado = procesar_imagen(
            contenido, filtro, mascara, current_app.extensions["procesador_gpu"], carpeta,
            current_app.config["MAX_PIXELES"], current_app.config["MAX_PIXELES_ENTRADA"])
        fin = time.perf_counter()
    except ErrorServicio as error:
        shutil.rmtree(carpeta, ignore_errors=True)
        if error.http >= 500:
            current_app.logger.error("solicitud %s: %s: %s", solicitud_id, error.codigo, error)
        return respuesta_error(error, solicitud_id)
    except HTTPException:
        # 413 (MAX_CONTENT_LENGTH) y similares los atiende el manejador de la aplicación.
        shutil.rmtree(carpeta, ignore_errors=True)
        raise
    except Exception as error:  # pylint: disable=broad-except
        shutil.rmtree(carpeta, ignore_errors=True)
        current_app.logger.exception("solicitud %s: error no controlado", solicitud_id)
        return jsonify(error=f"Error interno al procesar la solicitud: {error}",
                       codigo="error_interno", id_solicitud=solicitud_id), 500

    preparada, gpu = resultado.preparada, resultado.gpu
    tiempos = dict(resultado.tiempos_ms)
    tiempos["recepcion"] = (fin_recepcion - inicio) * 1000.0
    tiempos["servidor_total"] = (fin - inicio) * 1000.0
    archivo_url = lambda nombre: url_for("api.obtener_archivo", solicitud_id=solicitud_id,
                                         nombre=nombre)
    return jsonify({
        "id_solicitud": solicitud_id,
        "filtro": resultado.filtro,
        "mascara": resultado.mascara,
        "dimensiones": {"ancho": preparada.ancho, "alto": preparada.alto},
        "dimensiones_originales": {
            "ancho": preparada.ancho_original,
            "alto": preparada.alto_original,
        },
        "preparacion": {
            "aplicada": preparada.preparacion_aplicada,
            "recorte_central": preparada.recorte is not None,
            "redimensionada": preparada.redimensionada,
            "recorte": list(preparada.recorte) if preparada.recorte else None,
        },
        "gpu": {
            "hilos_por_bloque": gpu.hilos,
            "bloques": gpu.bloques,
            "memoria_reservada_mb": gpu.memoria_reservada_bytes / 2**20,
            "memoria_gpu_usada_mb": (None if gpu.memoria_gpu_usada_bytes is None
                                     else gpu.memoria_gpu_usada_bytes / 2**20),
            "memoria_gpu_total_mb": (None if gpu.memoria_gpu_total_bytes is None
                                     else gpu.memoria_gpu_total_bytes / 2**20),
            "transferencias": "síncronas desde memoria paginable (NumPy)",
        },
        "original_url": archivo_url("original.png"),
        "entrada_preparada_url": archivo_url("original.png"),
        "resultado_url": archivo_url("resultado.png"),
        "resultado_crudo_url": archivo_url("resultado.npy"),
        "tiempos_ms": tiempos,
    }), 201


@api.get("/resultados/<solicitud_id>/<nombre>")
def obtener_archivo(solicitud_id, nombre):
    permitidos = {"original.png", "resultado.png", "resultado.npy"}
    if not id_solicitud_valido(solicitud_id) or nombre not in permitidos:
        return jsonify(error="Archivo no disponible.", codigo="no_encontrado"), 404
    directorio = Path(current_app.config["DIRECTORIO_RESULTADOS"]) / solicitud_id
    if not (directorio / nombre).is_file():
        return jsonify(error="El resultado no existe o ya expiró.", codigo="no_encontrado"), 404
    return send_from_directory(directorio, nombre)


@api.get("/equipo")
def equipo():
    """Especificaciones del equipo que atiende las solicitudes (se muestran en la interfaz)."""
    respuesta = {"servidor": datos_equipo(), "gpu": None, "error_gpu": None,
                 "limites": {
                     "max_archivo_mb": current_app.config["MAX_CONTENT_LENGTH"] / 2**20,
                     "max_pixeles_procesados": current_app.config["MAX_PIXELES"],
                     "hilos_por_bloque": current_app.config["HILOS_POR_BLOQUE"],
                     "solicitudes_gpu_simultaneas": current_app.config["LIMITE_TRABAJOS_GPU"],
                 }}
    try:
        respuesta["gpu"] = current_app.extensions["procesador_gpu"].diagnosticar()
    except ErrorServicio as error:
        respuesta["error_gpu"] = str(error)
    return jsonify(respuesta)


@api.get("/salud")
def salud():
    """Diagnóstico real de la GPU: 200 si está utilizable, 503 con el motivo si no."""
    try:
        gpu = current_app.extensions["procesador_gpu"].diagnosticar()
    except ErrorServicio as error:
        return jsonify(estado="sin_gpu", error=str(error), codigo=error.codigo), error.http
    return jsonify(estado="listo", gpu=gpu)
