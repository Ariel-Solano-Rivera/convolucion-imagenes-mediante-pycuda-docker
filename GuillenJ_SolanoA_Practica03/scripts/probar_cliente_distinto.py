"""Consume el servicio desde un contenedor distinto y emite evidencia JSON."""
import argparse
import json
import platform
import socket
from pathlib import Path

from scripts.util_http import enviar_imagen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://convolucion:8000")
    parser.add_argument("--imagen", type=Path,
                        default=Path("/opt/practica02/datos/base_250.pgm"))
    args = parser.parse_args()
    respuesta = enviar_imagen(args.url, args.imagen, "media", 3)
    evidencia = {
        "tipo_cliente": "contenedor_separado_sin_gpu_requerida",
        "hostname_cliente": socket.gethostname(),
        "sistema_cliente": platform.platform(),
        "url_servicio": args.url,
        "imagen": str(args.imagen),
        "http": respuesta.estado_http,
        "id_solicitud": respuesta.cuerpo.get("id_solicitud", ""),
        "dimensiones": respuesta.cuerpo.get("dimensiones", {}),
        "tiempo_cliente_hasta_descarga_ms": round(respuesta.tiempo_cliente_ms, 4),
        "resultado": "OK" if respuesta.estado_http == 201 else "FALLA",
        "error": respuesta.cuerpo.get("error", ""),
    }
    print(json.dumps(evidencia, ensure_ascii=False))
    return 0 if evidencia["resultado"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
