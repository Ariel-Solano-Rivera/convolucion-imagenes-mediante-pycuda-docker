"""Errores controlados (sin GPU, memoria, kernel), pipeline compartido y referencia CPU."""
from io import BytesIO
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from scripts.experimentos import COLUMNAS, fila_respuesta
from scripts.validar_servicio import referencia_cpu
from webapp.errores import (ErrorProcesamientoGPU, GPUNoDisponible, MemoriaGPUInsuficiente)
from webapp.filtros import crear_mascara
from webapp.procesador_gpu import ServicioGPU
from webapp.procesamiento import procesar_imagen
from tests.test_api import ProcesadorFalso, crear_cliente, imagen_png


class ProcesadorQueFalla:
    def __init__(self, error):
        self.error = error

    def procesar(self, *_args):
        raise self.error

    def diagnosticar(self):
        raise self.error


def publicar(cliente):
    return cliente.post("/api/convoluciones", data={
        "imagen": (imagen_png(), "entrada.png"), "filtro": "media", "mascara": "3"})


@pytest.mark.parametrize("error, http, codigo", [
    (GPUNoDisponible("sin GPU"), 503, "gpu_no_disponible"),
    (MemoriaGPUInsuficiente("sin memoria"), 503, "memoria_gpu_insuficiente"),
    (ErrorProcesamientoGPU("kernel"), 500, "error_procesamiento_gpu"),
])
def test_errores_gpu_tienen_codigo_y_no_dejan_archivos(tmp_path, error, http, codigo):
    cliente = crear_cliente(tmp_path, procesador=ProcesadorQueFalla(error))
    respuesta = publicar(cliente)
    cuerpo = respuesta.get_json()
    assert respuesta.status_code == http
    assert cuerpo["codigo"] == codigo
    assert "resultado_url" not in cuerpo  # no hay respaldo silencioso en CPU
    assert not any((tmp_path / "resultados").iterdir())


def test_salud_informa_ausencia_de_gpu(tmp_path):
    cliente = crear_cliente(tmp_path, procesador=ProcesadorQueFalla(
        GPUNoDisponible("No hay ninguna GPU NVIDIA visible para el proceso.")))
    respuesta = cliente.get("/api/salud")
    assert respuesta.status_code == 503
    assert respuesta.get_json()["codigo"] == "gpu_no_disponible"
    assert "GPU" in respuesta.get_json()["error"]


def test_archivo_grande_tiene_codigo(tmp_path):
    respuesta = crear_cliente(tmp_path).post("/api/convoluciones", data={
        "imagen": (BytesIO(b"x" * (1024 * 1024)), "grande.bin"),
        "filtro": "media", "mascara": "3"})
    assert respuesta.status_code == 413
    assert respuesta.get_json()["codigo"] == "archivo_demasiado_grande"


def test_respuesta_incluye_fases_y_memoria(tmp_path):
    cuerpo = publicar(crear_cliente(tmp_path)).get_json()
    for clave in ("recepcion", "decodificacion_y_preparacion", "espera_gpu",
                  "reserva_liberacion", "cpu_a_gpu", "kernel", "gpu_a_cpu", "gpu_total",
                  "codificacion_y_escritura", "procesamiento_total", "servidor_total"):
        assert clave in cuerpo["tiempos_ms"]
    assert cuerpo["gpu"]["bloques"] == 1
    assert cuerpo["gpu"]["memoria_reservada_mb"] > 0


def test_pipeline_directo_y_servicio_dan_el_mismo_resultado(tmp_path):
    contenido = imagen_png().getvalue()
    carpeta = tmp_path / "directo"
    carpeta.mkdir()
    directo = procesar_imagen(contenido, "media", "3", ProcesadorFalso(), carpeta, 100, 1000)
    cliente = crear_cliente(tmp_path)
    cuerpo = publicar(cliente).get_json()
    servicio = np.load(BytesIO(cliente.get(cuerpo["resultado_crudo_url"]).data))
    assert np.array_equal(np.load(carpeta / "resultado.npy"), servicio)
    assert np.array_equal(directo.gpu.datos, servicio)
    assert {"original.png", "resultado.png", "resultado.npy"} <= {
        ruta.name for ruta in carpeta.iterdir()}


