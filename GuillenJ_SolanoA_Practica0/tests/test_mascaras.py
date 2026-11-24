"""Las mascaras de P02 son float32 e identicas bit a bit a las de P01."""
import re
import struct

import numpy as np
import pytest

from src.python.comun.configuracion import P01, Filtro
from src.python.convolucion import crear_mascara


def float32_de_c(valor):
    """Redondea un double a float como lo hace C al asignar a float."""
    return struct.unpack("<f", struct.pack("<f", valor))[0]


def coeficientes_de_p01(archivo):
    """Lee los coeficientes de 'return {...};' en las fuentes de P01 (solo lectura)."""
    texto = (P01 / "src" / "filtros" / archivo).read_text(encoding="utf-8")
    cuerpo = re.search(r"return\s*\{([^}]*)\}", texto).group(1)
    return np.array([float(v) for v in cuerpo.split(",")], dtype=np.float32)


@pytest.mark.parametrize("k", [3, 9, 21])
def test_media_float32_bit_a_bit(k):
    mascara = crear_mascara(Filtro.MEDIA, k)
    assert mascara.dtype == np.float32 and mascara.flags.c_contiguous
    assert mascara.size == k * k
    # 1.0f / (k*k): la division en double redondeada a float es la division correcta en float.
    esperado = np.float32(float32_de_c(1.0 / (k * k)))
    assert np.all(mascara.view(np.uint32) == esperado.view(np.uint32))


@pytest.mark.parametrize("filtro, archivo", [(Filtro.NITIDEZ, "nitidez.cpp"),
                                             (Filtro.LAPLACIANO, "laplaciano.cpp")])
def test_mascaras_fijas_iguales_a_p01(filtro, archivo):
    mascara = crear_mascara(filtro, 3)
    assert mascara.dtype == np.float32 and mascara.flags.c_contiguous
    assert np.array_equal(mascara.view(np.uint32), coeficientes_de_p01(archivo).view(np.uint32))


@pytest.mark.parametrize("filtro, k, archivo", [
    (Filtro.MEDIA, 3, "mascara_media3.bin"), (Filtro.MEDIA, 9, "mascara_media9.bin"),
    (Filtro.MEDIA, 21, "mascara_media21.bin"), (Filtro.NITIDEZ, 3, "mascara_nitidez3.bin"),
    (Filtro.LAPLACIANO, 3, "mascara_laplaciano3.bin")])
def test_mascaras_bit_a_bit_contra_cpp(filtro, k, archivo):
    """Compara con crearMascara de P01 exportada por referencia_cpp (generar_referencias)."""
    from src.python.comun.configuracion import REFERENCIAS
    ruta = REFERENCIAS / archivo
    if not ruta.exists():
        pytest.skip("Faltan las referencias: python -m scripts.generar_referencias")
    cpp = np.fromfile(ruta, dtype="<u4")
    assert np.array_equal(crear_mascara(filtro, k).view(np.uint32), cpp)


def test_media_igual_a_fuente_p01():
    """La formula de media.cpp de P01 sigue siendo 1.0f / (tamano * tamano)."""
    texto = (P01 / "src" / "filtros" / "media.cpp").read_text(encoding="utf-8")
    assert "1.0f / (tamano * tamano)" in texto
