"""Lectura de imagenes PGM y escritura de resultados visibles en PNG."""
import hashlib
import json

import numpy as np
from PIL import Image

from .configuracion import HASHES_P01, RAIZ_REPO


def leer_pgm(ruta):
    """Devuelve (datos, ancho, alto); datos es float32, 1-D y contiguo, como leerPGM de P01."""
    with Image.open(ruta) as imagen:
        gris = imagen.convert("L")
        ancho, alto = gris.size
        bytes_ = np.asarray(gris, dtype=np.uint8)
    datos = np.ascontiguousarray(bytes_.reshape(-1), dtype=np.float32)
    return datos, ancho, alto


def a_bytes_visibles(datos, laplaciano):
    """Mismo tratamiento que guardarPGM de P01: |x|*4 en laplaciano y recorte a 0-255."""
    valores = datos.astype(np.float32, copy=False)
    if laplaciano:
        valores = np.abs(valores) * np.float32(4)
    # El cast de C a unsigned char trunca; astype(uint8) tras el recorte tambien.
    return np.clip(valores, np.float32(0), np.float32(255)).astype(np.uint8)


def guardar_png(ruta, datos, ancho, alto, laplaciano):
    """Guarda la salida como PNG (no PGM de 16 MB). El error se calcula antes de esto."""
    bytes_ = a_bytes_visibles(datos, laplaciano).reshape(alto, ancho)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bytes_).save(ruta)  # uint8 2-D -> modo "L"


def sha256(ruta):
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def verificar_datos_p01():
    """Comprueba que los .pgm de P01 son exactamente los registrados en hashes_p01.json."""
    if not HASHES_P01.exists():
        raise FileNotFoundError("Falta datos/hashes_p01.json: ejecute "
                                "python -m scripts.preparar_imagenes")
    registro = json.loads(HASHES_P01.read_text(encoding="utf-8"))
    for relativa, esperado in registro["sha256"].items():
        ruta = RAIZ_REPO / relativa
        if sha256(ruta) != esperado:
            raise ValueError(f"{relativa} no coincide con el SHA-256 registrado de P01")
    return len(registro["sha256"])
