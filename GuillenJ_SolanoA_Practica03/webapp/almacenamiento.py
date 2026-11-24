"""Aislamiento y limpieza diferida de los archivos generados por solicitudes."""
import shutil
import time
import uuid
from pathlib import Path


def nuevo_id_solicitud():
    return str(uuid.uuid4())


def id_solicitud_valido(valor):
    try:
        return str(uuid.UUID(valor)) == valor
    except (ValueError, TypeError, AttributeError):
        return False


def limpiar_resultados_expirados(raiz, retencion_segundos):
    """Elimina solo directorios UUID vencidos; nunca toca rutas externas."""
    limite = time.time() - retencion_segundos
    for ruta in Path(raiz).iterdir():
        if not ruta.is_dir() or not id_solicitud_valido(ruta.name):
            continue
        if ruta.stat().st_mtime < limite:
            shutil.rmtree(ruta)
