import numpy as np
import pytest

from webapp.errores import EntradaInvalida
from webapp.filtros import crear_mascara, validar_filtro_y_mascara


def test_mascaras_son_float32_y_contiguas():
    for filtro, k in (("media", 3), ("media", 9), ("media", 21),
                      ("nitidez", 3), ("laplaciano", 3)):
        mascara = crear_mascara(filtro, k)
        assert mascara.dtype == np.float32
        assert mascara.flags.c_contiguous
        assert mascara.size == k * k


def test_media_usa_division_float32():
    mascara = crear_mascara("media", 21)
    esperado = np.float32(1.0) / np.float32(21 * 21)
    assert np.array_equal(mascara, np.full(21 * 21, esperado, dtype=np.float32))


@pytest.mark.parametrize("filtro,k", [("media", 5), ("nitidez", 9), ("otro", 3)])
def test_parametros_invalidos(filtro, k):
    with pytest.raises(EntradaInvalida):
        validar_filtro_y_mascara(filtro, k)

