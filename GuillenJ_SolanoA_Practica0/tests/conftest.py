"""Fixtures compartidas: un solo contexto CUDA para todas las pruebas de GPU."""
import pytest


@pytest.fixture(scope="session")
def cuda_listo():
    from src.pycuda.contexto_cuda import cerrar_cuda, inicializar_cuda
    entorno = inicializar_cuda()
    yield entorno
    cerrar_cuda()
