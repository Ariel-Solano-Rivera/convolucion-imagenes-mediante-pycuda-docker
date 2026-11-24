from io import BytesIO

import numpy as np
from PIL import Image

from webapp import crear_aplicacion
from webapp.procesador_gpu import ResultadoGPU


class ProcesadorFalso:
    def procesar(self, entrada, _mascara, _ancho, _alto, _k):
        return ResultadoGPU(entrada.copy(), 1.0, 2.0, 1.0, 4.0, 0.0, None,
                            reserva_liberacion_ms=0.5, memoria_reservada_bytes=68,
                            memoria_gpu_usada_bytes=1024, memoria_gpu_total_bytes=4096,
                            bloques=1, hilos=256)

    def diagnosticar(self):
        return {"gpu": "falsa", "compute_capability": "8.6"}


def imagen_png():
    memoria = BytesIO()
    Image.fromarray(np.array([[0, 255], [64, 128]], dtype=np.uint8)).save(memoria, format="PNG")
    memoria.seek(0)
    return memoria


def crear_cliente(tmp_path, procesador=None, **cambios):
    configuracion = {
        "DIRECTORIO_RESULTADOS": tmp_path / "resultados",
        "PRACTICA02_ROOT": tmp_path / "no_usado",
        "MAX_CONTENT_LENGTH": 1024 * 1024,
        "MAX_PIXELES_ENTRADA": 1000,
        "MAX_PIXELES": 100,
        "HILOS_POR_BLOQUE": 256,
        "LIMITE_TRABAJOS_GPU": 2,
        "RETENCION_RESULTADOS_SEGUNDOS": 60,
    }
    configuracion.update(cambios)
    return crear_aplicacion(configuracion=configuracion,
                            procesador=procesador or ProcesadorFalso()).test_client()


def test_servicio_devuelve_imagen_y_tiempos(tmp_path):
    cliente = crear_cliente(tmp_path)
    respuesta = cliente.post("/api/convoluciones", data={
        "imagen": (imagen_png(), "entrada.png"), "filtro": "media", "mascara": "3",
    })
    cuerpo = respuesta.get_json()
    assert respuesta.status_code == 201
    assert cuerpo["dimensiones"] == {"ancho": 2, "alto": 2}
    assert cuerpo["dimensiones_originales"] == {"ancho": 2, "alto": 2}
    assert cuerpo["preparacion"]["aplicada"] is False
    assert cuerpo["entrada_preparada_url"] == cuerpo["original_url"]
    assert cuerpo["tiempos_ms"]["kernel"] == 2.0
    assert cliente.get(cuerpo["resultado_url"]).status_code == 200
    crudo = cliente.get(cuerpo["resultado_crudo_url"])
    assert crudo.status_code == 200
    assert np.load(BytesIO(crudo.data), allow_pickle=False).dtype == np.float32


def test_rechaza_filtro_desconocido(tmp_path):
    respuesta = crear_cliente(tmp_path).post("/api/convoluciones", data={
        "imagen": (imagen_png(), "entrada.png"), "filtro": "otro", "mascara": "3",
    })
    assert respuesta.status_code == 400
    assert "filtro" in respuesta.get_json()["error"].lower()


def test_no_permite_rutas_ajenas_en_resultados(tmp_path):
    respuesta = crear_cliente(tmp_path).get("/api/resultados/no-es-un-uuid/resultado.png")
    assert respuesta.status_code == 404


def test_rechaza_archivo_que_no_es_imagen(tmp_path):
    respuesta = crear_cliente(tmp_path).post("/api/convoluciones", data={
        "imagen": (BytesIO(b"esto no es una imagen"), "falsa.png"),
        "filtro": "media", "mascara": "3",
    })
    assert respuesta.status_code == 400
    assert "imagen" in respuesta.get_json()["error"].lower()


def test_rechaza_mascara_no_permitida(tmp_path):
    respuesta = crear_cliente(tmp_path).post("/api/convoluciones", data={
        "imagen": (imagen_png(), "entrada.png"), "filtro": "media", "mascara": "5",
    })
    assert respuesta.status_code == 400
    assert "máscaras" in respuesta.get_json()["error"].lower()


def test_solicitudes_no_comparten_resultados(tmp_path):
    cliente = crear_cliente(tmp_path)
    cuerpos = []
    for filtro in ("media", "nitidez"):
        respuesta = cliente.post("/api/convoluciones", data={
            "imagen": (imagen_png(), f"{filtro}.png"), "filtro": filtro, "mascara": "3",
        })
        assert respuesta.status_code == 201
        cuerpos.append(respuesta.get_json())
    assert cuerpos[0]["id_solicitud"] != cuerpos[1]["id_solicitud"]
    assert cuerpos[0]["resultado_url"] != cuerpos[1]["resultado_url"]


def test_prepara_imagen_grande_con_recorte_y_redimension(tmp_path):
    memoria = BytesIO()
    Image.fromarray(np.arange(12 * 11, dtype=np.uint8).reshape(12, 11)).save(
        memoria, format="PNG")
    memoria.seek(0)
    cliente = crear_cliente(tmp_path)
    respuesta = cliente.post("/api/convoluciones", data={
        "imagen": (memoria, "grande.png"), "filtro": "media", "mascara": "3",
    })
    cuerpo = respuesta.get_json()
    assert respuesta.status_code == 201
    assert cuerpo["dimensiones_originales"] == {"ancho": 11, "alto": 12}
    assert cuerpo["dimensiones"] == {"ancho": 10, "alto": 10}
    assert cuerpo["preparacion"] == {
        "aplicada": True,
        "recorte_central": True,
        "redimensionada": True,
        "recorte": [0, 0, 11, 11],
    }
    with Image.open(BytesIO(cliente.get(cuerpo["original_url"]).data)) as original:
        assert original.size == (10, 10)


def test_rechaza_imagen_que_supera_limite_de_entrada(tmp_path):
    memoria = BytesIO()
    Image.fromarray(np.zeros((12, 11), dtype=np.uint8)).save(memoria, format="PNG")
    memoria.seek(0)
    respuesta = crear_cliente(tmp_path, MAX_PIXELES_ENTRADA=120).post(
        "/api/convoluciones", data={
            "imagen": (memoria, "demasiado-grande.png"),
            "filtro": "media", "mascara": "3",
        })
    assert respuesta.status_code == 400
    assert "límite de entrada" in respuesta.get_json()["error"].lower()


def test_rechaza_archivo_que_supera_limite_de_bytes(tmp_path):
    respuesta = crear_cliente(tmp_path).post("/api/convoluciones", data={
        "imagen": (BytesIO(b"x" * (1024 * 1024)), "grande.bin"),
        "filtro": "media", "mascara": "3",
    })
    assert respuesta.status_code == 413


def test_interfaz_y_salud_estan_disponibles(tmp_path):
    cliente = crear_cliente(tmp_path)
    interfaz = cliente.get("/")
    assert interfaz.status_code == 200
    assert "Tiempo total percibido" in interfaz.get_data(as_text=True)
    salud = cliente.get("/api/salud")
    assert salud.status_code == 200
    assert salud.get_json()["estado"] == "listo"

