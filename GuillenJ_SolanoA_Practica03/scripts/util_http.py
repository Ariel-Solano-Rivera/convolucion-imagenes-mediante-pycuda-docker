"""Cliente HTTP sin dependencias adicionales para el servicio de convolución."""
import json
import mimetypes
import time
import uuid
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RespuestaHTTP:
    estado_http: int
    cuerpo: dict
    tiempo_cliente_ms: float


def _multipart(campos, nombre_archivo, contenido, tipo_contenido):
    frontera = f"----practica03-{uuid.uuid4().hex}"
    partes = []
    for nombre, valor in campos.items():
        partes.extend([
            f"--{frontera}\r\n".encode(),
            f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode(),
            str(valor).encode("utf-8"), b"\r\n",
        ])
    partes.extend([
        f"--{frontera}\r\n".encode(),
        f'Content-Disposition: form-data; name="imagen"; filename="{nombre_archivo}"\r\n'.encode(),
        f"Content-Type: {tipo_contenido}\r\n\r\n".encode(),
        contenido, b"\r\n", f"--{frontera}--\r\n".encode(),
    ])
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


def enviar_bytes(url_base, nombre, contenido, filtro, mascara, timeout=600):
    tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
    cuerpo, cabecera = _multipart({"filtro": filtro, "mascara": mascara},
                                  nombre, contenido, tipo)
    solicitud = Request(urljoin(url_base.rstrip("/") + "/", "api/convoluciones"),
                        data=cuerpo, method="POST",
                        headers={"Content-Type": cabecera, "Accept": "application/json"})
    inicio = time.perf_counter()
    try:
        with urlopen(solicitud, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
            estado = respuesta.status
        # La guía define el tiempo del cliente hasta recibir la imagen final,
        # no solamente hasta obtener el JSON que contiene su URL.
        if estado == 201 and datos.get("resultado_url"):
            with urlopen(urljoin(url_base.rstrip("/") + "/",
                                 datos["resultado_url"].lstrip("/")),
                         timeout=timeout) as resultado:
                resultado.read()
    except HTTPError as error:
        estado = error.code
        try:
            datos = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            datos = {"error": str(error)}
    except URLError as error:
        return RespuestaHTTP(0, {"error": f"No se pudo conectar: {error.reason}"},
                             (time.perf_counter() - inicio) * 1000.0)
    return RespuestaHTTP(estado, datos, (time.perf_counter() - inicio) * 1000.0)


def enviar_imagen(url_base, ruta, filtro, mascara, timeout=600):
    ruta = Path(ruta)
    return enviar_bytes(url_base, ruta.name, ruta.read_bytes(), filtro, mascara, timeout)


def descargar(url_base, ruta_relativa, timeout=600):
    with urlopen(urljoin(url_base.rstrip("/") + "/", ruta_relativa.lstrip("/")),
                 timeout=timeout) as respuesta:
        return respuesta.read()


def enviar_longitud_excesiva(url_base, longitud_declarada, timeout=30):
    """Provoca 413 sin transferir decenas de MiB innecesariamente."""
    partes = urlparse(url_base)
    conexion_cls = HTTPSConnection if partes.scheme == "https" else HTTPConnection
    conexion = conexion_cls(partes.hostname, partes.port, timeout=timeout)
    inicio = time.perf_counter()
    try:
        conexion.putrequest("POST", "/api/convoluciones")
        conexion.putheader("Content-Type", "multipart/form-data; boundary=limite")
        conexion.putheader("Content-Length", str(longitud_declarada))
        conexion.endheaders()
        respuesta = conexion.getresponse()
        contenido = respuesta.read()
        try:
            cuerpo = json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            cuerpo = {"error": contenido.decode("utf-8", errors="replace")}
        return RespuestaHTTP(respuesta.status, cuerpo,
                             (time.perf_counter() - inicio) * 1000.0)
    finally:
        conexion.close()

