"""PyCUDA: kernel de P01, prueba manual, no multiplo con 128/256/512 hilos y tipos."""
import re

import numpy as np
import pytest

from src.python.comun.configuracion import (
    KERNEL, NO_MULTIPLO, P01, TOLERANCIA, Filtro)
from src.python.convolucion import convolucion_cpu, crear_mascara
from src.pycuda.convolucion import (
    calcular_gpu, ejecutar_gpu, escalares_kernel, reservar_memoria_gpu,
    liberar_memoria_gpu)
from src.python.comun.experimentos import (
    CASOS_MANUALES, IMAGEN_MANUAL, TOLERANCIA_MANUAL, mascaras_manuales)
from src.python.comun.imagenes import leer_pgm

pytestmark = pytest.mark.gpu
HILOS = (128, 256, 512)
CONFIGURACIONES_NO_MULTIPLO = [(Filtro.MEDIA, 3), (Filtro.NITIDEZ, 3),
                               (Filtro.LAPLACIANO, 3), (Filtro.MEDIA, 9)]  # las de P01


def cuerpo_kernel(texto):
    """Desde '__global__ void convolucionGPU' hasta su llave de cierre, sin espacios."""
    inicio = texto.index("__global__ void convolucionGPU")
    profundidad, fin = 0, None
    for pos in range(texto.index("{", inicio), len(texto)):
        profundidad += {"{": 1, "}": -1}.get(texto[pos], 0)
        if profundidad == 0:
            fin = pos + 1
            break
    return re.sub(r"\s+", "", texto[inicio:fin])


def test_kernel_identico_a_p01():
    propio = KERNEL.read_text(encoding="utf-8")
    original = (P01 / "src" / "filtros.cu").read_text(encoding="utf-8")
    assert cuerpo_kernel(propio) == cuerpo_kernel(original)


def test_inicializacion_registrada(cuda_listo):
    etapas = [fila["etapa"] for fila in cuda_listo.tiempos]
    assert etapas == ["contexto", "compilacion_sin_cache", "carga_con_cache", "get_function"]


@pytest.mark.parametrize("caso", CASOS_MANUALES,
                         ids=[f"m{c[0]}_f{c[1]}_c{c[2]}" for c in CASOS_MANUALES])
def test_caso_manual_gpu(cuda_listo, caso):
    m, fila, columna, esperado = caso
    salida = calcular_gpu(IMAGEN_MANUAL, mascaras_manuales()[m], 5, 5, 3, 256)
    assert abs(float(salida[fila * 5 + columna]) - float(esperado)) <= TOLERANCIA_MANUAL


@pytest.fixture(scope="module")
def no_multiplo():
    return leer_pgm(NO_MULTIPLO)


def referencia_float64(entrada, ancho, alto, mascara, k):
    """Referencia de prueba en float64 con relleno de ceros (solo para tests)."""
    radio = k // 2
    imagen = np.pad(entrada.reshape(alto, ancho).astype(np.float64), radio)
    m = mascara.reshape(k, k).astype(np.float64)
    salida = np.zeros((alto, ancho))
    for j in range(k):
        for i in range(k):
            salida += m[j, i] * imagen[j:j + alto, i:i + ancho]
    return salida.reshape(-1)


@pytest.mark.parametrize("hilos", HILOS)
@pytest.mark.parametrize("filtro, k", CONFIGURACIONES_NO_MULTIPLO)
def test_no_multiplo(cuda_listo, no_multiplo, hilos, filtro, k):
    entrada, ancho, alto = no_multiplo
    n = ancho * alto
    bloques = (n + hilos - 1) // hilos
    assert n % hilos != 0 and bloques * hilos > n  # el ultimo bloque esta incompleto

    mascara = crear_mascara(filtro, k)
    centinela = np.full(n, np.nan, dtype=np.float32)
    salida = calcular_gpu(entrada, mascara, ancho, alto, k, hilos, salida_inicial=centinela)

    assert not np.isnan(salida).any()  # todos los pixeles fueron escritos
    esperado = referencia_float64(entrada, ancho, alto, mascara, k)
    assert np.max(np.abs(salida - esperado)) <= TOLERANCIA
    # Bordes y ultimo bloque incompleto, explicitamente.
    imagen, ref = salida.reshape(alto, ancho), esperado.reshape(alto, ancho)
    for borde, borde_ref in ((imagen[0], ref[0]), (imagen[-1], ref[-1]),
                             (imagen[:, 0], ref[:, 0]), (imagen[:, -1], ref[:, -1]),
                             (salida[(bloques - 1) * hilos:], esperado[(bloques - 1) * hilos:])):
        assert np.max(np.abs(borde - borde_ref)) <= TOLERANCIA


@pytest.mark.parametrize("hilos", HILOS)
@pytest.mark.parametrize("filtro, k", CONFIGURACIONES_NO_MULTIPLO)
def test_gpu_igual_a_python_secuencial_pequena(cuda_listo, hilos, filtro, k):
    """37x23 (851 pixeles): PyCUDA frente a Python secuencial, pixel por pixel."""
    ancho, alto = 37, 23
    entrada = np.random.default_rng(2).integers(0, 256, ancho * alto).astype(np.float32)
    mascara = crear_mascara(filtro, k)
    cpu = np.zeros(ancho * alto, dtype=np.float32)
    convolucion_cpu(entrada, cpu, mascara, ancho, alto, k)
    gpu = calcular_gpu(entrada, mascara, ancho, alto, k, hilos)
    if filtro == Filtro.MEDIA:
        assert np.max(np.abs(cpu - gpu)) <= TOLERANCIA
    else:  # coeficientes enteros: operaciones exactas en float32
        assert np.array_equal(cpu, gpu)


def test_tipos_transferidos(cuda_listo):
    ancho = alto = 8
    k = 3
    d = reservar_memoria_gpu(ancho * alto, k)
    try:
        bien = np.zeros(ancho * alto, dtype=np.float32)
        mascara = crear_mascara(Filtro.MEDIA, k)
        ejecutar_gpu(bien, np.empty_like(bien), mascara, *d, ancho, alto, k, 256)
        with pytest.raises(TypeError, match="float32"):
            ejecutar_gpu(bien.astype(np.float64), np.empty_like(bien), mascara, *d,
                         ancho, alto, k, 256)
        no_contiguo = np.zeros(2 * ancho * alto, dtype=np.float32)[::2]
        with pytest.raises(TypeError, match="contiguo"):
            ejecutar_gpu(no_contiguo, np.empty_like(bien), mascara, *d, ancho, alto, k, 256)
    finally:
        liberar_memoria_gpu(*d)
    assert all(type(v) is np.int32 for v in escalares_kernel(ancho, alto, k))
