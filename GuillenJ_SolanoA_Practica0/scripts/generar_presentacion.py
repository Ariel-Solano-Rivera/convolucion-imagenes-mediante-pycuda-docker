"""Genera la presentación de la práctica 02 con el formato de la presentación de P01.

Todas las cifras se calculan con scripts/informe_datos.py a partir de los CSV.
Salida: ../docs/presentacion/presentacion_practica02.pptx
Uso: .venv\\Scripts\\python.exe -m scripts.generar_presentacion
"""
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from scripts.informe_datos import (EXP_FILTROS, EXP_HILOS, EXP_MASCARA, EXP_RESOLUCION,
                                   RAIZ, Datos)

SALIDA = RAIZ.parent / "docs" / "presentacion" / "presentacion_practica02.pptx"
IMAGENES = RAIZ / "resultados" / "imagenes"
FUENTE = "Arial"
PIE = "Práctica 02 · Computación Paralela · UPS"

# Paleta de la presentación de P01
MARINO = RGBColor(0x1C, 0x29, 0x42)
MARINO_TARJETA = RGBColor(0x26, 0x34, 0x50)
MARINO_BORDE = RGBColor(0x3A, 0x46, 0x60)
CREMA = RGBColor(0xF3, 0xF0, 0xEA)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
BORDE = RGBColor(0xE1, 0xDF, 0xDC)
NARANJA = RGBColor(0xB5, 0x54, 0x1B)
NARANJA_CLARO = RGBColor(0xE8, 0x9F, 0x5E)
NARANJA_SUAVE = RGBColor(0xF5, 0xD9, 0xC4)
TEXTO = RGBColor(0x22, 0x26, 0x2E)
GRIS = RGBColor(0x5F, 0x66, 0x73)
GRIS_CLARO = RGBColor(0xC9, 0xCE, 0xD8)
GRIS_AZUL = RGBColor(0x8C, 0x96, 0xA8)
GRIS_AZUL_CLARO = RGBColor(0xB7, 0xBF, 0xCC)
CREMA_TEXTO = RGBColor(0xF3, 0xF0, 0xEA)
GRIS_OSCURO_TEXTO = RGBColor(0xA9, 0xB1, 0xC0)
VERDE = RGBColor(0x2E, 0x7D, 0x4F)


def n(valor, dec=1):
    if round(valor, dec) == 0:
        valor = 0.0
    texto = f"{valor:,.{dec}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".").replace("-", "−")


# ---------------------------------------------------------------------------
# Ayudas de dibujo
# ---------------------------------------------------------------------------
def fondo(diapo, color):
    relleno = diapo.background.fill
    relleno.solid()
    relleno.fore_color.rgb = color


def texto(diapo, x, y, w, h, contenido, tam=14, color=TEXTO, negrita=False, alinear=PP_ALIGN.LEFT,
          vertical=MSO_ANCHOR.TOP, espacio=0, nombre=None):
    """contenido: str o lista de párrafos; cada párrafo es str o lista de (texto, opciones)."""
    caja = diapo.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if nombre:
        caja.name = nombre
    marco = caja.text_frame
    marco.word_wrap = True
    marco.margin_left = marco.margin_right = marco.margin_top = marco.margin_bottom = 0
    marco.vertical_anchor = vertical
    parrafos = contenido if isinstance(contenido, list) else [contenido]
    for i, parrafo in enumerate(parrafos):
        p = marco.paragraphs[0] if i == 0 else marco.add_paragraph()
        p.alignment = alinear
        if espacio and i:
            p.space_before = Pt(espacio)
        trozos = parrafo if isinstance(parrafo, list) else [(parrafo, {})]
        for trozo, opciones in trozos:
            r = p.add_run()
            r.text = trozo
            f = r.font
            f.name = FUENTE
            f.size = Pt(opciones.get("tam", tam))
            f.bold = opciones.get("negrita", negrita)
            f.color.rgb = opciones.get("color", color)
    return caja


def tarjeta(diapo, x, y, w, h, relleno=BLANCO, borde=BORDE, nombre=None):
    forma = diapo.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                   Inches(w), Inches(h))
    forma.adjustments[0] = 0.04
    forma.fill.solid()
    forma.fill.fore_color.rgb = relleno
    if borde is None:
        forma.line.fill.background()
    else:
        forma.line.color.rgb = borde
        forma.line.width = Pt(0.75)
    forma.shadow.inherit = False
    if nombre:
        forma.name = nombre
    return forma


def circulo(diapo, x, y, d, numero, color=NARANJA):
    forma = diapo.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    forma.fill.solid()
    forma.fill.fore_color.rgb = color
    forma.line.fill.background()
    forma.shadow.inherit = False
    marco = forma.text_frame
    marco.margin_left = marco.margin_right = marco.margin_top = marco.margin_bottom = 0
    p = marco.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    marco.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = p.add_run()
    r.text = str(numero)
    r.font.name, r.font.size, r.font.bold = FUENTE, Pt(18), True
    r.font.color.rgb = BLANCO


def flecha(diapo, x, y, color=GRIS):
    texto(diapo, x, y, 0.3, 0.3, "→", tam=16, color=color, alinear=PP_ALIGN.CENTER)


def nueva(prs, titulo, numero, oscura=False, notas=""):
    diapo = prs.slides.add_slide(prs.slide_layouts[6])
    fondo(diapo, MARINO if oscura else CREMA)
    if titulo:
        texto(diapo, 0.67, 0.42, 8.7, 0.75, titulo, tam=32, negrita=True,
              color=CREMA_TEXTO if oscura else MARINO, vertical=MSO_ANCHOR.BOTTOM, nombre="Título")
    color_pie = GRIS_OSCURO_TEXTO if oscura else GRIS
    texto(diapo, 0.67, 5.13, 5, 0.25, PIE, tam=9, color=color_pie, nombre="Pie")
    texto(diapo, 8.6, 5.07, 0.73, 0.25, str(numero), tam=9, color=color_pie,
          alinear=PP_ALIGN.RIGHT, nombre="Número")
    if notas:
        diapo.notes_slide.notes_text_frame.text = notas
    return diapo


