"""Genera el informe de la práctica 03 (Word) con el formato UPS de las prácticas anteriores.

Todas las cifras se leen de resultados/ (CSV y JSON generados por ejecutar_experimentos.ps1).
Salidas:
  ../docs/informe/informe_practica03.docx   (PDF con scripts/exportar_pdf.ps1)
  ../docs/informe/figuras_p03/*.png
Uso: .venv\\Scripts\\python.exe -m scripts.generar_informe
"""
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Pt  # noqa: E402

from scripts.formato_docx import (Marco, e, encabezado_pie, estilos, formato_parrafo, n,  # noqa: E402
                                  pct, recursos_guia)

RAIZ = Path(__file__).resolve().parents[1]
REPO = RAIZ.parent
RES = RAIZ / "resultados"
MED = RES / "mediciones"
PRU = RES / "pruebas"
EVI = RES / "evidencia"
GRA = RES / "graficas"
DOCS = REPO / "docs" / "informe"
FIGURAS = DOCS / "figuras_p03"
CAPTURAS = DOCS / "imagenes_otra_pc"
SALIDA = DOCS / "informe_practica03.docx"
DATOS_P02 = REPO / "GuillenJ_SolanoA_Practica0" / "datos"
URL_TUNEL = "https://released-absolute-veteran-commonly.trycloudflare.com"
# Repositorio de entrega de la práctica 03 y repositorio de origen de la práctica 02.
URL_REPOSITORIO = "https://github.com/Ariel-Solano-Rivera/convolucion-imagenes-mediante-pycuda-docker"
URL_REPOSITORIO_P02 = "https://github.com/JuanGuillenA/procesamiento-imagenes-pycuda"


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as archivo:
        return list(csv.DictReader(archivo))


def leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8-sig"))


def git(*argumentos):
    return subprocess.run(["git", "-C", str(REPO), *argumentos], capture_output=True,
                          text=True, check=False).stdout.strip()


class Datos:
    def __init__(self):
        self.resumen = leer_csv(MED / "resumen.csv")
        self.filas = {nombre: leer_csv(MED / f"{nombre}.csv")
                      for nombre in ("directo_anfitrion", "directo_contenedor", "servicio")}
        self.anfitrion = leer_json(MED / "entorno_anfitrion_final.json")
        self.contenedor = leer_json(MED / "entorno_contenedor_final.json")
        self.manual = leer_csv(PRU / "prueba_manual_servicio.csv")
        self.bordes = leer_csv(PRU / "bordes_cobertura.csv")
        self.equivalencia = leer_csv(PRU / "validacion_directo_servicio.csv")
        self.invalidas = leer_csv(PRU / "entradas_invalidas.csv")
        self.aislamiento = leer_csv(PRU / "aislamiento_solicitudes.csv")
        self.cola = leer_csv(PRU / "cola_solicitudes.csv")
        self.sin_gpu = leer_json(EVI / "sin_gpu.json")
        self.copia = leer_json(EVI / "copia_limpia.json")
        self.cliente = leer_json(EVI / "cliente_distinto.json")
        self.salud = leer_json(EVI / "salud_servicio.json")
        self.commit_p03 = self.anfitrion["repositorio"]["commit_practica03"]
        self.commit_p02 = self.anfitrion["repositorio"]["commit_origen_practica02"]

    def r(self, experimento, modo="servicio_contenedor", entorno=None, filtro="media", k=9,
          lado=4000, conc=1):
        for f in self.resumen:
            if (experimento in f["experimento"].split("|") and f["modo_ejecucion"] == modo
                    and (entorno is None or f["entorno"] == entorno) and f["filtro"] == filtro
                    and int(f["mascara"]) == k and int(f["ancho"]) == lado
                    and int(f["concurrencia"]) == conc):
                return f
        raise KeyError((experimento, modo, entorno, filtro, k, lado, conc))

    @staticmethod
    def m(fila, columna):
        valor = fila.get(f"{columna}_mediana", "")
        return float(valor) if valor not in ("", None) else None

    @staticmethod
    def rango(fila, columna, dec=1):
        q1, q3 = fila.get(f"{columna}_q1", ""), fila.get(f"{columna}_q3", "")
        if q1 in ("", None):
            return "—"
        return f"{n(float(q1), dec)}–{n(float(q3), dec)}"

    def crudas(self, origen, experimento, **filtros):
        salida = []
        for f in self.filas[origen]:
            if experimento not in f["experimento"].split("|"):
                continue
            if all(str(f[c]) == str(v) for c, v in filtros.items()):
                salida.append(f)
        return salida

    def frio(self, origen):
        fila = next(f for f in self.filas[origen] if f["experimento"] == "arranque_frio")
        valor = float(fila["observaciones"].split("=")[1])
        return fila, valor

    def total_filas(self):
        return sum(len(v) for v in self.filas.values())

    def completadas(self):
        return sum(f["estado"] == "completada" for v in self.filas.values() for f in v)


def ms(valor, dec=1):
    if valor is None:
        return "—"
    return f"{n(valor, dec)}"


def sha_archivo(ruta):
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


# ---------------------------------------------------------------------------
# Figura de arquitectura
# ---------------------------------------------------------------------------
def figura_arquitectura():
    FIGURAS.mkdir(parents=True, exist_ok=True)
    fig, eje = plt.subplots(figsize=(10, 3.6))
    eje.set_xlim(0, 100)
    eje.set_ylim(0, 36)
    eje.axis("off")
    cajas = [
        (1, 13, 13, 10, "Navegador /\ncliente HTTP", "#eef2ff"),
        (19, 13, 16, 10, "Gunicorn\n1 proceso · 4 hilos\nFlask (api.py)", "#e0f2fe"),
        (40, 13, 17, 10, "procesamiento.py\ndecodificar → GPU\n→ PNG / NPY", "#e0f2fe"),
        (62, 13, 15, 10, "Cola (2 cupos)\n1 trabajador CUDA\ncontexto único", "#fef3c7"),
        (82, 13, 16, 10, "PyCUDA (P02)\nkernel propio\nRTX 3070", "#dcfce7"),
    ]
    for x0, y0, ancho, alto, texto, color in cajas:
        eje.add_patch(FancyBboxPatch((x0, y0), ancho, alto, boxstyle="round,pad=0.6",
                                     facecolor=color, edgecolor="#334155", linewidth=1))
        eje.text(x0 + ancho / 2, y0 + alto / 2, texto, ha="center", va="center", fontsize=8.5)
    for x0, x1 in ((14.6, 18.4), (35.6, 39.4), (57.6, 61.4), (77.6, 81.4)):
        eje.add_patch(FancyArrowPatch((x0, 19.5), (x1, 19.5), arrowstyle="-|>",
                                      mutation_scale=12, color="#334155"))
        eje.add_patch(FancyArrowPatch((x1, 16.5), (x0, 16.5), arrowstyle="-|>",
                                      mutation_scale=12, color="#94a3b8"))
    eje.add_patch(FancyBboxPatch((18, 3), 80.5, 27.5, boxstyle="round,pad=0.4", fill=False,
                                 edgecolor="#4f46e5", linewidth=1.2, linestyle="--"))
    eje.text(19, 31.5, "Contenedor Docker (nvidia/cuda:12.9.1-devel-ubuntu24.04, --gpus all)",
             fontsize=8.5, color="#4f46e5")
    eje.text(58, 5.5, "Anfitrión: controlador NVIDIA 596.36 + NVIDIA Container Toolkit (WSL2)",
             ha="center", fontsize=8, color="#475569")
    eje.text(1, 9.5, "POST /api/convoluciones\nGET /api/resultados/{uuid}/…", fontsize=7.5,
             color="#475569")
    plt.tight_layout()
    ruta = FIGURAS / "arquitectura.png"
    plt.savefig(ruta, dpi=180)
    plt.close()
    return ruta


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------
def tabla_fases(b, d, filas, etiquetas):
    columnas = ("t_decodificacion_ms", "t_espera_ms", "t_reserva_liberacion_ms", "t_h2d_ms",
                "t_kernel_ms", "t_d2h_ms", "t_gpu_total_ms", "t_codificacion_ms",
                "t_servidor_ms", "t_cliente_ms")
    datos = []
    for fila, etiqueta in zip(filas, etiquetas):
        datos.append([etiqueta] + [ms(d.m(fila, c), 2 if c in ("t_espera_ms",) else 1)
                                   for c in columnas])
    b.tabla(["Configuración", "Decodif.", "Espera", "Reserva", "H2D", "Kernel", "D2H",
             "GPU total", "Codif. y escritura", "Procesam. / servidor", "Cliente"],
            datos, [86, 38, 34, 38, 34, 38, 34, 42, 52, 54, 50], tam=7.5)


