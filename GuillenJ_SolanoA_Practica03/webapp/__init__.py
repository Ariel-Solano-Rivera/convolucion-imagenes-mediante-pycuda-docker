"""Aplicación web de la práctica 03."""
from pathlib import Path

from flask import Flask, jsonify

from .api import api
from .configuracion import Configuracion
from .procesador_gpu import ServicioGPU


def crear_aplicacion(configuracion=None, procesador=None):
    """Construye la aplicación sin inicializar CUDA hasta la primera solicitud."""
    config = configuracion or Configuracion.desde_entorno()
    valores = config.como_dict() if isinstance(config, Configuracion) else config
    aplicacion = Flask(__name__, static_folder="static", static_url_path="")
    aplicacion.config.from_mapping(valores)
    Path(aplicacion.config["DIRECTORIO_RESULTADOS"]).mkdir(parents=True, exist_ok=True)
    aplicacion.extensions["procesador_gpu"] = procesador or ServicioGPU(
        practica02=aplicacion.config["PRACTICA02_ROOT"],
        hilos=aplicacion.config["HILOS_POR_BLOQUE"],
        limite_trabajos=aplicacion.config["LIMITE_TRABAJOS_GPU"],
    )
    aplicacion.register_blueprint(api)

    @aplicacion.get("/")
    def inicio():
        return aplicacion.send_static_file("index.html")

    @aplicacion.errorhandler(413)
    def archivo_muy_grande(_error):
        limite = aplicacion.config["MAX_CONTENT_LENGTH"] / 2**20
        return jsonify(error=f"El archivo supera el límite configurado de {limite:.0f} MiB.",
                       codigo="archivo_demasiado_grande"), 413

    return aplicacion

