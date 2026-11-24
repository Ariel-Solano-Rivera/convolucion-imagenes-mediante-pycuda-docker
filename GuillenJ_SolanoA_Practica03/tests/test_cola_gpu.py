import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from webapp.errores import ColaGPULlena
from webapp.procesador_gpu import ResultadoGPU, ServicioGPU


def test_un_trabajo_ejecuta_otro_espera_y_el_tercero_se_rechaza(tmp_path):
    servicio = ServicioGPU(tmp_path, hilos=256, limite_trabajos=2)

    def lento(entrada, _mascara, _ancho, _alto, _k, _enviado):
        time.sleep(0.15)
        return ResultadoGPU(entrada, 0, 0, 0, 0, 0, None)

    servicio._procesar_en_hilo_cuda = lento
    datos = np.zeros(4, dtype=np.float32)
    mascara = np.ones(9, dtype=np.float32)
    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            primero = ejecutor.submit(servicio.procesar, datos, mascara, 2, 2, 3)
            segundo = ejecutor.submit(servicio.procesar, datos, mascara, 2, 2, 3)
            time.sleep(0.03)
            with pytest.raises(ColaGPULlena):
                servicio.procesar(datos, mascara, 2, 2, 3)
            primero.result()
            segundo.result()
    finally:
        servicio.cerrar()

