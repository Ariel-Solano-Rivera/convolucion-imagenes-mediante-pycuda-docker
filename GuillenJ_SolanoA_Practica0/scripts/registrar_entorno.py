"""Registra el entorno de ejecucion en resultados/mediciones/entorno.json."""
import json
import platform
import re
import subprocess
import sys
from datetime import datetime
from importlib import metadata

from src.python.comun.configuracion import (
    ARQUITECTURA, MEDICIONES, OPCIONES_NVCC, RAIZ_REPO)


def ejecutar(comando):
    """Devuelve la salida de un comando o un texto 'no disponible'."""
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=60,
                           cwd=RAIZ_REPO)
        return (r.stdout.strip() or r.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"no disponible: {error}"


def version_cl():
    """cl.exe escribe su version en stderr con la pagina de codigos OEM."""
    try:
        r = subprocess.run(["cl"], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "no disponible (ejecute scripts\\entorno_vs.bat)"
    texto = r.stderr.decode("oem", errors="replace")
    encontrado = re.search(r"\d+\.\d+\.\d+(\.\d+)?", texto)
    return f"MSVC cl.exe {encontrado.group(0)} x64" if encontrado else texto.strip()


def powershell_json(script):
    salida = ejecutar(["powershell", "-NoProfile", "-Command",
                       script + " | ConvertTo-Json"])
    try:
        return json.loads(salida)
    except json.JSONDecodeError:
        return {"error": salida}


def equipo():
    datos = powershell_json(
        "$p = Get-CimInstance Win32_Processor | Select-Object -First 1;"
        "$c = Get-CimInstance Win32_ComputerSystem;"
        "$o = Get-CimInstance Win32_OperatingSystem;"
        "[pscustomobject]@{cpu=$p.Name.Trim(); nucleos=$p.NumberOfCores;"
        "hilos=$p.NumberOfLogicalProcessors; ram=$c.TotalPhysicalMemory;"
        "so=$o.Caption; so_version=$o.Version}")
    if "error" in datos:
        return datos
    return {
        "cpu": datos["cpu"],
        "nucleos_fisicos": datos["nucleos"],
        "hilos_logicos": datos["hilos"],
        "ram_gib": round(int(datos["ram"]) / 2**30, 2),
        "so": f'{datos["so"]} (version {datos["so_version"]})',
        "plataforma": platform.platform(),
    }


def gpu():
    consulta = ejecutar(["nvidia-smi",
                         "--query-gpu=name,memory.total,driver_version,compute_cap",
                         "--format=csv,noheader"])
    info = {"nvidia_smi": consulta}
    try:
        import pycuda.driver as cuda
        cuda.init()
        dispositivo = cuda.Device(0)
        mayor, menor = dispositivo.compute_capability()
        info.update({
            "nombre": dispositivo.name(),
            "memoria_mib": dispositivo.total_memory() // 2**20,
            "capacidad_computo": f"{mayor}.{menor}",
            "arquitectura_compilacion": ARQUITECTURA,
            "arquitectura_coincide": f"sm_{mayor}{menor}" == ARQUITECTURA,
            # Version maxima de CUDA que soporta el controlador (p. ej. 13020 -> 13.2).
            "cuda_soportada_por_controlador":
                f"{cuda.get_driver_version() // 1000}."
                f"{cuda.get_driver_version() % 1000 // 10}",
            "pycuda_compilado_con_cuda": ".".join(map(str, cuda.get_version())),
        })
    except Exception as error:  # el registro no debe abortar por la GPU
        info["error_pycuda"] = repr(error)
    return info


def versiones():
    paquetes = ("numpy", "pycuda", "pillow", "matplotlib", "pytest", "pytools")
    datos = {"python": platform.python_version(),
             "python_ejecutable": f"{platform.python_implementation()} "
                                  f"{sys.version.split()[0]} {platform.architecture()[0]}"}
    for paquete in paquetes:
        try:
            datos[paquete] = metadata.version(paquete)
        except metadata.PackageNotFoundError:
            datos[paquete] = "no instalado"
    nvcc = ejecutar(["nvcc", "--version"]).splitlines()
    datos["cuda_toolkit_nvcc"] = nvcc[-2] if len(nvcc) >= 2 else "no disponible"
    datos["compilador_cl"] = version_cl()
    datos["opciones_nvcc"] = OPCIONES_NVCC + [f"arch={ARQUITECTURA}"]
    return datos


def repositorio():
    estado = ejecutar(["git", "status", "--porcelain"])
    return {
        "commit_p02": ejecutar(["git", "rev-parse", "HEAD"]),
        "arbol_limpio": estado == "",
        "cambios_sin_commit": estado.splitlines(),
        "commit_p01": ejecutar(["git", "rev-list", "-n", "1", "practica01-entrega"]),
        "tag_p01": "practica01-entrega",
    }


def main():
    registro = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "equipo": equipo(),
        "gpu": gpu(),
        "versiones": versiones(),
        "repositorio": repositorio(),
    }
    MEDICIONES.mkdir(parents=True, exist_ok=True)
    destino = MEDICIONES / "entorno.json"
    destino.write_text(json.dumps(registro, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"Entorno registrado en {destino.relative_to(RAIZ_REPO)}")
    if not registro["repositorio"]["arbol_limpio"]:
        print("AVISO: el arbol de trabajo tiene cambios sin commit.")


if __name__ == "__main__":
    main()
