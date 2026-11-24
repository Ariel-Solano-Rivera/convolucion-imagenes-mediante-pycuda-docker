"""Mascara fija 3x3 para detectar bordes."""
import numpy as np


def crear_mascara_laplaciano():
    return np.array([0, 1, 0,
                     1, -4, 1,
                     0, 1, 0], dtype=np.float32)
