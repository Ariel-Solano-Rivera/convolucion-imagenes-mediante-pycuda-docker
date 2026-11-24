"""Mascara de media de tamano variable."""
import numpy as np


def crear_mascara_media(tamano):
    # Igual que P01: 1.0f / (tamano * tamano), division hecha en float32.
    valor = np.float32(1.0) / np.float32(tamano * tamano)
    return np.full(tamano * tamano, valor, dtype=np.float32)
