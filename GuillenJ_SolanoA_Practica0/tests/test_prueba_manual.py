"""Prueba manual 5x5: los 12 casos de pruebaManual() de P01."""
import re

import numpy as np
import pytest

from src.python.comun.configuracion import P01
from src.python.convolucion import convolucion_cpu
from src.python.comun.experimentos import (
    CASOS_MANUALES, IMAGEN_MANUAL, MASCARA_FIGURA1, TOLERANCIA_MANUAL,
    mascaras_manuales)


def bloque_de_p01(nombre):
    """Texto entre llaves de una declaracion de experimentos.cu de P01."""
    texto = (P01 / "src" / "experimentos.cu").read_text(encoding="utf-8")
    return re.search(nombre + r"\[\]\s*=\s*\{(.*?)\};", texto, re.S).group(1)


def test_datos_manuales_iguales_a_p01():
    """La matriz, la mascara de la figura 1 y los 12 casos coinciden con experimentos.cu."""
    imagen = [float(v) for v in bloque_de_p01("float imagen").split(",")]
    figura = [float(v) for v in bloque_de_p01("float figura").split(",")]
    assert np.array_equal(IMAGEN_MANUAL, np.array(imagen, dtype=np.float32))
    assert np.array_equal(MASCARA_FIGURA1, np.array(figura, dtype=np.float32))

    casos = re.findall(r"\{(\d+),\s*(\d+),\s*(\d+),\s*([^}]+)\}", bloque_de_p01("Caso casos"))
    assert len(casos) == 12 == len(CASOS_MANUALES)
    for (m, fila, columna, esperado), propio in zip(casos, CASOS_MANUALES):
        if "/" in esperado:  # p. ej. 155.f / 9 -> division en float32
            a, b = esperado.replace("f", "").split("/")
            valor = np.float32(float(a)) / np.float32(float(b))
        else:
            valor = np.float32(float(esperado))
        assert (int(m), int(fila), int(columna), valor) == propio


@pytest.mark.parametrize("caso", CASOS_MANUALES,
                         ids=[f"m{c[0]}_f{c[1]}_c{c[2]}" for c in CASOS_MANUALES])
def test_caso_manual_cpu(caso):
    m, fila, columna, esperado = caso
    salida = np.zeros(25, dtype=np.float32)
    convolucion_cpu(IMAGEN_MANUAL, salida, mascaras_manuales()[m], 5, 5, 3)
    assert abs(float(salida[fila * 5 + columna]) - float(esperado)) <= TOLERANCIA_MANUAL
