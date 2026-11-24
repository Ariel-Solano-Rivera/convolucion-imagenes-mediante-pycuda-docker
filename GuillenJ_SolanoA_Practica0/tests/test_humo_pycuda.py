"""Prueba de humo: PyCUDA compila con SourceModule y ejecuta un kernel trivial."""
import numpy as np
import pytest

from src.python.comun.configuracion import ARQUITECTURA, OPCIONES_NVCC

pytestmark = pytest.mark.gpu

CODIGO = """
__global__ void duplicar(float* datos, int n) {
    int id = blockIdx.x * blockDim.x + threadIdx.x;
    if (id >= n) return;
    datos[id] = 2.0f * datos[id];
}
"""


def test_kernel_trivial():
    import pycuda.driver as cuda
    from pycuda.compiler import SourceModule

    cuda.init()
    contexto = cuda.Device(0).make_context()  # contexto manual, sin autoinit
    try:
        modulo = SourceModule(CODIGO, options=OPCIONES_NVCC, arch=ARQUITECTURA)
        duplicar = modulo.get_function("duplicar")

        n, hilos = 1000, 256  # n no es multiplo de 256
        datos = np.arange(n, dtype=np.float32)
        d_datos = cuda.mem_alloc(datos.nbytes)
        cuda.memcpy_htod(d_datos, datos)
        bloques = (n + hilos - 1) // hilos
        duplicar(d_datos, np.int32(n), block=(hilos, 1, 1), grid=(bloques, 1))
        salida = np.empty_like(datos)
        cuda.memcpy_dtoh(salida, d_datos)
        d_datos.free()
    finally:
        contexto.pop()

    assert np.array_equal(salida, 2 * datos)
