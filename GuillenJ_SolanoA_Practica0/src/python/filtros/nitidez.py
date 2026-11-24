"""Mascara fija 3x3 que resalta detalles."""
import numpy as np


def crear_mascara_nitidez():
    return np.array([0, -1, 0,
                     -1, 5, -1,
                     0, -1, 0], dtype=np.float32)
