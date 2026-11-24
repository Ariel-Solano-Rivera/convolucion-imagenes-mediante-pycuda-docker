"""Decodificación segura y escritura de imágenes visibles."""
from dataclasses import dataclass
from io import BytesIO
from math import isqrt
import warnings

import numpy as np
from PIL import Image, UnidentifiedImageError

from .errores import EntradaInvalida

FORMATOS_PERMITIDOS = {"PNG", "JPEG", "BMP", "PPM"}


@dataclass(frozen=True)
class ImagenPreparada:
    datos: np.ndarray
    ancho: int
    alto: int
    visible: Image.Image
    ancho_original: int
    alto_original: int
    recorte: tuple[int, int, int, int] | None
    redimensionada: bool

    @property
    def preparacion_aplicada(self):
        return self.recorte is not None or self.redimensionada


def _abrir_validada(contenido, max_pixeles_entrada):
    if not contenido:
        raise EntradaInvalida("Debe adjuntar una imagen no vacía.")
    try:
        # Pillow advierte a partir de unos 89 MP. El servicio aplica su propio
        # límite, más estricto que el umbral de error de Pillow, antes de convertir.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contenido)) as prueba:
                prueba.verify()
            imagen = Image.open(BytesIO(contenido))
        if imagen.format not in FORMATOS_PERMITIDOS:
            imagen.close()
            raise EntradaInvalida("Formato no admitido. Use PNG, JPG, BMP, PGM o PPM.")
        ancho, alto = imagen.size
        pixeles = ancho * alto
        if pixeles > max_pixeles_entrada:
            imagen.close()
            raise EntradaInvalida(
                f"La imagen tiene {pixeles} píxeles y supera el límite de entrada "
                f"de {max_pixeles_entrada}.")
        return imagen
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise EntradaInvalida("El archivo no es una imagen válida o no puede decodificarse.") from error


def leer_imagen(archivo, max_pixeles):
    """Valida el contenido real y entrega píxeles contiguos float32 en gris."""
    contenido = archivo.read()
    imagen = _abrir_validada(contenido, max_pixeles)
    try:
        ancho, alto = imagen.size
        gris = imagen.convert("L")
        original = gris.copy()
        datos = np.ascontiguousarray(np.asarray(gris, dtype=np.uint8).reshape(-1), dtype=np.float32)
    finally:
        imagen.close()
    return datos, ancho, alto, original


def preparar_imagen_subida(archivo, max_pixeles_procesamiento, max_pixeles_entrada):
    """Reproduce la preparación previa: recorte central y LANCZOS hasta el máximo."""
    if max_pixeles_procesamiento < 1 or max_pixeles_entrada < max_pixeles_procesamiento:
        raise ValueError("Los límites de píxeles configurados no son válidos.")
    contenido = archivo.read()
    imagen = _abrir_validada(contenido, max_pixeles_entrada)
    try:
        ancho_original, alto_original = imagen.size
        gris = imagen.convert("L")
    finally:
        imagen.close()

    recorte = None
    redimensionada = False
    if ancho_original * alto_original > max_pixeles_procesamiento:
        lado = min(ancho_original, alto_original)
        izquierda = (ancho_original - lado) // 2
        superior = (alto_original - lado) // 2
        recorte = (izquierda, superior, izquierda + lado, superior + lado)
        gris = gris.crop(recorte)
        lado_maximo = isqrt(max_pixeles_procesamiento)
        if lado > lado_maximo:
            gris = gris.resize((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
            redimensionada = True

    ancho, alto = gris.size
    if ancho * alto > max_pixeles_procesamiento:
        raise EntradaInvalida(
            f"No fue posible preparar la imagen dentro del límite de "
            f"{max_pixeles_procesamiento} píxeles.")
    visible = gris.copy()
    datos = np.ascontiguousarray(
        np.asarray(gris, dtype=np.uint8).reshape(-1), dtype=np.float32)
    return ImagenPreparada(
        datos=datos,
        ancho=ancho,
        alto=alto,
        visible=visible,
        ancho_original=ancho_original,
        alto_original=alto_original,
        recorte=recorte,
        redimensionada=redimensionada,
    )


def guardar_resultado(ruta, datos, ancho, alto, laplaciano=False):
    """Aplica solo la transformación de visualización usada en práctica 02."""
    visibles = datos.astype(np.float32, copy=False)
    if laplaciano:
        visibles = np.abs(visibles) * np.float32(4)
    bytes_ = np.clip(visibles, np.float32(0), np.float32(255)).astype(np.uint8)
    Image.fromarray(bytes_.reshape(alto, ancho), mode="L").save(ruta, format="PNG")
