"""Datos del equipo donde corre el servicio (anfitrión o contenedor), sin valores fijos."""
import os
import platform
import re
import subprocess
import sys
from functools import lru_cache
from importlib import metadata
from pathlib import Path


def nombre_cpu():
    """Modelo comercial de la CPU (registro en Windows, /proc/cpuinfo en Linux)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as clave:
                return winreg.QueryValueEx(clave, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    try:
        for linea in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if linea.startswith("model name"):
                return linea.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "no informado por el sistema"


def ram_total_gib():
    """RAM física visible para este sistema (en WSL2/contenedor: la asignada a la VM)."""
    if sys.platform == "win32":
        import ctypes

        class Estado(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        estado = Estado()
        estado.dwLength = ctypes.sizeof(Estado)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return round(estado.ullTotalPhys / 2**30, 2)
        return None
    try:
        texto = Path("/proc/meminfo").read_text(encoding="utf-8")
        kib = int(re.search(r"MemTotal:\s+(\d+)", texto).group(1))
        return round(kib / 2**20, 2)
    except (OSError, AttributeError):
        return None


def version_paquete(nombre):
    try:
        return metadata.version(nombre)
    except metadata.PackageNotFoundError:
        return "no instalado"


def version_nvcc():
    try:
        salida = subprocess.run(["nvcc", "--version"], capture_output=True, text=True,
                                timeout=20, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "no disponible"
    coincidencia = re.search(r"release ([\d.]+)", salida)
    return coincidencia.group(1) if coincidencia else "no disponible"


@lru_cache(maxsize=1)
def datos_equipo():
    """Datos estáticos del servidor; se calculan una sola vez por proceso."""
    return {
        "cpu": nombre_cpu(),
        "nucleos_logicos": os.cpu_count(),
        "ram_total_gib": ram_total_gib(),
        "sistema": platform.platform(),
        "en_contenedor": Path("/.dockerenv").exists(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "cuda_toolkit_nvcc": version_nvcc(),
        "paquetes": {nombre: version_paquete(nombre)
                     for nombre in ("pycuda", "numpy", "Pillow", "Flask", "gunicorn")},
        "commit_practica03": os.environ.get("COMMIT_PRACTICA03", "no declarado"),
    }
