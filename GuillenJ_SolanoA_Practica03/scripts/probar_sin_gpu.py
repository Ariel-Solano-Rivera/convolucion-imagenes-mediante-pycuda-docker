"""Evidencia de diagnóstico sin GPU: la misma imagen iniciada sin ``--gpus``.

Se espera HTTP 503 con código ``gpu_no_disponible`` tanto en /api/salud como en una
solicitud de convolución, y ningún resultado calculado en CPU.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from scripts.util_http import enviar_imagen


def consultar_salud(url, intentos=30):
    for _ in range(intentos):
        try:
            with urlopen(url.rstrip("/") + "/api/salud", timeout=10) as respuesta:
                return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))
        except URLError:
            time.sleep(2)
    return 0, {"error": "El servicio sin GPU no respondió."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8081")
    parser.add_argument("--imagen", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    estado_salud, cuerpo_salud = consultar_salud(args.url)
    respuesta = enviar_imagen(args.url, args.imagen, "media", 3)
    evidencia = {
        "escenario": "misma imagen Docker iniciada sin --gpus",
        "salud": {"http": estado_salud, "cuerpo": cuerpo_salud},
        "convolucion": {"http": respuesta.estado_http, "cuerpo": respuesta.cuerpo},
    }
    correcto = (estado_salud == 503 and respuesta.estado_http == 503
                and respuesta.cuerpo.get("codigo") == "gpu_no_disponible"
                and "resultado_url" not in respuesta.cuerpo)
    evidencia["resultado"] = "OK" if correcto else "FALLA"
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(json.dumps(evidencia, ensure_ascii=False))
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())
