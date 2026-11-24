"""Lee los CSV de resultados y calcula las cifras del informe y la presentación.

Todas las cifras salen de los CSV generados por el código entregado:
  resultados/mediciones/mediciones.csv                C++ secuencial y CUDA C
  resultados/mediciones/mediciones_python_pycuda.csv  Python secuencial y PyCUDA
  resultados/mediciones/inicializacion.csv            contexto y compilación PyCUDA
  resultados/pruebas/*.csv                            prueba manual y validación
Python secuencial con estado distinto de "medido" se trata como NO COMPLETADA:
se informa el tiempo transcurrido y las filas procesadas, nunca la estimación.
"""
import csv
import json
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
MEDICIONES = RAIZ / "resultados" / "mediciones"
PRUEBAS = RAIZ / "resultados" / "pruebas"

VERSIONES = ("cpp_secuencial", "cuda_c", "python_secuencial", "pycuda")
NOMBRES = {"cpp_secuencial": "C++ secuencial", "cuda_c": "CUDA C",
           "python_secuencial": "Python secuencial", "pycuda": "PyCUDA"}

# Configuraciones de los experimentos: (filtro, k, lado, hilos)
EXP_FILTROS = [("media", 3, 4000, 256), ("nitidez", 3, 4000, 256), ("laplaciano", 3, 4000, 256)]
EXP_RESOLUCION = [("media", 9, 2000, 256), ("media", 9, 4000, 256), ("media", 9, 6000, 256)]
EXP_MASCARA = [("media", 3, 4000, 256), ("media", 9, 4000, 256), ("media", 21, 4000, 256)]
EXP_HILOS = [("media", 9, 4000, h) for h in (128, 256, 512)]


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _num(valor):
    return None if valor in ("", "NA", None) else float(valor)


def cargar_mediciones():
    """Une ambos CSV en un formato común."""
    filas = []
    for f in leer(MEDICIONES / "mediciones.csv"):
        filas.append({
            "version": "cpp_secuencial" if f["implementacion"] == "CPU" else "cuda_c",
            "estado": "completada", "filtro": f["filtro"], "k": int(f["mascara"]),
            "lado": int(f["ancho"]), "alto": int(f["alto"]),
            "hilos": None if f["hilos_bloque"] == "NA" else int(f["hilos_bloque"]),
            "bloques": None if f["bloques"] == "NA" else int(f["bloques"]),
            "h2d": _num(f["t_h2d"]), "kernel": _num(f["t_kernel"]),
            "d2h": _num(f["t_d2h"]), "total": _num(f["t_total"]),
            "filas_procesadas": None})
    for f in leer(MEDICIONES / "mediciones_python_pycuda.csv"):
        python = f["version"] == "python_secuencial"
        filas.append({
            "version": f["version"],
            "estado": "completada" if f["estado"] == "medido" else "no_completada",
            "filtro": f["filtro"], "k": int(f["mascara"]), "lado": int(f["ancho"]),
            "alto": int(f["alto"]),
            # Python no usa hilos de GPU: la columna del CSV no aplica.
            "hilos": None if python else int(f["hilos_bloque"]),
            "bloques": None,
            "h2d": None if python else _num(f["t_h2d_ms"]),
            "kernel": None if python else _num(f["t_kernel_ms"]),
            "d2h": None if python else _num(f["t_d2h_ms"]),
            "total": _num(f["t_total_ms"]),
            "filas_procesadas": _num(f["filas_procesadas"]),
            "limite_s": _num(f["limite_s"])})
    return filas


class Resumen:
    """Estadísticos de una serie de repeticiones (ms)."""

    def __init__(self, valores):
        v = np.asarray(valores, dtype=float)
        self.n = len(v)
        self.mediana = float(np.median(v))
        self.q1, self.q3 = (float(x) for x in np.percentile(v, [25, 75]))
        self.iqr = self.q3 - self.q1
        self.media = float(v.mean())
        self.de = float(v.std(ddof=1)) if len(v) > 1 else 0.0
        self.cv = self.de / self.media if self.media else 0.0
        self.minimo, self.maximo = float(v.min()), float(v.max())


