"""Python secuencial: bordes con ceros, tipos float32, limite de tiempo e imagenes."""
import numpy as np
import pytest

from src.python.comun.configuracion import Filtro
from src.python.convolucion import (
    TiempoExcedido, comparar, convolucion_cpu, crear_mascara, ejecutar_cpu)
from src.python.comun.imagenes import (
    a_bytes_visibles, leer_pgm, verificar_datos_p01)


def referencia_independiente(entrada, ancho, alto, mascara, k):
    """Referencia de prueba en float64 con relleno de ceros explicito (np.pad)."""
    radio = k // 2
    imagen = np.pad(entrada.reshape(alto, ancho).astype(np.float64), radio)
    m = mascara.reshape(k, k).astype(np.float64)
    salida = np.zeros((alto, ancho))
    for j in range(k):
        for i in range(k):
            salida += m[j, i] * imagen[j:j + alto, i:i + ancho]
    return salida.reshape(-1)


@pytest.mark.parametrize("filtro, k", [(Filtro.MEDIA, 3), (Filtro.NITIDEZ, 3),
                                       (Filtro.LAPLACIANO, 3), (Filtro.MEDIA, 9)])
def test_bordes_en_imagen_no_multiplo(filtro, k):
    """37x23 = 851 pixeles (no multiplo de 128/256/512); incluye esquinas y bordes."""
    ancho, alto = 37, 23
    entrada = np.random.default_rng(1).integers(0, 256, ancho * alto).astype(np.float32)
    salida = np.full(ancho * alto, np.nan, dtype=np.float32)
    mascara = crear_mascara(filtro, k)
    convolucion_cpu(entrada, salida, mascara, ancho, alto, k)
    assert not np.isnan(salida).any()  # cubre todos los pixeles
    esperado = referencia_independiente(entrada, ancho, alto, mascara, k)
    assert np.max(np.abs(salida - esperado)) < 1e-3


def test_acumulacion_en_float32():
    """El resultado conserva float32 y difiere de una acumulacion en float64 (prueba de tipo)."""
    entrada = np.full(9, np.float32(0.1), dtype=np.float32)
    salida = np.zeros(9, dtype=np.float32)
    convolucion_cpu(entrada, salida, crear_mascara(Filtro.MEDIA, 3), 3, 3, 3)
    assert salida.dtype == np.float32
    # Pixel central: nueve sumas de 0.1f * (1/9)f redondeadas a float32 una por una.
    suma = np.float32(0)
    for _ in range(9):
        suma = np.float32(suma + np.float32(np.float32(0.1) * (np.float32(1) / np.float32(9))))
    assert salida[4].view(np.uint32) == suma.view(np.uint32)


def test_limite_de_tiempo_aborta():
    ancho = alto = 300
    entrada = np.zeros(ancho * alto, dtype=np.float32)
    salida = np.zeros_like(entrada)
    with pytest.raises(TiempoExcedido) as error:
        ejecutar_cpu(entrada, salida, crear_mascara(Filtro.MEDIA, 9), ancho, alto, 9,
                     limite_segundos=0.05)
    assert error.value.transcurrido > 0.05
    assert 0 < error.value.filas_procesadas < alto


def test_ejecutar_cpu_devuelve_ms():
    entrada = np.ones(100, dtype=np.float32)
    salida = np.zeros_like(entrada)
    mascara = crear_mascara(Filtro.NITIDEZ, 3)
    t = ejecutar_cpu(entrada, salida, mascara, 10, 10, 3)
    assert t > 0 and salida[55] == 1.0  # interior: 5 - 4 = 1


def test_comparar():
    a = np.array([1, 2, 3], dtype=np.float32)
    b = np.array([1, 2.5, 2], dtype=np.float32)
    assert comparar(a, b) == (1.0, 0.5)


def test_tratamiento_visible_como_p01():
    datos = np.array([-70, 10.7, 300, 63.9], dtype=np.float32)
    assert a_bytes_visibles(datos, laplaciano=False).tolist() == [0, 10, 255, 63]
    assert a_bytes_visibles(datos, laplaciano=True).tolist() == [255, 42, 255, 255]


def test_datos_p01_verificados_y_float32():
    assert verificar_datos_p01() == 4
    from src.python.comun.configuracion import NO_MULTIPLO
    datos, ancho, alto = leer_pgm(NO_MULTIPLO)
    assert (ancho, alto) == (1013, 757)
    assert datos.dtype == np.float32 and datos.flags.c_contiguous and datos.ndim == 1