def test_fila_csv_registra_todas_las_fases(tmp_path):
    ruta = tmp_path / "e.png"
    Image.fromarray(np.zeros((3, 5), dtype=np.uint8)).save(ruta)
    respuesta = SimpleNamespace(estado_http=201, tiempo_cliente_ms=9.0, cuerpo={
        "id_solicitud": "x", "gpu": {"memoria_reservada_mb": 1.0, "memoria_gpu_usada_mb": 10.0},
        "tiempos_ms": {"recepcion": 1, "decodificacion_y_preparacion": 2, "espera_gpu": 0,
                       "reserva_liberacion": 0.1, "cpu_a_gpu": 1, "kernel": 2,
                       "gpu_a_cpu": 1, "gpu_total": 4, "codificacion_y_escritura": 3,
                       "servidor_total": 8, "inicio_frio": None}})
    fila = fila_respuesta("resolucion", "servicio_contenedor", "local", "media", 9, ruta, 1,
                          respuesta)
    assert set(fila) == set(COLUMNAS)
    for columna in ("t_recepcion_ms", "t_decodificacion_ms", "t_codificacion_ms",
                    "t_reserva_liberacion_ms", "memoria_reservada_mb", "t_cliente_ms"):
        assert fila[columna] != ""
    assert fila["bloques"] == 1 and fila["estado"] == "completada"


def _servicio_con_funciones(tmp_path, reservar, ejecutar):
    servicio = ServicioGPU(tmp_path, hilos=256, limite_trabajos=1)
    cerrados = []
    servicio._practica02 = (lambda: None, lambda: cerrados.append(True), ejecutar,
                            lambda *_p: None, reservar)
    servicio._inicio_frio_registrado = True
    return servicio, cerrados


def test_falta_de_memoria_gpu_se_informa_sin_reiniciar_contexto(tmp_path):
    def reservar(_n, _k):
        raise RuntimeError("cuMemAlloc failed: out of memory")

    servicio, cerrados = _servicio_con_funciones(tmp_path, reservar, None)
    datos = np.zeros(4, dtype=np.float32)
    try:
        with pytest.raises(MemoriaGPUInsuficiente):
            servicio.procesar(datos, crear_mascara("media", 3), 2, 2, 3)
        assert not cerrados
    finally:
        servicio._inicio_frio_registrado = False
        servicio.cerrar()


def test_error_del_kernel_reinicia_el_contexto(tmp_path):
    def ejecutar(*_args):
        raise RuntimeError("cuLaunchKernel failed: unspecified launch failure")

    servicio, cerrados = _servicio_con_funciones(
        tmp_path, lambda _n, _k: (object(), object(), object()), ejecutar)
    datos = np.zeros(4, dtype=np.float32)
    try:
        with pytest.raises(ErrorProcesamientoGPU):
            servicio.procesar(datos, crear_mascara("media", 3), 2, 2, 3)
        assert cerrados and servicio._inicio_frio_registrado is False
    finally:
        servicio.cerrar()


def _convolucion_ingenua(imagen, mascara, k):
    alto, ancho = imagen.shape
    radio = k // 2
    salida = np.zeros(alto * ancho, dtype=np.float32)
    for y in range(alto):
        for x in range(ancho):
            suma = np.float32(0)
            for j in range(-radio, radio + 1):
                for i in range(-radio, radio + 1):
                    yy, xx = y + j, x + i
                    if 0 <= yy < alto and 0 <= xx < ancho:
                        suma = np.float32(suma + np.float32(
                            imagen[yy, xx] * mascara[(j + radio) * k + i + radio]))
            salida[y * ancho + x] = suma
    return salida


@pytest.mark.parametrize("filtro, k", [("media", 3), ("media", 9), ("laplaciano", 3)])
def test_referencia_cpu_equivale_a_convolucion_con_ceros(filtro, k):
    imagen = np.random.default_rng(3).integers(0, 256, (7, 11)).astype(np.float32)
    mascara = crear_mascara(filtro, k)
    assert np.allclose(referencia_cpu(imagen, mascara, k),
                       _convolucion_ingenua(imagen, mascara, k), atol=1e-4)


def test_equipo_muestra_especificaciones(tmp_path):
    datos = crear_cliente(tmp_path).get("/api/equipo").get_json()
    assert datos["gpu"]["compute_capability"] == "8.6"
    assert datos["servidor"]["cpu"] and datos["servidor"]["nucleos_logicos"] >= 1
    assert datos["limites"]["hilos_por_bloque"] == 256


def test_equipo_informa_gpu_ausente_sin_fallar(tmp_path):
    cliente = crear_cliente(tmp_path, procesador=ProcesadorQueFalla(GPUNoDisponible("sin GPU")))
    respuesta = cliente.get("/api/equipo")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["gpu"] is None
    assert respuesta.get_json()["error_gpu"] == "sin GPU"