class Datos:
    def __init__(self):
        self.filas = cargar_mediciones()
        self.validacion_c = leer(PRUEBAS / "validacion.csv")
        self.validacion_py = leer(PRUEBAS / "validacion_python_pycuda.csv")
        self.manual_c = leer(PRUEBAS / "prueba_manual.csv")
        self.manual_py = leer(PRUEBAS / "prueba_manual_python_pycuda.csv")
        self.inicializacion = leer(MEDICIONES / "inicializacion.csv")
        self.entorno = json.loads((MEDICIONES / "entorno.json").read_text(encoding="utf-8"))
        visual = PRUEBAS / "evidencia_visual.csv"
        self.visual = leer(visual) if visual.exists() else []

    # --- búsqueda ---------------------------------------------------------
    def serie(self, version, filtro, k, lado, hilos=256, estado="completada"):
        h = None if version in ("cpp_secuencial", "python_secuencial") else hilos
        return [f for f in self.filas if f["version"] == version and f["filtro"] == filtro
                and f["k"] == k and f["lado"] == lado and f["hilos"] == h
                and f["estado"] == estado]

    def resumen(self, version, filtro, k, lado, campo="total", hilos=256):
        """Resumen de la columna; None si la configuración no se completó."""
        serie = self.serie(version, filtro, k, lado, hilos)
        if not serie:
            return None
        return Resumen([f[campo] for f in serie])

    def no_completada(self, filtro, k, lado):
        """Primera fila no completada de Python (hilos 256) para esa configuración."""
        for f in self.filas:
            if (f["version"] == "python_secuencial" and f["estado"] == "no_completada"
                    and f["filtro"] == filtro and f["k"] == k and f["lado"] == lado):
                return f
        return None

    def no_completadas(self):
        vistas, salida = set(), []
        for f in self.filas:
            clave = (f["filtro"], f["k"], f["lado"])
            if (f["version"] == "python_secuencial" and f["estado"] == "no_completada"
                    and clave not in vistas):
                vistas.add(clave)
                salida.append(f)
        return salida

    def intentos_no_completados(self):
        return [f for f in self.filas
                if f["version"] == "python_secuencial" and f["estado"] == "no_completada"]

    def repeticiones(self, version):
        return sorted({len(self.serie(version, *c)) for c in EXP_FILTROS + EXP_RESOLUCION
                       + EXP_MASCARA if self.serie(version, *c)})

    # --- fila consolidada de una configuración ---------------------------
    def configuracion(self, filtro, k, lado, hilos=256):
        r = {"filtro": filtro, "k": k, "lado": lado, "hilos": hilos}
        r["cpp"] = self.resumen("cpp_secuencial", filtro, k, lado)
        r["py"] = self.resumen("python_secuencial", filtro, k, lado)
        r["py_nc"] = None if r["py"] else self.no_completada(filtro, k, lado)
        for v, pref in (("cuda_c", "cu"), ("pycuda", "pc")):
            for campo in ("h2d", "kernel", "d2h", "total"):
                r[f"{pref}_{campo}"] = self.resumen(v, filtro, k, lado, campo, hilos)
        n = lado * lado
        r["bloques"] = (n + hilos - 1) // hilos
        if r["cpp"]:
            r["acel_cu_kernel"] = r["cpp"].mediana / r["cu_kernel"].mediana
            r["acel_cu_total"] = r["cpp"].mediana / r["cu_total"].mediana
        if r["py"]:
            r["acel_pc_kernel"] = r["py"].mediana / r["pc_kernel"].mediana
            r["acel_pc_total"] = r["py"].mediana / r["pc_total"].mediana
            r["py_vs_cpp"] = r["py"].mediana / r["cpp"].mediana
        for nombre, version in (("cu", "cuda_c"), ("pc", "pycuda")):
            # Proporción de copias calculada en cada repetición; se reporta su mediana.
            serie = self.serie(version, filtro, k, lado, hilos)
            r[f"{nombre}_pct_transf"] = float(np.median(
                [100 * (f["h2d"] + f["d2h"]) / f["total"] for f in serie]))
        r["pc_vs_cu_kernel"] = r["pc_kernel"].mediana / r["cu_kernel"].mediana
        r["pc_vs_cu_total"] = r["pc_total"].mediana / r["cu_total"].mediana
        return r

    # --- validación --------------------------------------------------------
    def errores_por_version(self):
        """Error máximo y medio frente a C++ secuencial, por versión."""
        salida = {}
        for version in ("cuda_c", "python_secuencial", "pycuda"):
            filas = [f for f in self.validacion_py
                     if f["version"] == version and f["referencia"] == "cpp_secuencial"]
            filas += [f for f in self.visual if f["version"] == version]
            salida[version] = {
                "casos": len(filas),
                "ok": sum(f["resultado"] == "OK" for f in filas),
                "max": max(float(f["error_max"]) for f in filas),
                "medio_max": max(float(f["error_medio"]) for f in filas)}
        filas = [f for f in self.validacion_py if f["referencia"] == "cuda_c"]
        salida["pycuda_vs_cuda_c"] = {
            "casos": len(filas), "ok": sum(f["resultado"] == "OK" for f in filas),
            "max": max(float(f["error_max"]) for f in filas),
            "medio_max": max(float(f["error_medio"]) for f in filas)}
        return salida

    def todas_validaciones_ok(self):
        listas = (self.validacion_c, self.validacion_py, self.manual_c, self.manual_py,
                  self.visual)
        return all(f["resultado"] == "OK" for lista in listas for f in lista)

    def tiempos_inicializacion(self):
        return {f["etapa"]: float(f["tiempo"]) for f in self.inicializacion}