def tabla(diapo, x, y, w, encabezado, filas, anchos, tam=12, alto_fila=0.3, alinear=None,
          oscura=False):
    alinear = alinear or [PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * (len(encabezado) - 1)
    forma = diapo.shapes.add_table(len(filas) + 1, len(encabezado), Inches(x), Inches(y),
                                   Inches(w), Inches(alto_fila * (len(filas) + 1)))
    t = forma.table
    t.first_row = True
    for j, a in enumerate(anchos):
        t.columns[j].width = Inches(a)
    for i in range(len(filas) + 1):
        t.rows[i].height = Inches(alto_fila)
        for j in range(len(encabezado)):
            celda = t.cell(i, j)
            celda.fill.solid()
            celda.fill.fore_color.rgb = RGBColor(0xDD, 0xDD, 0xDD) if i == 0 else BLANCO
            celda.margin_left = celda.margin_right = Inches(0.08)
            celda.margin_top = celda.margin_bottom = Inches(0.02)
            celda.vertical_anchor = MSO_ANCHOR.MIDDLE
            marco = celda.text_frame
            p = marco.paragraphs[0]
            p.alignment = alinear[j]
            r = p.add_run()
            r.text = encabezado[j] if i == 0 else str(filas[i - 1][j])
            r.font.name, r.font.size = FUENTE, Pt(tam)
            r.font.bold = i == 0
            r.font.color.rgb = TEXTO
    return t


def estilo_grafico(grafico, colores, etiquetas=True, formato="0.0", leyenda=True, tam=10,
                   posicion=XL_LABEL_POSITION.OUTSIDE_END, titulo=None):
    grafico.font.name = FUENTE
    grafico.font.size = Pt(tam)
    grafico.font.color.rgb = TEXTO
    if titulo:
        grafico.has_title = True
        grafico.chart_title.text_frame.text = titulo
        p = grafico.chart_title.text_frame.paragraphs[0]
        p.runs[0].font.size = Pt(12)
        p.runs[0].font.bold = False
        p.runs[0].font.color.rgb = MARINO
    else:
        grafico.has_title = False
    grafico.has_legend = leyenda
    if leyenda:
        grafico.legend.position = XL_LEGEND_POSITION.BOTTOM
        grafico.legend.include_in_layout = False
        grafico.legend.font.size = Pt(tam)
    plot = grafico.plots[0]
    for serie, color in zip(plot.series, colores):
        serie.format.fill.solid()
        serie.format.fill.fore_color.rgb = color
    if etiquetas:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = formato
        dl.number_format_is_linked = False
        dl.position = posicion
        dl.font.size = Pt(tam - 1)
        dl.font.color.rgb = TEXTO
    eje_v = grafico.value_axis
    eje_v.has_major_gridlines = True
    eje_v.major_gridlines.format.line.color.rgb = RGBColor(0xE4, 0xE4, 0xE4)
    eje_v.format.line.fill.background()
    eje_v.tick_labels.font.size = Pt(tam - 1)
    eje_v.tick_labels.font.color.rgb = GRIS
    eje_c = grafico.category_axis
    eje_c.format.line.color.rgb = GRIS_CLARO
    eje_c.tick_labels.font.size = Pt(tam)
    eje_c.has_major_gridlines = False
    return plot


# ---------------------------------------------------------------------------
# Diapositivas
# ---------------------------------------------------------------------------
def construir(d):
    cfg = {c: d.configuracion(*c) for c in EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA + EXP_HILOS}
    err = d.errores_por_version()
    ini = d.tiempos_inicializacion()
    completas = [c for c in cfg if cfg[c]["py"]]
    con_cpp = list(dict.fromkeys(EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA))
    todas = list(dict.fromkeys(EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA + EXP_HILOS))
    acel_cu_k = [cfg[c]["acel_cu_kernel"] for c in con_cpp]
    acel_cu_t = [cfg[c]["acel_cu_total"] for c in con_cpp]
    acel_pc_k = [cfg[c]["acel_pc_kernel"] for c in completas]
    acel_pc_t = [cfg[c]["acel_pc_total"] for c in completas]
    py_cpp = [cfg[c]["py_vs_cpp"] for c in completas]
    rk = [cfg[c]["pc_vs_cu_kernel"] for c in todas]
    rt = [cfg[c]["pc_vs_cu_total"] for c in todas]
    transf = [cfg[c][f"{p}_pct_transf"] for c in con_cpp for p in ("cu", "pc")]
    m3 = cfg[EXP_MASCARA[0]]
    m9 = cfg[EXP_MASCARA[1]]
    m21 = cfg[EXP_MASCARA[2]]
    r2000, r6000 = cfg[EXP_RESOLUCION[0]], cfg[EXP_RESOLUCION[2]]
    hil = [cfg[c] for c in EXP_HILOS]
    nc = d.no_completadas()
    eq, gpu = d.entorno["equipo"], d.entorno["gpu"]

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(10), Inches(5.625)
    num = 0

    # 1. Portada ---------------------------------------------------------------
    num += 1
    s = nueva(prs, None, num, oscura=True, notas=(
        "Presentamos la práctica 02: el mismo problema de la práctica 01 (filtros de convolución "
        "sobre imágenes grandes), ahora con el programa anfitrión en Python y el kernel lanzado "
        "con PyCUDA. Comparamos cuatro versiones: C++ secuencial, CUDA C, Python secuencial y PyCUDA."))
    for forma in list(s.shapes):  # la portada no lleva pie ni número
        if forma.name in ("Pie", "Número"):
            forma._element.getparent().remove(forma._element)
    texto(s, 0.67, 0.6, 8.5, 0.3, "U N I V E R S I D A D   P O L I T É C N I C A   S A L E S I A N A",
          tam=11, color=NARANJA_CLARO)
    texto(s, 0.67, 1.0, 8.6, 1.9, "Convolución de imágenes de alta resolución con Python y PyCUDA",
          tam=38, negrita=True, color=CREMA_TEXTO, vertical=MSO_ANCHOR.BOTTOM)
    texto(s, 0.67, 3.0, 8.5, 0.35, "Práctica 02 · Computación Paralela", tam=15, color=GRIS_CLARO)
    texto(s, 0.67, 4.15, 8.5, 0.3, "Juan Alberto Guillén · Ariel Solano", tam=12, color=CREMA_TEXTO)
    texto(s, 0.67, 4.45, 8.5, 0.3, "Docente: Ing. Gabriel A. León Paredes, PhD. · Noviembre de 2026",
          tam=11, color=GRIS_OSCURO_TEXTO)

    # 2. Qué hicimos -----------------------------------------------------------
    num += 1
    s = nueva(prs, "Qué hicimos en la práctica", num, notas=(
        "Tres pasos: migrar a Python todo lo que hacía el programa en C++ fuera de la GPU, "
        "comprobar que las cuatro versiones dan el mismo resultado y medir con los mismos "
        "experimentos de la práctica 01."))
    pasos = (("Migrar", "El programa anfitrión pasa de C++ a Python; la GPU ejecuta el mismo kernel CUDA C con PyCUDA."),
             ("Validar", "Las cuatro versiones con la misma imagen, la misma máscara y float32."),
             ("Medir", "Filtro, resolución, máscara e hilos por bloque, cambiando una cosa a la vez."))
    for i, (titulo, cuerpo) in enumerate(pasos):
        x = 0.67 + i * 2.97
        tarjeta(s, x, 1.3, 2.78, 2.15)
        circulo(s, x + 0.2, 1.48, 0.5, i + 1)
        texto(s, x + 0.2, 2.1, 2.4, 0.35, titulo, tam=17, negrita=True, color=MARINO)
        texto(s, x + 0.2, 2.48, 2.45, 0.95, cuerpo, tam=12.5)
        if i < 2:
            flecha(s, x + 2.75, 2.2)
    tarjeta(s, 0.67, 3.7, 8.72, 0.75)
    texto(s, 0.87, 3.8, 8.4, 0.6, [[("Equipo:  ", {"negrita": True, "color": MARINO}),
                                     (f"CPU Intel Core i9-12900K (las versiones secuenciales usan 1 núcleo)  ·  "
                                      f"GPU NVIDIA RTX 3070 (8 GB, capacidad {gpu['capacidad_computo']})  ·  "
                                      "Windows 11  ·  CUDA 12.9  ·  Python 3.12 + PyCUDA 2026.1", {})]],
          tam=12, vertical=MSO_ANCHOR.MIDDLE)

    # 3. Cuatro versiones ------------------------------------------------------
    num += 1
    s = nueva(prs, "Cuatro versiones, un mismo cálculo", num, notas=(
        "Las dos versiones de arriba son de la práctica 01 y no se reescribieron. Las dos de "
        "abajo son nuevas. Lo importante: CUDA C y PyCUDA ejecutan exactamente el mismo kernel; "
        "solo cambia el lenguaje del programa que lo lanza."))
    texto(s, 2.3, 1.25, 3.4, 0.3, "En la CPU (secuencial)", tam=13, negrita=True, color=GRIS,
          alinear=PP_ALIGN.CENTER)
    texto(s, 5.9, 1.25, 3.4, 0.3, "En la GPU (un hilo por píxel)", tam=13, negrita=True, color=GRIS,
          alinear=PP_ALIGN.CENTER)
    filas = (("Práctica 01", "Programa en C++",
              ("C++ secuencial", "4 bucles: filas, columnas y máscara"),
              ("CUDA C", "kernel convolucionGPU")),
             ("Práctica 02", "Programa en Python",
              ("Python secuencial", "los mismos 4 bucles, en Python"),
              ("PyCUDA", "el mismo kernel, lanzado desde Python")))
    for i, (etiqueta, sub, cpu, gpu_txt) in enumerate(filas):
        y = 1.65 + i * 1.45
        texto(s, 0.67, y + 0.3, 1.55, 0.7, [[(etiqueta, {"negrita": True, "color": MARINO, "tam": 15})],
                                           [(sub, {"color": GRIS, "tam": 11})]])
        for j, (titulo, cuerpo) in enumerate((cpu, gpu_txt)):
            x = 2.3 + j * 3.6
            nueva_t = i == 1
            tarjeta(s, x, y, 3.4, 1.25, relleno=NARANJA_SUAVE if nueva_t else BLANCO,
                    borde=NARANJA if nueva_t else BORDE)
            texto(s, x + 0.2, y + 0.2, 3.0, 0.4, titulo, tam=17, negrita=True,
                  color=NARANJA if nueva_t else MARINO)
            texto(s, x + 0.2, y + 0.65, 3.0, 0.5, cuerpo, tam=12.5)
    texto(s, 0.67, 4.6, 8.7, 0.35, [[("Nuevas en la práctica 02 ", {"negrita": True, "color": NARANJA}),
                                      ("(fondo naranja). CUDA C y PyCUDA ejecutan el mismo código en la GPU.", {})]],
          tam=12)

    # 4. Qué pasó a Python -----------------------------------------------------
    num += 1
    s = nueva(prs, "Qué pasó a Python y qué no cambió", num, notas=(
        "A la izquierda, todo lo que antes hacía main.cu y experimentos.cu y ahora hace Python. "
        "A la derecha, lo que no cambió: el kernel se copió sin tocar su lógica, con la misma "
        "distribución de una dimensión y la extensión con ceros."))
    columnas = (("Pasa a Python (programa anfitrión)", MARINO, [
                    "Leer la imagen y convertirla a float32",
                    "Crear las máscaras (media 1/(k·k) en float32)",
                    "Reservar memoria y copiar a la GPU",
                    "Elegir bloques e hilos y lanzar el kernel",
                    "Medir con eventos CUDA",
                    "Validar, guardar CSV e imágenes"]),
                ("Se queda igual en la GPU", NARANJA, [
                    "El kernel convolucionGPU, sin cambios",
                    "Un hilo calcula un píxel",
                    "fila = id ÷ ancho, columna = id mod ancho",
                    "Si id ≥ n, el hilo no hace nada",
                    "Vecinos en memoria global; bordes con 0",
                    "Entrada y salida en arreglos separados"]))
    for i, (titulo, color, items) in enumerate(columnas):
        x = 0.67 + i * 4.47
        tarjeta(s, x, 1.3, 4.25, 3.2)
        texto(s, x + 0.25, 1.45, 3.8, 0.4, titulo, tam=16, negrita=True, color=color)
        texto(s, x + 0.25, 1.95, 3.85, 2.7,
              [[("●  ", {"color": color, "tam": 9}), (item, {})] for item in items],
              tam=13, espacio=7)
    flecha(s, 4.82, 2.85)

    # 5. Cómo lanza Python el kernel -------------------------------------------
    num += 1
    s = nueva(prs, "Cómo lanza Python el kernel", num, notas=(
        "SourceModule compila el archivo .cu con los mismos flags de la práctica 01. Los "
        "arreglos deben ser float32 y contiguos; los escalares se pasan como np.int32 y block y "
        "grid se dan de forma explícita. Crear el contexto y compilar se mide aparte: se paga "
        "una sola vez, no en cada filtro."))
    pasos = (("SourceModule", "compila el .cu\n-O3, sm_86"),
             ("mem_alloc", "reserva una vez\npor configuración"),
             ("memcpy_htod", "imagen y máscara\nfloat32 contiguas"),
             ("kernel(...)", "block=(256,1,1)\ngrid=(bloques,1)"),
             ("memcpy_dtoh", "trae la salida\nal arreglo NumPy"))
    for i, (titulo, cuerpo) in enumerate(pasos):
        x = 0.67 + i * 1.78
        tarjeta(s, x, 1.3, 1.58, 1.25)
        texto(s, x + 0.12, 1.42, 1.4, 0.3, titulo, tam=13, negrita=True, color=NARANJA)
        texto(s, x + 0.12, 1.78, 1.4, 0.7, cuerpo.split("\n"), tam=11)
        if i < 4:
            flecha(s, x + 1.53, 1.75)
    codigo = tarjeta(s, 0.67, 2.8, 5.25, 1.95, relleno=MARINO, borde=None)
    texto(s, 0.87, 2.95, 4.95, 1.7, [
        "kernel(d_entrada, d_salida, d_mascara,",
        "       np.int32(ancho), np.int32(alto), np.int32(k),",
        "       block=(hilos, 1, 1), grid=(bloques, 1))",
        "",
        "# kernel: const float*, float*, const float*,",
        "#         int ancho, int alto, int k"], tam=10.5, color=CREMA_TEXTO)
    for p in s.shapes[-1].text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Consolas"
    cifras = ((n(ini["contexto"], 0) + " ms", "crear el contexto CUDA"),
              (n(ini["compilacion_sin_cache"], 0) + " ms", "compilar con nvcc"),
              (n(ini["carga_con_cache"], 1) + " ms", "cargar desde la caché"))
    for i, (valor, desc) in enumerate(cifras):
        y = 2.8 + i * 0.67
        tarjeta(s, 6.12, y, 3.27, 0.58)
        texto(s, 6.27, y + 0.08, 1.35, 0.42, valor, tam=17, negrita=True, color=NARANJA,
              vertical=MSO_ANCHOR.MIDDLE)
        texto(s, 7.62, y + 0.08, 1.7, 0.42, desc, tam=11, vertical=MSO_ANCHOR.MIDDLE)
    texto(s, 6.12, 4.82, 3.3, 0.25, "Se miden aparte: no entran en los tiempos del kernel.",
          tam=10, color=GRIS)

    # 6. Mismo resultado ---------------------------------------------------------
    num += 1
    s = nueva(prs, "Las cuatro versiones coinciden", num, notas=(
        "Python reproduce a C++ bit a bit, y PyCUDA a CUDA C bit a bit. La única diferencia es "
        "entre CPU y GPU en el filtro de media, por redondeo: la GPU usa FMA. La tolerancia se "
        "deduce de la precisión float32 para cada máscara; el mayor error está muy por debajo. "
        "Abajo, el recorte del filtro de nitidez en las cuatro versiones."))
    tarjetas = (("Python vs C++", n(err["python_secuencial"]["max"], 0), "diferencia: bit a bit"),
                ("PyCUDA vs CUDA C", n(err["pycuda_vs_cuda_c"]["max"], 0), "diferencia: bit a bit"),
                ("GPU vs CPU", n(err["pycuda"]["max"], 6).replace("−", ""),
                 "máxima, solo en la media (redondeo FMA)"))
    for i, (titulo, valor, desc) in enumerate(tarjetas):
        x = 0.67 + i * 2.97
        tarjeta(s, x, 1.3, 2.78, 1.35)
        texto(s, x + 0.2, 1.4, 2.4, 0.3, titulo, tam=12, negrita=True, color=GRIS)
        texto(s, x + 0.2, 1.68, 2.4, 0.5, valor, tam=26, negrita=True, color=NARANJA)
        texto(s, x + 0.2, 2.2, 2.45, 0.4, desc, tam=11)
    nombres = (("cpp_secuencial", "C++"), ("cuda_c", "CUDA C"), ("python_secuencial", "Python"),
               ("pycuda", "PyCUDA"))
    for i, (v, etiqueta) in enumerate(nombres):
        x = 0.67 + i * 2.23
        s.shapes.add_picture(str(IMAGENES / f"{v}_nitidez3_4000_recorte.png"), Inches(x + 0.2),
                             Inches(2.8), Inches(1.45), Inches(1.45))
        texto(s, x + 0.2, 4.27, 1.45, 0.25, etiqueta, tam=11, negrita=True, color=MARINO,
              alinear=PP_ALIGN.CENTER)
    texto(s, 0.67, 4.65, 8.7, 0.35, "Nitidez 3×3, recorte de 600×600 px. Tolerancia según float32: "
          "de 0,00027 (media 3×3) a 0,013 (media 21×21).", tam=11, color=GRIS)

    # 7. Cómo medimos --------------------------------------------------------------
    num += 1
    s = nueva(prs, "Cómo medimos los tiempos", num, notas=(
        "Igual que en la práctica 01: calentar, repetir y usar la mediana, separar copia, "
        "cálculo y copia de vuelta. Lo nuevo es el límite de 120 segundos para Python: si no "
        "termina, se marca como no completada y no se inventa un tiempo."))
    pasos = (("Calentar", "C++ 1 vez; CUDA C y PyCUDA 2 s, sin anotar."),
             ("Repetir", "10 veces (Python 5) y usar la mediana."),
             ("Separar", "Copia a la GPU · kernel · copia de vuelta."),
             ("Límite", "Python: 120 s; si no acaba, «no completada»."))
    for i, (titulo, cuerpo) in enumerate(pasos):
        x = 0.67 + i * 2.22
        tarjeta(s, x, 1.3, 2.05, 1.5)
        circulo(s, x + 0.15, 1.42, 0.42, i + 1)
        texto(s, x + 0.68, 1.47, 1.3, 0.35, titulo, tam=15, negrita=True, color=MARINO,
              vertical=MSO_ANCHOR.MIDDLE)
        texto(s, x + 0.15, 1.95, 1.8, 0.8, cuerpo, tam=11.5)
    texto(s, 0.67, 2.95, 8, 0.3, "Cambiamos una sola cosa a la vez:", tam=13, negrita=True, color=MARINO)
    tabla(s, 0.67, 3.3, 8.72, ["Qué cambiamos", "Valores probados", "Lo demás fijo", "Versiones"], [
        ["Filtro", "Media, nitidez, laplaciano (3×3)", "Imagen 4000², 256 hilos", "Las cuatro"],
        ["Tamaño de imagen", "2000², 4000², 6000²", "Media 9×9, 256 hilos", "Las cuatro"],
        ["Tamaño de máscara", "3×3, 9×9, 21×21", "Imagen 4000², 256 hilos", "Las cuatro"],
        ["Hilos por bloque", "128, 256, 512", "Media 9×9, imagen 4000²", "CUDA C y PyCUDA"]],
        [1.9, 2.6, 2.4, 1.82], tam=11, alto_fila=0.29,
        alinear=[PP_ALIGN.LEFT] * 4)

    # 8. Python es lento --------------------------------------------------------------
    num += 1
    f3 = [cfg[c] for c in EXP_FILTROS]
    s = nueva(prs, f"Python, {n(min(py_cpp), 0)}× a {n(max(py_cpp), 0)}× más lento que C++", num,
              oscura=True, notas=(
        "Mismo algoritmo, mismo orden de operaciones y mismo resultado bit a bit, pero cada "
        "operación de Python pasa por el intérprete. Por eso tres configuraciones grandes no "
        "terminaron en 120 segundos: las registramos como no completadas, sin estimar su tiempo."))
    for i, (valor, desc) in enumerate(((n(m3["cpp"].mediana, 0) + " ms", "C++: media 3×3 sobre 16 millones de píxeles"),
                                       (n(m3["py"].mediana / 1000, 1) + " s", "Python: el mismo cálculo, con 4 bucles explícitos"))):
        x = 0.67 + i * 4.47
        tarjeta(s, x, 1.3, 4.25, 1.45, relleno=MARINO_TARJETA, borde=MARINO_BORDE)
        texto(s, x + 0.25, 1.4, 3.8, 0.75, valor, tam=40, negrita=True, color=NARANJA_CLARO)
        texto(s, x + 0.25, 2.2, 3.8, 0.4, desc, tam=12.5, color=CREMA_TEXTO)
    texto(s, 0.67, 2.98, 4.25, 0.3, "Configuraciones completas (5 repeticiones)", tam=12, negrita=True,
          color=CREMA_TEXTO)
    tabla(s, 0.67, 3.3, 4.25, ["Configuración", "C++", "Python", "Veces"],
          [[f"{c[0].capitalize()} {c[1]}×{c[1]}, {c[2]}²", n(cfg[c]["cpp"].mediana, 0) + " ms",
            n(cfg[c]["py"].mediana / 1000, 1) + " s", n(cfg[c]["py_vs_cpp"], 0) + "×"]
           for c in completas], [1.75, 0.8, 0.85, 0.85], tam=10.5, alto_fila=0.27)
    texto(s, 5.14, 2.98, 4.25, 0.3, "No completadas en 120 s", tam=12, negrita=True, color=CREMA_TEXTO)
    tabla(s, 5.14, 3.3, 4.25, ["Configuración", "Filas hechas", "Avance"],
          [[f"{f['filtro'].capitalize()} {f['k']}×{f['k']}, {f['lado']}²",
            f"{n(f['filas_procesadas'], 0)} / {n(f['alto'], 0)}",
            n(100 * f["filas_procesadas"] / f["alto"], 0) + " %"] for f in nc],
          [1.85, 1.4, 1.0], tam=10.5, alto_fila=0.27)

    # 9. PyCUDA = CUDA C ------------------------------------------------------------------
    num += 1
    s = nueva(prs, "El kernel tarda lo mismo desde Python", num, notas=(
        "Al medir solo el kernel, PyCUDA y CUDA C dan prácticamente el mismo tiempo: es el mismo "
        "código máquina en la misma GPU. La mayor diferencia, cerca del 5 %, aparece en el kernel "
        "más corto, donde unos microsegundos de lanzamiento desde Python pesan más (hipótesis)."))
    lista = EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA[2:]
    datos = CategoryChartData()
    datos.categories = [f"{c[0][:3].capitalize()}. {c[1]}×{c[1]}, {c[2]}²" for c in lista]
    datos.add_series("CUDA C", [round(cfg[c]["cu_kernel"].mediana, 3) for c in lista])
    datos.add_series("PyCUDA", [round(cfg[c]["pc_kernel"].mediana, 3) for c in lista])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(1.25),
                            Inches(6.2), Inches(3.7), datos)
    plot = estilo_grafico(gf.chart, [MARINO, NARANJA], formato="0.00", tam=9,
                          titulo="Kernel, mediana en ms (256 hilos)")
    plot.gap_width = 60
    plot.overlap = 0
    tarjeta(s, 6.95, 1.3, 2.44, 1.6)
    texto(s, 7.12, 1.4, 2.1, 0.3, "Diferencia en el kernel", tam=12, negrita=True, color=GRIS)
    texto(s, 7.12, 1.7, 2.2, 0.6, f"{n(max(0, (min(rk) - 1) * 100), 0)} – {n((max(rk) - 1) * 100, 0)} %",
          tam=28, negrita=True, color=NARANJA)
    texto(s, 7.12, 2.3, 2.15, 0.55, "mismo código máquina en la misma GPU", tam=11)
    tarjeta(s, 6.95, 3.1, 2.44, 1.5)
    texto(s, 7.12, 3.2, 2.15, 1.6, [[("Con copias: ", {"negrita": True, "color": MARINO}),
                                     ("ambas usan la misma copia del controlador; las diferencias "
                                      f"({n((min(rt) - 1) * 100, 0)} % a +{n((max(rt) - 1) * 100, 0)} %) son ruido de la memoria paginable.", {})]],
          tam=11)

    # 10. Aceleraciones -----------------------------------------------------------------
    num += 1
    s = nueva(prs, "Cuánto acelera la GPU", num, notas=(
        "Cada GPU se compara con la versión secuencial de su propio lenguaje. La GPU hace el "
        "mismo trabajo en ambos casos; la aceleración de PyCUDA es enorme porque la referencia "
        "en Python es unas 210 a 280 veces más lenta que C++. Solo calculamos aceleraciones con "
        "ejecuciones completas."))
    bloques = (("CUDA C frente a C++", MARINO,
                (f"{n(min(acel_cu_k), 0)}× – {n(max(acel_cu_k), 0)}×", "solo el cálculo (kernel)"),
                (f"{n(min(acel_cu_t), 0)}× – {n(max(acel_cu_t), 0)}×", "contando las copias"),
                f"{len(acel_cu_k)} configuraciones"),
               ("PyCUDA frente a Python", NARANJA,
                (f"{n(min(acel_pc_k) / 1000, 0)} mil× – {n(max(acel_pc_k) / 1000, 0)} mil×", "solo el cálculo (kernel)"),
                (f"{n(min(acel_pc_t), 0)}× – {n(max(acel_pc_t), 0)}×", "contando las copias"),
                f"{len(acel_pc_k)} configuraciones donde Python terminó"))
    for i, (titulo, color, a, b, nota) in enumerate(bloques):
        x = 0.67 + i * 4.47
        tarjeta(s, x, 1.3, 4.25, 2.75)
        texto(s, x + 0.25, 1.42, 3.8, 0.35, titulo, tam=16, negrita=True, color=color)
        for j, (valor, desc) in enumerate((a, b)):
            y = 1.88 + j * 0.95
            texto(s, x + 0.25, y, 3.9, 0.5, valor, tam=27, negrita=True, color=color)
            texto(s, x + 0.25, y + 0.5, 3.9, 0.3, desc, tam=12)
        texto(s, x + 0.25, 3.75, 3.8, 0.25, nota, tam=10, color=GRIS)
    texto(s, 0.67, 4.25, 8.7, 0.6, [[("¿Por qué tanta diferencia? ", {"negrita": True, "color": MARINO}),
                                      (f"La GPU es la misma; cambia la referencia: Python secuencial es "
                                       f"{n(min(py_cpp), 0)}–{n(max(py_cpp), 0)} veces más lento que C++.", {})]],
          tam=13)

    # 11. Copias ------------------------------------------------------------------------
    num += 1
    s = nueva(prs, "Copiar datos cuesta más que calcular", num, notas=(
        "Reparto del tiempo de PyCUDA en una imagen de 4000 por 4000. Con 3 por 3 casi todo es "
        "copiar 64 MB de ida y 64 MB de vuelta; con 21 por 21 el kernel gana peso. CUDA C "
        "muestra el mismo reparto."))
    lista = EXP_MASCARA
    datos = CategoryChartData()
    datos.categories = [f"Media {c[1]}×{c[1]}" for c in lista]
    datos.add_series("Copiar a la GPU", [round(cfg[c]["pc_h2d"].mediana, 1) for c in lista])
    datos.add_series("Calcular (kernel)", [round(cfg[c]["pc_kernel"].mediana, 1) for c in lista])
    datos.add_series("Traer el resultado", [round(cfg[c]["pc_d2h"].mediana, 1) for c in lista])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(0.55), Inches(1.25), Inches(5.9),
                            Inches(3.7), datos)
    plot = estilo_grafico(gf.chart, [GRIS_AZUL, NARANJA, GRIS_AZUL_CLARO], formato="0.0",
                          posicion=XL_LABEL_POSITION.CENTER, tam=10,
                          titulo="PyCUDA, milisegundos (imagen 4000×4000)")
    plot.gap_width = 55
    plot.overlap = 100
    gf.chart.category_axis.reverse_order = True
    tarjeta(s, 6.65, 1.3, 2.74, 1.6)
    texto(s, 6.85, 1.38, 2.4, 0.7, n(m3["pc_pct_transf"], 0) + " %", tam=36, negrita=True, color=NARANJA)
    texto(s, 6.85, 2.1, 2.4, 0.7, "del tiempo de PyCUDA con un filtro 3×3 es copiar datos.", tam=12)
    tarjeta(s, 6.65, 3.1, 2.74, 1.75)
    texto(s, 6.85, 3.2, 2.4, 0.3, "Con máscara 21×21", tam=13, negrita=True, color=MARINO)
    texto(s, 6.85, 3.55, 2.4, 1.2, f"las copias bajan a {n(m21['pc_pct_transf'], 0)} %: más trabajo por "
          "píxel amortiza mejor la transferencia.", tam=12)

    # 12. Crecimiento --------------------------------------------------------------------
    num += 1
    s = nueva(prs, "El tiempo crece de forma predecible", num, notas=(
        "Al multiplicar los píxeles por 9, C++ y el kernel de PyCUDA también se multiplican por "
        "9. Con la máscara, el trabajo crece 49 veces pero el tiempo de C++ y de la GPU crece "
        "menos. En Python el costo sí crece casi como k²: con 21×21 procesaba unas 40 veces "
        "menos píxeles por segundo que con 3×3."))
    for i, (lista, titulo, trabajo, eje) in enumerate((
            (EXP_RESOLUCION, "Tamaño de imagen (veces más que 2000²)", [1, 4, 9], ["2000²", "4000²", "6000²"]),
            (EXP_MASCARA, "Tamaño de máscara (veces más que 3×3)", [1, 9, 49], ["3×3", "9×9", "21×21"]))):
        base = cfg[lista[0]]
        datos = CategoryChartData()
        datos.categories = eje
        datos.add_series("Trabajo", trabajo)
        datos.add_series("C++", [round(cfg[c]["cpp"].mediana / base["cpp"].mediana, 1) for c in lista])
        datos.add_series("PyCUDA (kernel)", [round(cfg[c]["pc_kernel"].mediana / base["pc_kernel"].mediana, 1)
                                             for c in lista])
        gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55 + i * 4.47), Inches(1.2),
                                Inches(4.35), Inches(2.9), datos)
        plot = estilo_grafico(gf.chart, [GRIS_CLARO, MARINO, NARANJA], formato="0.0", tam=9,
                              titulo=titulo)
        plot.gap_width = 50
        plot.overlap = 0
    cpp_r = r6000["cpp"].mediana / r2000["cpp"].mediana
    k_r = r6000["pc_kernel"].mediana / r2000["pc_kernel"].mediana
    texto(s, 0.67, 4.2, 4.2, 0.8, [[("Imagen ×9 → tiempo ≈ ×9", {"negrita": True, "color": NARANJA, "tam": 15})],
                                    [(f"C++ ×{n(cpp_r, 1)}, kernel ×{n(k_r, 1)}: crece igual que los píxeles.", {})]],
          tam=12, espacio=3)
    m_cpp = m21["cpp"].mediana / m3["cpp"].mediana
    m_k = m21["pc_kernel"].mediana / m3["pc_kernel"].mediana
    nc21 = d.no_completada("media", 21, 4000)
    py_px = (4000 * 4000 / m3["py"].mediana) / (nc21["filas_procesadas"] * 4000 / nc21["total"])
    texto(s, 5.14, 4.2, 4.25, 0.8, [[(f"Máscara ×49 → tiempo ×{n(m_cpp, 0)} a ×{n(m_k, 0)}", {"negrita": True, "color": NARANJA, "tam": 15})],
                                     [(f"Crece menos que las multiplicaciones (Python: ×{n(py_px, 0)}).", {})]],
          tam=12, espacio=3)

    # 13. Hilos ----------------------------------------------------------------------------
    num += 1
    s = nueva(prs, "Los hilos por bloque casi no importan", num, notas=(
        "Media 9 por 9 a 4000 por 4000. Las tres configuraciones llenan los multiprocesadores de "
        "la RTX 3070, así que el tiempo casi no cambia y la variabilidad es mínima. Con las "
        "copias la diferencia desaparece."))
    datos = CategoryChartData()
    datos.categories = [f"{r['hilos']} hilos" for r in hil]
    datos.add_series("CUDA C", [round(r["cu_kernel"].mediana, 3) for r in hil])
    datos.add_series("PyCUDA", [round(r["pc_kernel"].mediana, 3) for r in hil])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(1.25), Inches(5.6),
                            Inches(3.7), datos)
    plot = estilo_grafico(gf.chart, [MARINO, NARANJA], formato="0.000", tam=10,
                          titulo="Kernel, mediana en ms (media 9×9, 4000×4000)")
    plot.gap_width = 70
    plot.overlap = 0
    gf.chart.value_axis.minimum_scale = 0
    mejor = min(hil, key=lambda r: r["cu_kernel"].mediana)
    peor = max(hil, key=lambda r: r["cu_kernel"].mediana)
    cv_max = max(100 * r[p + "_kernel"].cv for r in hil for p in ("cu", "pc"))
    for i, (titulo, cuerpo) in enumerate((
            ("Diferencia máxima", f"{n((peor['cu_kernel'].mediana / mejor['cu_kernel'].mediana - 1) * 100, 1)} % "
                                  f"entre {mejor['hilos']} y {peor['hilos']} hilos."),
            ("Variabilidad", f"CV ≤ {n(cv_max, 2)} % en las 10 repeticiones."),
            ("Con copias", " · ".join(n(r["pc_total"].mediana, 1) for r in hil) + " ms: igual."))):
        y = 1.3 + i * 1.2
        tarjeta(s, 6.4, y, 2.99, 1.05)
        texto(s, 6.6, y + 0.12, 2.6, 0.3, titulo, tam=13, negrita=True, color=NARANJA)
        texto(s, 6.6, y + 0.45, 2.65, 0.55, cuerpo, tam=12)

    # 14. Resultados ---------------------------------------------------------------------------
    num += 1
    s = nueva(prs, "Resultados obtenidos", num, notas=(
        "Resumen en cuatro cifras, todas tomadas de los CSV del repositorio."))
    cifras = (("Mismo resultado", n(err["pycuda"]["max"], 6), "diferencia máxima CPU–GPU; Python = C++ y PyCUDA = CUDA C"),
              ("PyCUDA vs CUDA C", f"{n(max(0, (min(rk) - 1) * 100), 0)} – {n((max(rk) - 1) * 100, 0)} %", "de diferencia en el kernel"),
              ("Python vs C++", f"{n(min(py_cpp), 0)}× – {n(max(py_cpp), 0)}×", "más lento con el mismo algoritmo"),
              ("Peso de las copias", f"{n(min(transf), 0)} – {n(max(transf), 0)} %", "del tiempo de la GPU es copiar datos"))
    for i, (titulo, valor, desc) in enumerate(cifras):
        x = 0.67 + i * 2.23
        tarjeta(s, x, 1.3, 2.05, 1.95)
        texto(s, x + 0.17, 1.4, 1.8, 0.3, titulo, tam=12, negrita=True, color=GRIS)
        texto(s, x + 0.17, 1.78, 1.85, 0.5, valor, tam=21, negrita=True, color=NARANJA)
        texto(s, x + 0.17, 2.35, 1.8, 0.85, desc, tam=11)
    texto(s, 0.67, 3.5, 8.7, 1.4, [
        [("●  ", {"color": NARANJA, "tam": 9}), (f"CUDA C acelera {n(min(acel_cu_k), 0)}×–{n(max(acel_cu_k), 0)}× el cálculo "
                                                 f"frente a C++; con copias, {n(min(acel_cu_t), 0)}×–{n(max(acel_cu_t), 0)}×.", {})],
        [("●  ", {"color": NARANJA, "tam": 9}), ("Python no terminó en 120 s tres configuraciones: quedaron como «no completadas», sin estimar.", {})],
        [("●  ", {"color": NARANJA, "tam": 9}), ("Mediciones reproducibles: 10 repeticiones (Python 5), CSV y código en el repositorio.", {})]],
        tam=13, espacio=6)

    # 15. Conclusiones -----------------------------------------------------------------------
    num += 1
    s = nueva(prs, "Conclusiones", num, oscura=True, notas=(
        "Python cambia la forma de gestionar la ejecución, no lo que hace la GPU. El costo de "
        "Python está en el contexto, la compilación y, sobre todo, en la versión secuencial."))
    conclusiones = (("En la GPU no cambia nada", "Mismo kernel, mismos hilos, mismo resultado y mismo tiempo."),
                    ("Python cambia el anfitrión", "Memoria, tipos y compilación en tiempo de ejecución (una sola vez)."),
                    ("Python secuencial es el cuello", f"{n(min(py_cpp), 0)}–{n(max(py_cpp), 0)}× más lento que C++: de ahí la gran aceleración."),
                    ("Copiar sigue costando", "Con máscaras pequeñas, la mayor parte del tiempo GPU son copias."))
    for i, (titulo, cuerpo) in enumerate(conclusiones):
        x = 0.67 + (i % 2) * 4.47
        y = 1.3 + (i // 2) * 1.35
        tarjeta(s, x, y, 4.25, 1.15, relleno=MARINO_TARJETA, borde=MARINO_BORDE)
        texto(s, x + 0.22, y + 0.13, 3.9, 0.35, titulo, tam=16, negrita=True, color=NARANJA_CLARO)
        texto(s, x + 0.22, y + 0.53, 3.9, 0.55, cuerpo, tam=12.5, color=CREMA_TEXTO)
    texto(s, 0.67, 4.1, 8.7, 0.85, [
        [("Limitaciones: ", {"negrita": True}), ("un solo equipo; Python con 5 repeticiones y sin las configuraciones grandes; memoria paginable.", {})],
        [("Mejoras: ", {"negrita": True}), ("comparar máscaras en una resolución menor común, memoria fijada y medir con el commit final.", {})]],
        tam=12, color=CREMA_TEXTO, espacio=3)
    return prs


def main():
    d = Datos()
    prs = construir(d)
    prs.core_properties.title = "Práctica 02: Convolución de imágenes con Python y PyCUDA"
    prs.core_properties.author = "Juan Alberto Guillén; Ariel Solano"
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    prs.save(SALIDA)
    print(f"Presentación: {SALIDA}")


if __name__ == "__main__":
    main()