def tabla_variabilidad(b, d, filas, etiquetas):
    datos = []
    for fila, etiqueta in zip(filas, etiquetas):
        datos.append([etiqueta, fila["repeticiones"], d.rango(fila, "t_kernel_ms", 2),
                      d.rango(fila, "t_gpu_total_ms"), d.rango(fila, "t_servidor_ms", 0),
                      d.rango(fila, "t_cliente_ms", 0)])
    b.tabla(["Configuración", "n", "Kernel Q1–Q3", "GPU total Q1–Q3", "Servidor Q1–Q3",
             "Cliente Q1–Q3"], datos, [120, 24, 84, 90, 90, 92], tam=7.5)


def construir(d, logo, firmas, arquitectura):
    doc = Document()
    estilos(doc)
    encabezado_pie(doc, logo)
    marco = Marco(doc, logo)

    an, co = d.anfitrion, d.contenedor
    # Solo se afirma que la carpeta de P02 es idéntica si se pudo comprobar con Git.
    p02_identica = (git("cat-file", "-t", d.commit_p02) == "commit"
                    and git("diff", "--stat", d.commit_p02, d.commit_p03, "--",
                            "GuillenJ_SolanoA_Practica0") == "")
    posteriores = git("log", "--format=%h %s", f"{d.commit_p03}..HEAD").splitlines()
    cambiados = sorted({ruta for ruta in git("diff", "--name-only", d.commit_p03, "HEAD").splitlines()
                        if ruta.startswith("GuillenJ_SolanoA_Practica03/")
                        and "/resultados/" not in ruta})

    # Configuraciones principales (medianas del resumen)
    integ = [d.r("integracion", "pycuda_directo", "anfitrion"),
             d.r("integracion", "pycuda_directo", "contenedor"),
             d.r("integracion", "servicio_contenedor")]
    reso = [d.r("resolucion", lado=lado) for lado in (2000, 4000, 6000)]
    filt = [d.r("filtros_mascara", filtro=f, k=k) for f, k in
            (("media", 3), ("media", 9), ("media", 21), ("nitidez", 3), ("laplaciano", 3))]
    conc = [d.r("concurrencia", conc=c) for c in (1, 2)]
    s4 = integ[2]
    m = d.m
    frac_codif = m(s4, "t_codificacion_ms") / m(s4, "t_servidor_ms") * 100
    frac_gpu = m(s4, "t_gpu_total_ms") / m(s4, "t_servidor_ms") * 100
    kernel_min = min(float(f["t_kernel_ms"]) for v in d.filas.values() for f in v
                     if f["ancho"] == "4000" and f["filtro"] == "media" and f["mascara"] == "9")
    est_4000 = [f for v in d.filas.values() for f in v if f["ancho"] == "4000"
                and f["filtro"] == "media" and f["mascara"] == "9"
                and f["experimento"] != "arranque_frio"]
    rapidas = sum(float(f["t_kernel_ms"]) <= kernel_min * 1.2 for f in est_4000)
    h2d_rap = [float(f["t_h2d_ms"]) for f in est_4000 if float(f["t_kernel_ms"]) <= kernel_min * 1.2]
    h2d_len = [float(f["t_h2d_ms"]) for f in est_4000 if float(f["t_kernel_ms"]) > kernel_min * 1.2]
    lentos = [float(f["t_kernel_ms"]) for f in est_4000 if float(f["t_kernel_ms"]) > kernel_min * 1.2]
    cont_rep = d.crudas("directo_contenedor", "integracion")
    _, frio_anf = d.frio("directo_anfitrion")
    _, frio_cont = d.frio("directo_contenedor")
    fila_frio_srv, frio_srv = d.frio("servicio")
    espera2 = [float(f["t_espera_ms"]) for f in d.crudas("servicio", "concurrencia", concurrencia=2)]
    rps1, rps2 = m(conc[0], "rendimiento_rps"), m(conc[1], "rendimiento_rps")
    err_bordes = max(float(f["error_max"]) for f in d.bordes)
    sha = {lado: next(f["sha256_entrada"] for f in d.filas["servicio"] if int(f["ancho"]) == lado)
           for lado in (2000, 4000, 6000)}
    sha_nm = sha_archivo(DATOS_P02 / "no_multiplo_1013x757.pgm")
    mem = {lado: m(d.r("resolucion", lado=lado), "memoria_reservada_mb") for lado in (2000, 4000, 6000)}
    mem_uso = [float(f["memoria_gpu_usada_mb"]) for v in d.filas.values() for f in v
               if f["memoria_gpu_usada_mb"]]

    # --- Objetivo ---------------------------------------------------------------
    b = marco.fila()
    b.p("**OBJETIVO ALCANZADO:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Integrar el kernel de convolución propio de la práctica 02 (PyCUDA) en una aplicación "
        "web en Python, con interfaz y servicio HTTP, gestión de solicitudes y errores controlados.",
        "Construir una imagen Docker reproducible y desplegar el servicio con acceso a una GPU NVIDIA, "
        "demostrando su uso desde otro equipo.",
        "Validar la equivalencia numérica entre ejecución directa y servicio, y analizar con "
        "mediciones reproducibles cómo se distribuye el tiempo entre GPU, preparación, servicio y "
        "comunicación."])
    marco.fila("ACTIVIDADES DESARROLLADAS")

    # --- 1 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("1. Revisar la solución de la práctica 02 y definir la arquitectura web.")
    b.p(f"Repositorio de la práctica 03: {URL_REPOSITORIO}")
    b.p(f"**Commit de origen de la práctica 02:** `{d.commit_p02}`, en el repositorio de la "
        f"práctica 02 ({URL_REPOSITORIO_P02}). Su carpeta `GuillenJ_SolanoA_Practica0/` se incluye "
        "en este repositorio como versión ejecutable directamente para establecer la referencia"
        + (" y es idéntica a la de ese commit (comprobado con `git diff`)." if p02_identica else "."))
    b.p(f"**Commit de la práctica 03 medido:** `{d.commit_p03}`. Las mediciones, la imagen Docker "
        f"(`{an['software']['imagen_docker_p03'].split(' | ')[0][:19]}…`, etiqueta "
        "`org.opencontainers.image.revision` con ese commit) y el árbol de trabajo limpio se "
        "registraron en `resultados/mediciones/entorno_*_final.json`.")
    if posteriores:
        b.p("Commits posteriores a la medición (solo resultados, documentación e interfaz): "
            + "; ".join(f"`{c.split(' ', 1)[0]}`" for c in posteriores) + ". Archivos de código "
            "modificados después de medir: " + (", ".join(f"`{Path(c).name}`" for c in cambiados)
                                               or "ninguno") + ". Ninguno altera el "
            "procesamiento, la API ni el kernel.")
    b.subtitulo("Qué se reutilizó y qué es nuevo")
    b.tabla(["Elemento", "Práctica 02 (reutilizado sin cambios)", "Práctica 03 (nuevo)"], [
        ["Kernel", "`convolucionGPU` en `src/pycuda/kernels/convolucion.cu`: un píxel por hilo, "
                   "bloques e hilos en X, extensión con ceros, float32", "Se carga desde el contenedor; no se copia ni se modifica"],
        ["Contexto y ejecución", "`contexto_cuda.py` (contexto manual, `SourceModule -O3 sm_86`) y "
                                 "`convolucion.py` (mem_alloc, memcpy, eventos)", "`procesador_gpu.py`: un trabajador CUDA, cola acotada, errores y reinicio de contexto"],
        ["Filtros", "Media 3/9/21 (1/k² en float32), nitidez y laplaciano 3×3", "Validación de parámetros en `filtros.py`"],
        ["Datos", "base_2000/4000/6000 y no_multiplo_1013x757 (PGM)", "Cualquier PNG/JPG/BMP/PGM/PPM; preparación automática si supera 6000²"],
        ["Programa", "Scripts de línea de comandos", "Flask + Gunicorn, interfaz web, Docker, despliegue y mediciones de servicio"],
    ], [72, 214, 214], alinear=["l", "l", "l"], tam=8)
    b.subtitulo("Equipo y herramientas utilizados")
    b.tabla(["Componente", "Detalle (de entorno_anfitrion_final.json y entorno_contenedor_final.json)"], [
        ["Ubicación", an["equipo"]["ubicacion"]],
        ["CPU y RAM", f"{an['equipo']['cpu']}, {an['equipo']['nucleos_logicos']} hilos; RAM "
                      f"{n(an['equipo']['ram_total_gib'], 1)} GiB (el contenedor ve "
                      f"{n(co['equipo']['ram_total_gib'], 2)} GiB de la VM de WSL2)"],
        ["GPU", f"{an['gpu']['nvidia_smi'].split(',')[0]}, {an['gpu']['nvidia_smi'].split(',')[1].strip()}, "
                f"capacidad de cómputo {an['gpu']['nvidia_smi'].split(',')[3].strip()} (sm_86)"],
        ["Controlador (anfitrión)", f"NVIDIA {an['gpu']['nvidia_smi'].split(',')[2].strip()}, admite "
                                    f"hasta CUDA {an['gpu']['cuda_maxima_controlador']}"],
        ["Sistema operativo", f"Anfitrión {an['equipo']['sistema']}; contenedor {co['equipo']['sistema']}"],
        ["Docker y runtime GPU", an["software"]["docker_servidor"].replace("|", "·")],
        ["Imagen", "nvidia/cuda:12.9.1-devel-ubuntu24.04: CUDA Toolkit 12.9 (nvcc V12.9.86), "
                   f"Python {co['equipo']['python']}"],
        ["Paquetes", ", ".join(f"{k} {v}" for k, v in co["software"]["paquetes"].items())],
        ["Red", f"IP {', '.join(an['red']['direcciones_ip'])}; puerto {an['red']['puerto_publicado_anfitrion']} "
                f"(anfitrión) → {an['red']['puerto_contenedor']} (contenedor)"],
    ], [110, 390], alinear=["l", "l"], tam=8)
    b.subtitulo("Arquitectura")
    b.figura(arquitectura, 6.6, "Figura 1. Arquitectura: navegador → servicio web Python → PyCUDA "
                                "→ GPU → resultado → navegador. Todo el procesamiento ocurre dentro del contenedor.")
    b.vinetas([
        "**Un proceso de Gunicorn** con 4 hilos HTTP: un solo proceso implica un solo contexto CUDA "
        "(varios procesos crearían contextos duplicados que compiten por la GPU).",
        "**Un trabajador CUDA** (hilo único) crea el contexto, compila o carga el kernel y ejecuta todas "
        "las llamadas CUDA; los hilos HTTP solo reciben, decodifican y codifican.",
        "**Cola acotada a 2** (uno en ejecución y uno en espera); la tercera solicitud simultánea "
        "recibe HTTP 429 de inmediato. Sin GPU, el servicio responde 503 y nunca calcula en CPU.",
        "**El mismo procesamiento** (`webapp/procesamiento.py`) se usa desde el servicio, desde la "
        "ejecución directa y desde la validación, de modo que se compara exactamente lo mismo."])
    b.subtitulo("Imágenes de entrada")
    b.tabla(["Imagen", "Uso", "SHA-256"], [
        ["base_2000.pgm", "Resolución", f"`{sha[2000]}`"],
        ["base_4000.pgm", "Integración, filtros, máscara, concurrencia", f"`{sha[4000]}`"],
        ["base_6000.pgm", "Resolución, límite de cola", f"`{sha[6000]}`"],
        ["no_multiplo_1013x757.pgm", "Bordes, cobertura y equivalencia", f"`{sha_nm}`"],
    ], [96, 120, 284], alinear=["l", "l", "l"], tam=7.5)
    b.p("Son los mismos archivos de las prácticas 01 y 02, versionados en "
        "`GuillenJ_SolanoA_Practica0/datos/` (con `hashes_p01.json`); cada fila de los CSV registra el "
        "SHA-256 del archivo enviado.", tam=10)

    # --- 2 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("2. Implementar la interfaz, el servicio y la gestión de solicitudes GPU.")
    b.p("La interfaz (`webapp/static/`) permite elegir o arrastrar una imagen, seleccionar el filtro y, "
        "para media, la máscara 3×3, 9×9 o 21×21 (nitidez y laplaciano quedan fijos en 3×3). Muestra "
        "la original, la entrada preparada (si se recortó o redujo) y el resultado, permite descargarlo "
        "y presenta los tiempos con unidades y alcance. El botón se deshabilita mientras se procesa para "
        "evitar envíos duplicados, y los errores se muestran con su código HTTP. Arriba se informa el "
        "equipo que procesa (GPU, CPU, RAM, versiones), obtenido de `GET /api/equipo`.")
    b.subtitulo("Contrato HTTP")
    b.tabla(["Ruta", "Entrada", "Respuesta correcta"], [
        ["`POST /api/convoluciones`", "multipart: `imagen` (archivo), `filtro` (media | nitidez | "
                                      "laplaciano), `mascara` (3 | 9 | 21; 3 para nitidez y laplaciano)",
         "201 JSON: `id_solicitud` (UUID), dimensiones, preparación, URL del PNG y del NPY float32, "
         "bloques, hilos, memoria y `tiempos_ms` por fase"],
        ["`GET /api/resultados/{uuid}/{archivo}`", "`original.png`, `resultado.png` o `resultado.npy`",
         "200 con el archivo; 404 si el UUID o el nombre no son válidos"],
        ["`GET /api/salud`", "—", "200 con GPU, compute capability y política; 503 si no hay GPU"],
        ["`GET /api/equipo`", "—", "200 con CPU, RAM, sistema, GPU, versiones y límites"],
    ], [118, 176, 206], alinear=["l", "l", "l"], tam=8)
    b.tabla(["HTTP", "`codigo`", "Causa"], [
        ["400", "entrada_invalida", "No es imagen, formato no admitido, dimensiones fuera de límite, filtro o máscara no permitidos"],
        ["413", "archivo_demasiado_grande", "Cuerpo mayor que 64 MiB"],
        ["429", "cola_llena", "Ya hay una solicitud en ejecución y otra en espera"],
        ["503", "gpu_no_disponible", "Sin libcuda/controlador/GPU, o fallo al crear el contexto o compilar el kernel"],
        ["503", "memoria_gpu_insuficiente / memoria_servidor_insuficiente", "`cuda.mem_alloc` o la decodificación no obtienen memoria"],
        ["500", "error_procesamiento_gpu", "Fallo de transferencia, kernel o sincronización (el contexto se recrea)"],
    ], [34, 150, 316], alinear=["c", "l", "l"], tam=8, negrita_col0=False)
    b.subtitulo("Validación, límites y aislamiento")
    b.vinetas([
        "Se valida el **formato real** con Pillow (`verify`), no la extensión: PNG, JPEG, BMP, PGM y PPM.",
        "Límites: 64 MiB por archivo (base_6000.pgm ocupa 36 MB), 170 millones de píxeles de entrada y "
        f"36 millones procesados (6000²). Una imagen de 6000² reserva {n(mem[6000], 1)} MiB en la GPU "
        "(entrada y salida float32 más la máscara), muy por debajo de los 8 GiB de la RTX 3070, y "
        "permite dos solicitudes en memoria del servidor a la vez. Las entradas mayores se recortan al "
        "cuadrado central y se reducen con Lanczos a 6000², como en las prácticas anteriores.",
        "Cada solicitud recibe un **UUID** y una carpeta propia (`original.png`, `resultado.png`, "
        "`resultado.npy`); las rutas de descarga solo aceptan UUID válidos y esos tres nombres. Las "
        "carpetas se eliminan si la solicitud falla y expiran a las 24 h.",
    ])
    b.subtitulo("Integración con PyCUDA")
    b.tabla(["Aspecto", "Cómo se gestiona"], [
        ["Contexto", "`cuda.init()` + `Device(0).make_context()` manual (sin `pycuda.autoinit`), en el hilo "
                     "del trabajador CUDA, la primera vez que llega una solicitud. Se libera en ese mismo hilo al cerrar."],
        ["Kernel", "`SourceModule` con `-O3` y `arch=sm_86`, con caché de PyCUDA; el tiempo de "
                   "importación, contexto y compilación/carga se informa aparte (`inicio_frio`)."],
        ["Memoria", "`cuda.mem_alloc` de entrada, salida y máscara por solicitud; `free` en `finally`. "
                    "Se mide aparte (`reserva_liberacion`) y no forma parte de `gpu_total`."],
        ["Transferencias", "`memcpy_htod` y `memcpy_dtoh` síncronas desde **memoria paginable** de NumPy "
                           "(arreglos float32 contiguos; escalares `np.int32`)."],
        ["Sincronización", "Eventos `e0→H2D→e1→kernel→e2→D2H→e3` y `e3.synchronize()` antes de leer."],
        ["Errores", "Sin GPU → 503 con diagnóstico; sin memoria → 503; fallo del kernel → 500 y el "
                    "contexto se descarta y se recrea en la siguiente solicitud."],
    ], [80, 420], alinear=["l", "l"], tam=8)
    b.codigo([
        "# webapp/procesador_gpu.py (extracto) - se ejecuta en el único hilo CUDA",
        "if not self._inicio_frio_registrado:",
        "    inicializar()                    # contexto + SourceModule (P02)",
        "punteros = reservar(n, k)           # cuda.mem_alloc x3",
        "try:",
        "    tiempos = ejecutar(entrada, salida, mascara, *punteros, ancho, alto, k, hilos)",
        "except Exception:",
        "    self._reiniciar_contexto(); raise ErrorProcesamientoGPU(...)",
        "liberar(*punteros)                  # free"])

    # --- 3 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("3. Construir el contenedor, verificar el acceso a GPU y desplegar.")
    b.p("El **controlador NVIDIA pertenece al anfitrión**; la imagen aporta CUDA Toolkit 12.9.1 "
        "(`nvcc`, necesario porque PyCUDA compila el kernel en tiempo de ejecución), Ubuntu 24.04, "
        "Python 3.12 y las dependencias con versión fija de `requirements.txt`. Docker Desktop (WSL2) "
        "expone la GPU mediante el runtime `nvidia` (NVIDIA Container Toolkit) con `--gpus all`. El "
        f"controlador {an['gpu']['nvidia_smi'].split(',')[2].strip()} admite hasta CUDA "
        f"{an['gpu']['cuda_maxima_controlador']}, compatible con el toolkit 12.9 de la imagen.")
    b.codigo([
        "# Dockerfile (extracto)",
        "FROM nvidia/cuda:12.9.1-devel-ubuntu24.04",
        "RUN apt-get install -y python3 python3-pip python3-dev build-essential",
        "RUN pip install -r requirements.txt        # versiones fijas",
        "COPY . .",
        "COPY --from=practica02 src /opt/practica02/src     # kernel y PyCUDA de P02",
        "COPY --from=practica02 datos /opt/practica02/datos",
        "ARG COMMIT_PRACTICA03  ->  LABEL org.opencontainers.image.revision",
        'CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","1","--threads","4",...,"servidor:app"]'])
    b.p("Comandos exactos (desde `GuillenJ_SolanoA_Practica03/`):", tam=10)
    b.codigo([
        "$env:COMMIT_PRACTICA03 = git -C .. rev-parse HEAD",
        "docker compose build                              # construir",
        "docker compose up -d                              # iniciar (puerto 8080 -> 8000)",
        "docker compose exec convolucion nvidia-smi        # comprobar GPU",
        "Invoke-RestMethod http://127.0.0.1:8080/api/salud",
        ".\\ejecutar_experimentos.ps1                     # validar y medir (árbol limpio)",
        "docker compose down                               # detener"])
    b.p("El servidor es Gunicorn, sin depurador ni recarga automática. La corrida final verificó "
        "además la construcción **desde una copia limpia** del repositorio (`git clone` del commit "
        f"medido): imagen `{d.copia['id_imagen'][:19]}…`, etiqueta de revisión "
        f"`{d.copia['revision_etiqueta'][:12]}`, resultado **{d.copia['resultado']}** "
        "(`resultados/evidencia/copia_limpia.json`).")
    b.subtitulo("Evidencia del contenedor y de la GPU")
    b.codigo([linea for linea in (EVI / "nvidia_smi_contenedor.txt").read_text(
        encoding="utf-8-sig").splitlines() if linea.strip()][:12])
    b.p("`docker compose ps`: " + (EVI / "contenedor_en_ejecucion.txt").read_text(
        encoding="utf-8-sig").splitlines()[-1].split("  ")[0] + " — estado **healthy**, "
        "`0.0.0.0:8080->8000/tcp`. `GET /api/salud` respondió `listo` con "
        f"{d.salud['gpu']['gpu']} (compute {d.salud['gpu']['compute_capability']}).", tam=9.5)
    sg = d.sin_gpu
    b.p(f"**Sin GPU:** la misma imagen iniciada sin `--gpus` respondió HTTP {sg['salud']['http']} en "
        f"`/api/salud` y HTTP {sg['convolucion']['http']} (`{sg['convolucion']['cuerpo']['codigo']}`) "
        f"en la convolución, con el diagnóstico «{sg['convolucion']['cuerpo']['error'][:150]}»; no "
        "devolvió ningún resultado calculado en CPU (`resultados/evidencia/sin_gpu.json`).", tam=10)
    b.subtitulo("Despliegue y acceso desde otro equipo")
    b.p("No se contó con una instancia de nube con GPU NVIDIA, por lo que se usó la alternativa "
        "prevista por la guía: un **servidor local** con GPU compatible (el equipo descrito en la "
        f"actividad 1, IP {an['red']['direcciones_ip'][0]}, puerto "
        f"{an['red']['puerto_publicado_anfitrion']}). Para la demostración desde otro equipo se "
        "expuso temporalmente el servicio con **Cloudflare Tunnel** (Quick Tunnel), que no requiere "
        "abrir puertos de entrada:")
    b.codigo(["cloudflared tunnel --url http://localhost:8080",
              f"# URL temporal asignada: {URL_TUNEL}"])
    b.p("Desde otro PC, en otra red, se abrió esa URL y se procesó una fotografía de 6480×7632 con "
        "laplaciano 3×3: el servicio la recortó y redujo a 6000×6000, la procesó en la RTX 3070 y "
        "devolvió el resultado (Figuras 2 a 4). El túnel se cerró al terminar la demostración; no hay "
        "recursos de pago. En las capturas el campo «Commit» indica `no_declarado` porque para la "
        "demostración el contenedor se construyó sin la variable `COMMIT_PRACTICA03`.")
    for indice, (nombre, pie) in enumerate((
            ("imagen1.jpeg", "Figura 2. Interfaz abierta desde otro PC mediante el túnel "
                             "(*.trycloudflare.com): equipo de procesamiento y GPU disponible."),
            ("imagen2.jpeg", "Figura 3. Resultado: original, entrada preparada (6000×6000) y "
                             "laplaciano 3×3, con tiempos del cliente, servidor y GPU."),
            ("imagen3.jpeg", "Figura 4. Desglose por fase de esa solicitud: recepción, "
                             "decodificación, reserva, H2D, kernel, D2H, codificación y cliente."))):
        ruta = CAPTURAS / nombre
        if ruta.exists():
            b.figura(ruta, 6.3, pie)
    b.p(f"Además, la corrida final envió una solicitud desde un **contenedor cliente separado** "
        f"(`{d.cliente['hostname_cliente']}`, sin GPU) a `{d.cliente['url_servicio']}`: HTTP "
        f"{d.cliente['http']}, resultado {d.cliente['resultado']} "
        "(`resultados/evidencia/cliente_distinto.json`).", tam=10)

    # --- 4 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("4. Validar los resultados.")
    b.p("Todas las validaciones se ejecutan contra el servicio en el contenedor "
        "(`scripts/validar_servicio.py`) y comparan el arreglo float32 **antes del recorte** "
        "(`resultado.npy`).")
    b.subtitulo("Tolerancia")
    b.p("Se usa 1e-2, como en las prácticas anteriores. Cada píxel suma hasta k² productos en float32; "
        "la cota de error de una suma de n términos es n·u·Σ|x·h|, con u = 2⁻²⁴ ≈ 5,96e-8. En el peor "
        "caso, media 21×21 (n = 441, Σ|x·h| ≤ 255) da 441·5,96e-8·255 ≈ 6,7e-3; nitidez (Σ|h| = 9) y "
        "laplaciano (Σ|h| = 8) dan ≈ 1,2e-3 y 1,1e-3. Por tanto 1e-2 acota el redondeo de float32 "
        "(incluida la contracción FMA de la GPU) y cualquier diferencia mayor indicaría un error real.")
    b.subtitulo("Matriz pequeña (5×5 de la práctica 02)")
    b.tabla(["Filtro", "Fila", "Col.", "Esperado", "Obtenido (servicio)", "Error", "Resultado"],
            [[f["filtro"], f["fila"], f["columna"], f["esperado"], f["obtenido"],
              e(float(f["error"])), f["resultado"]] for f in d.manual],
            [80, 40, 40, 80, 100, 80, 80], tam=8)
    b.subtitulo("Bordes y cobertura (1013×757, n no múltiplo de 256)")
    nb = d.bordes[0]
    b.p(f"n = {n(int(nb['pixeles']), 0)} píxeles, {n(int(nb['bloques']), 0)} bloques de "
        f"{nb['hilos_bloque']} hilos: sobran {nb['hilos_sobrantes']} hilos en el último bloque. Se "
        "compara la salida del servicio con una referencia en CPU float32 (mismo orden de suma y "
        "extensión con ceros) en la imagen completa, en la primera y última fila y columna, y en los "
        "píxeles del último bloque. Que los 766.841 valores sean finitos y coincidan comprueba que cada "
        "píxel fue escrito exactamente una vez.", tam=10)
    filas_b = []
    for f in d.bordes:
        if f["region"] == "imagen_completa":
            fila = [f"{f['filtro']} {f['mascara']}×{f['mascara']}", f["pixeles_finitos"]]
        regiones = {g["region"]: g for g in d.bordes if g["filtro"] == f["filtro"]
                    and g["mascara"] == f["mascara"]}
        if f["region"] == "imagen_completa":
            filas_b.append(fila + [e(float(regiones[r]["error_max"])) for r in
                                   ("imagen_completa", "bordes", "ultimo_bloque")]
                           + ["OK" if all(g["resultado"] == "OK" for g in regiones.values())
                              else "FALLA"])
    b.tabla(["Filtro", "Píxeles finitos", "Error máx. completa", "Error máx. bordes",
             "Error máx. último bloque", "Resultado"], filas_b, [90, 80, 85, 80, 90, 75], tam=8)
    b.subtitulo("Equivalencia directo–servicio")
    b.tabla(["Filtro", "Imagen", "Error máximo", "Error medio", "Tolerancia", "Resultado"],
            [[f"{f['filtro']} {f['mascara']}×{f['mascara']}", f"{f['ancho']}×{f['alto']}",
              e(float(f["error_max"])), e(float(f["error_medio"])), f["tolerancia"], f["resultado"]]
             for f in d.equivalencia], [90, 80, 85, 85, 80, 80], tam=8)
    b.p("PyCUDA directo (la misma función `procesar_imagen` sin HTTP) y el servicio dan resultados "
        "**idénticos bit a bit**: mismo kernel, mismos datos y misma configuración. Las únicas "
        "diferencias de cálculo aparecen frente a la referencia en CPU (máximo "
        f"{e(err_bordes)}), por el redondeo de float32. Las diferencias de la **codificación** son "
        "otras: el PNG visible recorta a 0–255, redondea a 8 bits y, en el laplaciano, guarda "
        "|v|·4; por eso la validación usa el NPY y nunca el PNG. Si la entrada es JPEG, su "
        "decodificación con Pillow forma parte de la entrada, no del cálculo.", tam=10)
    b.subtitulo("Resultado visual")
    visual = EVI / "visual"
    b.rejilla_imagenes([(visual / f"{nombre}.png", pie) for nombre, pie in (
        ("original", "Original 1013×757"), ("media", "Media 3×3"), ("nitidez", "Nitidez 3×3"),
        ("laplaciano", "Laplaciano 3×3 (|v|·4)"))], 4, 1.55)
    b.rejilla_imagenes([(visual / f"{nombre}_recorte.png", pie) for nombre, pie in (
        ("original", "Recorte central"), ("media", "Recorte media"),
        ("nitidez", "Recorte nitidez"), ("laplaciano", "Recorte laplaciano"))], 4, 1.55)
    b.pie("Figura 5. Salidas del servicio para los tres filtros y el mismo recorte central (600×600).")
    b.subtitulo("Entradas inválidas, aislamiento y cola")
    b.tabla(["Caso", "HTTP esperado", "HTTP obtenido", "Mensaje", "Resultado"],
            [[f["caso"], f["http_esperado"], f["http_obtenido"], f["mensaje"], f["resultado"]]
             for f in d.invalidas], [100, 50, 50, 240, 60], alinear=["l", "c", "c", "l", "c"], tam=8)
    b.p("Después de cada error el servicio siguió atendiendo: las solicitudes siguientes de la misma "
        "corrida terminaron con HTTP 201.", tam=10)
    b.tabla(["Cliente", "HTTP", "UUID", "URL del resultado", "Aislamiento"],
            [[f["cliente"], f["http"], f["id_solicitud"][:8] + "…", f["resultado_url"][:52] + "…",
              f["aislamiento"]] for f in d.aislamiento], [50, 40, 70, 280, 60],
            alinear=["c", "c", "l", "l", "c"], tam=8)
    rondas_cola = sorted({int(f["ronda"]) for f in d.cola})
    ultima = [f for f in d.cola if int(f["ronda"]) == rondas_cola[-1]]
    acept, rech = ultima[0]["aceptadas"], ultima[0]["rechazadas_429"]
    previas = len(rondas_cola) - 1
    b.p(f"Dos solicitudes simultáneas (media y laplaciano) recibieron UUID y archivos distintos, y "
        f"cada una su propio resultado. Para el límite de cola se enviaron ráfagas de cuatro "
        f"solicitudes simultáneas de 6000² con media 21×21. El cupo se toma después de recibir y "
        f"decodificar la imagen, así que el límite solo se alcanza si tres solicitudes coinciden en "
        f"la fase de GPU. "
        + (f"En {previas} ráfaga(s) previa(s) las solicitudes no llegaron a coincidir y las cuatro "
           f"se atendieron con HTTP 201. " if previas else "")
        + f"En la ráfaga {rondas_cola[-1]}, {acept} fueron aceptadas y {rech} recibieron HTTP 429 "
        "«La GPU tiene el máximo de solicitudes pendientes». Todas las rondas están en "
        "`cola_solicitudes.csv`.", tam=10)

    # --- 5 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("5. Ejecutar los experimentos y medir el rendimiento.")
    b.tabla(["Medida", "Método y alcance"], [
        ["H2D, kernel, D2H, GPU total", "Eventos CUDA y `synchronize()`; transferencias síncronas desde memoria paginable."],
        ["Decodificación, reserva, codificación, servidor", "`time.perf_counter` (monotónico) en el servidor. Codificación incluye escribir `original.png`, `resultado.png` y `resultado.npy`. La reserva/liberación está fuera de GPU total y dentro del servidor."],
        ["Espera", "Desde que el trabajo entra a la cola hasta que el trabajador CUDA lo toma."],
        ["Cliente", "`perf_counter` del cliente desde el envío hasta descargar completo el PNG final (incluye comunicación). Cliente: script Python en el mismo anfitrión, vía http://127.0.0.1:8080 (red local del equipo, sin Internet)."],
        ["Rendimiento", "Solicitudes exitosas / intervalo total de la ronda en el cliente."],
        ["Arranque en frío", "Primera solicitud de cada proceso: importación, contexto CUDA y compilación/carga del kernel; se registra aparte y se excluye de las medianas."],
    ], [130, 370], alinear=["l", "l"], tam=8)
    b.p(f"Se hizo calentamiento y 5 repeticiones por configuración; en concurrencia, 5 rondas por "
        f"nivel registrando cada solicitud. Se modificó un factor a la vez con 256 hilos por bloque, la "
        f"misma GPU y los mismos archivos. Las {d.total_filas()} filas de medición terminaron "
        f"({d.completadas()} completadas, ninguna incompleta ni rechazada). Los relojes del cliente y "
        "del servidor nunca se restan. Se reportan medianas y el rango intercuartílico (Q1–Q3).", tam=10)
    b.subtitulo("Integración y contenedor (media 9×9, 4000×4000) — medianas en ms")
    tabla_fases(b, d, integ, ["Directo · anfitrión", "Directo · contenedor", "Servicio"])
    tabla_variabilidad(b, d, integ, ["Directo · anfitrión", "Directo · contenedor", "Servicio"])
    b.figura(GRA / "distribucion_integracion.png", 6.3,
             "Figura 6. Distribución del tiempo por fase (barra izquierda) y tiempo del cliente "
             "(barra derecha, otro reloj).")
    b.subtitulo("Resolución (servicio, media 9×9) — medianas en ms")
    tabla_fases(b, d, reso, ["2000×2000", "4000×4000", "6000×6000"])
    tabla_variabilidad(b, d, reso, ["2000×2000", "4000×4000", "6000×6000"])
    b.figura(GRA / "distribucion_resolucion.png", 6.3,
             "Figura 7. Distribución del tiempo del servicio según la resolución.")
    b.subtitulo("Filtros y máscara (servicio, 4000×4000) — medianas en ms")
    etiquetas_f = ["Media 3×3", "Media 9×9", "Media 21×21", "Nitidez 3×3", "Laplaciano 3×3"]
    tabla_fases(b, d, filt, etiquetas_f)
    tabla_variabilidad(b, d, filt, etiquetas_f)
    b.figura(GRA / "filtros_kernel.png", 5.8,
             "Figura 8. Tiempo de kernel por filtro y máscara (mediana y Q1–Q3).")
    b.subtitulo("Solicitudes concurrentes (servicio, media 9×9, 4000×4000)")
    b.tabla(["Clientes", "Solicitudes", "Latencia cliente (Q1–Q3)", "Espera en cola (Q1–Q3)",
             "Servidor", "Rendimiento (Q1–Q3)", "Rechazos/fallos"],
            [[str(c), r_["repeticiones"],
              f"{ms(m(r_, 't_cliente_ms'), 0)} ({d.rango(r_, 't_cliente_ms', 0)})",
              f"{ms(m(r_, 't_espera_ms'), 2)} ({d.rango(r_, 't_espera_ms', 2)})",
              ms(m(r_, "t_servidor_ms"), 0),
              f"{n(m(r_, 'rendimiento_rps'), 3)} ({d.rango(r_, 'rendimiento_rps', 3)}) sol/s", "0"]
             for c, r_ in zip((1, 2), conc)], [44, 54, 92, 92, 50, 110, 58], tam=8)
    b.figura(GRA / "concurrencia_rendimiento.png", 5.4,
             "Figura 9. Solicitudes exitosas por segundo con uno y dos clientes (por ronda).")
    b.subtitulo("Arranque en frío y memoria")
    b.tabla(["Modo", "Arranque (importación + contexto + kernel)", "Procesamiento de esa solicitud"],
            [["Directo · anfitrión (4000²)", f"{n(frio_anf, 1)} ms", f"{n(float(d.frio('directo_anfitrion')[0]['t_servidor_ms']), 1)} ms"],
             ["Directo · contenedor (4000²)", f"{n(frio_cont, 1)} ms", f"{n(float(d.frio('directo_contenedor')[0]['t_servidor_ms']), 1)} ms"],
             ["Servicio (2000², primera solicitud)", f"{n(frio_srv, 1)} ms", f"{n(float(fila_frio_srv['t_servidor_ms']), 1)} ms (estable: {n(m(reso[0], 't_servidor_ms'), 1)} ms)"]],
            [150, 170, 180], alinear=["l", "r", "r"], tam=8)
    b.tabla(["Resolución", "Memoria GPU reservada por solicitud", "Memoria GPU en uso tras reservar (dispositivo)"],
            [[f"{lado}×{lado}", f"{n(mem[lado], 1)} MiB",
              f"{n(m(d.r('resolucion', lado=lado), 'memoria_gpu_usada_mb'), 0)} MiB de 8.192 MiB"]
             for lado in (2000, 4000, 6000)], [100, 190, 210], alinear=["l", "r", "r"], tam=8)

    # --- 6 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("6. Analizar los resultados.")
    b.subtitulo("¿Qué se reutilizó de la práctica 02 y qué cambió al convertirlo en servicio?")
    b.p("Se reutilizaron sin cambios el kernel, el contexto y la ejecución PyCUDA, las máscaras, la "
        "precisión float32, la extensión con ceros y el tratamiento visual. Cambió el programa "
        "anfitrión: ahora recibe archivos arbitrarios por HTTP, los valida y prepara, serializa el "
        "acceso a la GPU en un único trabajador, aísla los resultados por UUID, controla errores y se "
        "ejecuta en un contenedor con la GPU del anfitrión.")
    b.subtitulo("¿Se mantiene la equivalencia numérica?")
    b.p(f"Sí. El servicio coincide bit a bit con PyCUDA directo (error 0 en los tres filtros) y con "
        f"la referencia en CPU difiere como máximo {e(err_bordes)}, muy por debajo de la cota de float32. "
        "Las diferencias que sí aparecen en el PNG se deben a la codificación (recorte, 8 bits y "
        "|v|·4 en el laplaciano), no al cálculo.")
    b.subtitulo("¿Cómo se distribuye el tiempo entre GPU, preparación, servicio y comunicación?")
    b.p(f"En el servicio con 4000² y media 9×9, la codificación y escritura de los resultados ocupa "
        f"{pct(frac_codif, 0)} del tiempo del servidor ({ms(m(s4, 't_codificacion_ms'), 0)} de "
        f"{ms(m(s4, 't_servidor_ms'), 0)} ms), mientras que todo el trabajo en GPU (H2D + kernel + D2H) "
        f"es {pct(frac_gpu, 1)} y la decodificación {ms(m(s4, 't_decodificacion_ms'), 0)} ms. El "
        f"cliente percibe {ms(m(s4, 't_cliente_ms'), 0)} ms, que incluyen además el envío de la imagen "
        "y la descarga del PNG; en local esa comunicación es pequeña. En la demostración por Internet "
        "(Figura 4, una sola solicitud) la recepción de una foto de 3,9 MiB tardó 721,6 ms y el cliente "
        "14,06 s frente a 7,62 s del servidor: ahí la red sí pesa. Dentro de la GPU, las copias por PCIe superan al "
        "kernel en todas las configuraciones salvo media 21×21.")
    b.subtitulo("¿Qué diferencias aparecen entre ejecución directa y servicio? ¿Se puede atribuir alguna a Docker?")
    b.p(f"El servicio añade la recepción HTTP y la espera en cola (≈0,1 ms con un cliente); el resto "
        f"de fases es el mismo código. La diferencia grande está en la escritura: "
        f"{ms(m(integ[0], 't_codificacion_ms'), 0)} ms en el anfitrión (Windows, NTFS) frente a "
        f"{ms(m(integ[1], 't_codificacion_ms'), 0)} ms en el contenedor (Linux en la VM de WSL2). En la "
        f"GPU las medianas varían mucho, pero los datos son **bimodales**: en {rapidas} de "
        f"{len(est_4000)} repeticiones estables de esta configuración el kernel tardó "
        f"≈{n(kernel_min, 2)} ms, y en el resto entre {n(min(lentos), 1)} y {n(max(lentos), 1)} ms, "
        f"casi siempre junto con copias H2D más "
        f"lentas (≈{n(sorted(h2d_rap)[len(h2d_rap) // 2], 0)} ms frente a "
        f"≈{n(sorted(h2d_len)[len(h2d_len) // 2], 0)} ms). La primera repetición directa en el "
        f"contenedor midió {n(float(cont_rep[0]['t_kernel_ms']), 2)} ms, igual que en el anfitrión. Esto "
        "apunta a la gestión de energía de la GPU (estado P8 en reposo, reloj y enlace PCIe reducidos "
        "entre solicitudes separadas por segundos de trabajo en CPU) y a que la GPU también maneja la "
        "pantalla. El diseño no permite atribuir estas diferencias a Docker: anfitrión y contenedor "
        "difieren también en sistema operativo, sistema de archivos y estado de la GPU.")
    b.subtitulo("¿Cómo afectan resolución, máscara y concurrencia a latencia, rendimiento y memoria?")
    b.p(f"La latencia crece casi en proporción a los píxeles: {ms(m(reso[0], 't_cliente_ms'), 0)}, "
        f"{ms(m(reso[1], 't_cliente_ms'), 0)} y {ms(m(reso[2], 't_cliente_ms'), 0)} ms para 2000², "
        f"4000² y 6000² (×4 y ×9 píxeles), arrastrada por la codificación. La memoria de GPU reservada "
        f"también es lineal: {n(mem[2000], 1)}, {n(mem[4000], 1)} y {n(mem[6000], 1)} MiB. La máscara "
        f"apenas cambia la memoria (21²·4 B) pero sí el kernel: {ms(m(filt[0], 't_kernel_ms'), 1)} ms "
        f"con 3×3 frente a {ms(m(filt[2], 't_kernel_ms'), 1)} ms con 21×21 (49 veces más operaciones). "
        f"Nitidez y laplaciano cuestan en GPU lo mismo que la media 3×3; su codificación difiere porque "
        f"el tamaño del PNG depende del contenido. Con dos clientes la latencia sube poco "
        f"({ms(m(conc[0], 't_cliente_ms'), 0)} → {ms(m(conc[1], 't_cliente_ms'), 0)} ms) y el "
        f"rendimiento casi se duplica ({n(rps1, 3)} → {n(rps2, 3)} sol/s): la parte en CPU se hace en "
        f"paralelo en los hilos de Gunicorn y solo la GPU se serializa; la segunda solicitud esperó "
        f"hasta {n(max(espera2), 0)} ms en la cola. La memoria de GPU no crece con la concurrencia "
        f"porque solo un trabajo tiene memoria reservada a la vez (en uso: {n(min(mem_uso), 0)}–"
        f"{n(max(mem_uso), 0)} MiB del dispositivo, incluida la pantalla).")
    b.subtitulo("¿Cómo condicionan el contexto CUDA, los trabajadores y la cola el comportamiento?")
    b.p(f"El contexto se crea una vez por proceso y la primera solicitud paga el arranque "
        f"({n(frio_srv, 0)} ms en el servicio; {n(frio_anf, 0)} y {n(frio_cont, 0)} ms en directo en "
        "anfitrión y contenedor). Con un único proceso y un único trabajador CUDA no hay "
        "contextos duplicados ni accesos concurrentes a la GPU; el costo es que las solicitudes se "
        "atienden en orden y la segunda espera a la primera. El límite de dos solicitudes evita "
        "acumular imágenes en memoria y responde 429 de inmediato en vez de dejar al cliente esperando.")
    b.subtitulo("¿Qué límites del equipo, la red o el procedimiento restringen las conclusiones?")
    b.vinetas([
        "Un solo equipo con GPU compartida con la pantalla y gestión de energía activa; los tiempos "
        "de GPU son bimodales y la mediana de 5 repeticiones depende de cuántas caen en cada modo.",
        "Docker Desktop sobre WSL2: el contenedor corre en una VM con su propio sistema de archivos y "
        "15,5 GiB de RAM, por lo que no se aísla el efecto de Docker.",
        "El cliente de las mediciones estuvo en el mismo equipo (sin red real); el acceso remoto por "
        "Cloudflare se demostró con una sola solicitud y no se midió de forma sistemática.",
        "No se midió la RAM del servidor por solicitud ni se usó memoria fijada (pinned).",
        "Alcanzar el límite de la cola depende de que tres solicitudes coincidan en la fase de GPU; "
        "por eso la prueba de saturación se repite por ráfagas y se registran todas."])

    # --- 7 ------------------------------------------------------------------------
    b = marco.fila()
    b.titulo("7. Documentar las contribuciones de los integrantes.")
    b.p("El trabajo se repartió de forma equitativa: cuatro actividades cada integrante. Ambos "
        "revisaron el resultado final y el informe.", alinear=WD_ALIGN_PARAGRAPH.LEFT)
    # (actividad, responsable): G = J. Guillén, S = A. Solano
    actividades = [("Revisión de la práctica 02 y arquitectura web", "G"),
                   ("Servicio HTTP, interfaz y gestión de solicitudes", "G"),
                   ("Integración con PyCUDA (contexto, memoria, errores)", "S"),
                   ("Dockerfile, Compose y acceso a GPU", "S"),
                   ("Despliegue y demostración (Cloudflare Tunnel)", "S"),
                   ("Validación funcional y numérica", "G"),
                   ("Experimentos, CSV y gráficas", "S"),
                   ("Informe, README y repositorio", "G")]
    b.tabla(["Actividad", "J. Guillén", "A. Solano"],
            [[a, "X" if q == "G" else "", "X" if q == "S" else ""] for a, q in actividades],
            [320, 90, 90], alinear=["l", "c", "c"], negrita_col0=False)

    # --- Cierre -------------------------------------------------------------------
    b = marco.fila()
    b.p("**RESULTADO(S) OBTENIDO(S):**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Servicio web con interfaz y API que procesa imágenes en la GPU con el kernel propio de la "
        "práctica 02, dentro de un contenedor Docker con acceso a la RTX 3070.",
        f"Equivalencia exacta entre PyCUDA directo y servicio; error máximo frente a CPU {e(err_bordes)}; "
        "bordes, cobertura, entradas inválidas, aislamiento y cola verificados.",
        f"{d.completadas()} mediciones completadas en cuatro experimentos; en el servicio la GPU "
        f"representa {pct(frac_gpu, 1)} del tiempo y la codificación {pct(frac_codif, 0)}.",
        f"Con dos clientes el rendimiento pasa de {n(rps1, 2)} a {n(rps2, 2)} solicitudes/s sin "
        "rechazos; la cola rechaza con 429 a partir de la tercera solicitud simultánea.",
        "Imagen reproducible desde una copia limpia, diagnóstico 503 sin GPU y demostración desde otro "
        "equipo mediante Cloudflare Tunnel."])
    b = marco.fila()
    b.p("**CONCLUSIONES:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Ofrecer la convolución como servicio no cambia el cálculo: el resultado es idéntico al de la "
        "ejecución directa. Lo que cambia es todo lo que rodea al kernel: recepción, validación, cola, "
        "codificación, almacenamiento y comunicación.",
        "En un servicio el kernel deja de ser el cuello de botella: preparar y codificar las imágenes "
        "cuesta decenas de veces más que la GPU, por lo que optimizar el kernel tendría poco efecto en "
        "la latencia percibida.",
        "Un único trabajador CUDA con cola acotada es una política simple y segura: evita contextos "
        "duplicados y la saturación de memoria, y aun así la concurrencia mejora el rendimiento porque "
        "la parte en CPU se solapa.",
        "Docker con NVIDIA Container Toolkit permite usar la GPU sin cambiar el código; las diferencias "
        "de tiempo observadas se explican mejor por el estado de energía de la GPU y por WSL2 que por "
        "Docker en sí, y el diseño experimental no permite separarlas."])
    b = marco.fila()
    b.p("**RECOMENDACIONES:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Fijar el estado de rendimiento de la GPU (o usar una GPU dedicada sin pantalla) y aumentar las "
        "repeticiones para reducir la bimodalidad de los tiempos de GPU.",
        "Escribir el NPY solo cuando se requiera validar y comprimir el PNG con menor nivel para "
        "reducir la latencia del servicio.",
        "Usar memoria fijada (pagelocked) en el anfitrión para acelerar y estabilizar las copias.",
        "Repetir las mediciones con un cliente en otro equipo de la red o en una instancia de nube con "
        "GPU para cuantificar la comunicación.",
        "Comenzar con entradas pequeñas, validar el acceso a GPU antes de integrar la web y medir con "
        "el árbol de trabajo limpio y el commit registrado."])
    b = marco.fila()
    b.p("**REFERENCIAS:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "NVIDIA. CUDA C++ Programming Guide (v12.9) y NVIDIA Container Toolkit documentation.",
        "A. Klöckner et al. PyCUDA documentation: Device Interface y pycuda.compiler.SourceModule.",
        "Pallets. Flask documentation (3.1); Gunicorn documentation (23.0): design and settings.",
        "Docker Inc. Docker documentation: GPU support, Compose, build contexts (BuildKit).",
        "Cloudflare. Cloudflare Tunnel: Quick Tunnels (TryCloudflare).",
        "N. J. Higham. Accuracy and Stability of Numerical Algorithms, 2.ª ed., SIAM, 2002.",
        "Guías de las prácticas 01, 02 y 03, Computación Paralela, UPS (G. A. León Paredes)."],
        alinear=WD_ALIGN_PARAGRAPH.LEFT)

    # --- Firmas -------------------------------------------------------------------
    par = doc.add_paragraph()
    formato_parrafo(par, 11, WD_ALIGN_PARAGRAPH.LEFT, 18, 6)
    for texto, negrita, cursiva in (("Nombre de estudiante", True, True),
                                    (": Juan Alberto Guillén / Ariel Solano", True, False)):
        run = par.add_run(texto)
        run.bold, run.italic = negrita, cursiva
    par = doc.add_paragraph()
    formato_parrafo(par, 11, WD_ALIGN_PARAGRAPH.LEFT, 6, 2)
    run = par.add_run("Firma de estudiante")
    run.bold = run.italic = True
    par.add_run(":").bold = True
    if firmas:
        par = doc.add_paragraph()
        formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.LEFT)
        for lado in ("izquierda", "derecha"):
            if lado in firmas:
                par.add_run().add_picture(io.BytesIO(firmas[lado]), height=Pt(95))
    return doc


def main():
    d = Datos()
    logo, firmas = recursos_guia()
    doc = construir(d, logo, firmas, figura_arquitectura())
    doc.core_properties.title = ("Práctica 03: Servicio web de convolución de imágenes con "
                                 "Docker y PyCUDA")
    doc.core_properties.author = "Juan Alberto Guillén; Ariel Solano"
    doc.save(SALIDA)
    print(f"Informe: {SALIDA}")


if __name__ == "__main__":
    main()