if __name__ == "__main__":
    d = Datos()
    for nombre, exp in (("FILTROS", EXP_FILTROS), ("RESOLUCION", EXP_RESOLUCION),
                        ("MASCARA", EXP_MASCARA), ("HILOS", EXP_HILOS)):
        print(f"== {nombre}")
        for c in exp:
            r = d.configuracion(*c)
            py = (f"{r['py'].mediana:.1f} (IQR {r['py'].iqr:.1f}, n={r['py'].n})" if r["py"]
                  else f"NO COMPLETADA {r['py_nc']['total']/1000:.1f}s, filas {r['py_nc']['filas_procesadas']:.0f}")
            print(f"{c}: cpp {r['cpp'].mediana:.1f}({r['cpp'].iqr:.1f}) py {py}")
            for p in ("cu", "pc"):
                print(f"   {p}: h2d {r[p+'_h2d'].mediana:.2f} k {r[p+'_kernel'].mediana:.3f}"
                      f" (iqr {r[p+'_kernel'].iqr:.3f} cv {100*r[p+'_kernel'].cv:.1f}% min {r[p+'_kernel'].minimo:.3f} max {r[p+'_kernel'].maximo:.3f})"
                      f" d2h {r[p+'_d2h'].mediana:.2f} tot {r[p+'_total'].mediana:.2f} (iqr {r[p+'_total'].iqr:.2f}, cv {100*r[p+'_total'].cv:.1f}%)"
                      f" transf {r[p+'_pct_transf']:.1f}%")
            print(f"   acel cu k {r['acel_cu_kernel']:.1f} t {r['acel_cu_total']:.1f};"
                  + (f" pc k {r['acel_pc_kernel']:.1f} t {r['acel_pc_total']:.1f} py/cpp {r['py_vs_cpp']:.1f}" if r["py"] else "")
                  + f"; pc/cu k {r['pc_vs_cu_kernel']:.3f} t {r['pc_vs_cu_total']:.3f}")
    print(d.errores_por_version())
    print("todas OK:", d.todas_validaciones_ok())
    print(d.tiempos_inicializacion())
    for f in d.intentos_no_completados():
        print(f["filtro"], f["k"], f["lado"], f["total"], f["filas_procesadas"])
