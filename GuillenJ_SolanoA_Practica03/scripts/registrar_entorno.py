"""Registra versiones, hardware, contenedor y trazabilidad sin inventar datos."""
import argparse
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

from webapp.sistema import nombre_cpu, ram_total_gib, version_paquete


def ejecutar(comando, cwd=None):
    try:
        resultado = subprocess.run(comando, cwd=cwd, capture_output=True, text=True,
                                   timeout=60, check=False)
        salida = resultado.stdout.strip() or resultado.stderr.strip()
        return salida if salida else ("" if resultado.returncode == 0 else
                                      f"sin salida (código {resultado.returncode})")
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"no disponible: {error}"


def direcciones_ip():
    try:
        return sorted({ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                       if not ip.startswith("127.")})
    except OSError:
        return []


def version_cuda_controlador(raiz):
    """Versión máxima de CUDA que admite el controlador (cabecera de nvidia-smi)."""
    salida = ejecutar(["nvidia-smi"], raiz)
    coincidencia = re.search(r"CUDA Version:\s*([\d.]+)", salida)
    return coincidencia.group(1) if coincidencia else "no disponible"


def git(comando, raiz):
    return ejecutar(["git", "-c", f"safe.directory={raiz.as_posix()}", *comando], raiz)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entorno", required=True,
                        help="Ejemplos: anfitrion, contenedor, nube-gpu")
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--commit-practica02", default="NO_DECLARADO",
                        help="Commit exacto que se tomó como origen para la práctica 03")
    parser.add_argument("--commit-practica03",
                        help="Commit exacto verificado antes de construir la imagen")
    parser.add_argument("--ubicacion",
                        default="Servidor local con GPU NVIDIA (sin instancia de nube)",
                        help="Proveedor de nube o ubicación física del equipo")
    parser.add_argument("--arbol-limpio-verificado", action="store_true",
                        help="El ejecutor verificó el árbol antes de construir y medir")
    args = parser.parse_args()
    raiz_p03 = Path(__file__).resolve().parents[1]
    raiz_repo = raiz_p03.parent
    salida = args.salida or raiz_p03 / "resultados" / "mediciones" / f"entorno_{args.entorno}.json"
    paquetes = ("Flask", "gunicorn", "numpy", "Pillow", "pycuda", "matplotlib", "pytest")
    estado = git(["status", "--porcelain"], raiz_repo)
    git_disponible = not estado.startswith("no disponible:")
    arbol_limpio = args.arbol_limpio_verificado or (git_disponible and estado == "")
    registro = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "entorno": args.entorno,
        "equipo": {
            "ubicacion": args.ubicacion,
            "sistema": platform.platform(),
            "cpu": nombre_cpu(),
            "nucleos_logicos": os.cpu_count(),
            "ram_total_gib": ram_total_gib(),
            "python": platform.python_version(),
            "ejecutable_python": sys.executable,
        },
        "gpu": {
            "nvidia_smi": ejecutar([
                "nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap",
                "--format=csv,noheader"], raiz_repo),
            "cuda_maxima_controlador": version_cuda_controlador(raiz_repo),
            "nota": ("El controlador NVIDIA pertenece al anfitrión; la imagen aporta CUDA "
                     "Toolkit 12.9 (nvcc), Python y PyCUDA."),
        },
        "software": {
            "docker": ejecutar(["docker", "--version"], raiz_repo),
            "docker_servidor": ejecutar(
                ["docker", "info", "--format",
                 "{{.ServerVersion}} | {{.OperatingSystem}} | kernel {{.KernelVersion}} | "
                 "runtime por defecto {{.DefaultRuntime}} | runtimes disponibles: "
                 "{{range $nombre, $valor := .Runtimes}}{{$nombre}}={{$valor.Path}} {{end}}"],
                raiz_repo),
            "nvidia_container_toolkit": ejecutar(["nvidia-container-cli", "--version"],
                                                 raiz_repo),
            "imagen_docker_p03": ejecutar(
                ["docker", "image", "inspect", "convolucion-pycuda:p03",
                 "--format", "{{.Id}} | revision={{index .Config.Labels "
                 "\"org.opencontainers.image.revision\"}}"], raiz_repo),
            "imagen_base_digest": ejecutar(
                ["docker", "image", "inspect", "nvidia/cuda:12.9.1-devel-ubuntu24.04",
                 "--format", "{{json .RepoDigests}}"], raiz_repo),
            "nvcc": ejecutar(["nvcc", "--version"], raiz_repo),
            "paquetes": {paquete: version_paquete(paquete) for paquete in paquetes},
        },
        "contenedor": {
            "hostname": platform.node(),
            "indicador_docker": Path("/.dockerenv").exists(),
            "imagen_base": "nvidia/cuda:12.9.1-devel-ubuntu24.04",
            "commit_en_imagen": os.environ.get("COMMIT_PRACTICA03", "no aplica"),
        },
        "red": {
            "direcciones_ip": direcciones_ip(),
            "puerto_contenedor": 8000,
            "puerto_publicado_anfitrion": 8080,
            "acceso": "http://<IP del anfitrión>:8080 (interfaz) y POST /api/convoluciones",
        },
        "repositorio": {
            "commit_practica03": (args.commit_practica03
                                  or os.environ.get("COMMIT_PRACTICA03")
                                  or git(["rev-parse", "HEAD"], raiz_repo)),
            "commit_origen_practica02": args.commit_practica02,
            "arbol_limpio": arbol_limpio,
            "estado_porcelain": [] if arbol_limpio else estado.splitlines(),
            "verificacion": ("ejecutor_antes_de_construir" if args.arbol_limpio_verificado
                              else "git_status_local"),
            "ruta_practica02": str(Path(os.environ.get(
                "PRACTICA02_ROOT", raiz_repo / "GuillenJ_SolanoA_Practica0"))),
        },
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Entorno registrado en {salida}")
    if not arbol_limpio:
        print("AVISO: el árbol tiene cambios sin commit; no usar como medición final trazable.")


if __name__ == "__main__":
    main()

