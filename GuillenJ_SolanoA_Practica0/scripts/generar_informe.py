"""Genera el informe de la práctica 02 (Word) con el formato UPS de la guía de P01.

Todas las cifras se calculan con scripts/informe_datos.py a partir de los CSV.
Salidas:
  ../docs/informe/informe_practica02.docx
  ../docs/informe/figuras/*.png
El logotipo y las firmas se toman de ../docs/informe/guia_informe.pdf.
Uso: .venv\\Scripts\\python.exe -m scripts.generar_informe
"""
import io
import re
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pypdf
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw

from scripts.informe_datos import (EXP_FILTROS, EXP_HILOS, EXP_MASCARA, EXP_RESOLUCION,
                                   RAIZ, Datos)

DOCS = RAIZ.parent / "docs"
CARPETA = DOCS / "informe"
FIGURAS = CARPETA / "figuras"
SALIDA = CARPETA / "informe_practica02.docx"
GUIA = CARPETA / "guia_informe.pdf"
IMAGENES = RAIZ / "resultados" / "imagenes"
REPOSITORIO = "https://github.com/JuanGuillenA/procesamiento-imagenes-pycuda"
TAG_P01 = "practica01-entrega"
COMMIT_P01 = "08b155eab3bbc991cc9a20f9e633f25b41ac223f"
FUENTE = "Arial"
CODIGO = "Consolas"
GRIS = "D9D9D9"
BORDE = "808080"

COLORES = {"cpp": "#1f77b4", "py": "#6baed6", "cu_k": "#ff7f0e", "cu_t": "#fdae6b",
           "pc_k": "#2ca02c", "pc_t": "#98df8a"}
ETIQUETA_FILTRO = {"media": "Media", "nitidez": "Nitidez", "laplaciano": "Laplaciano"}


# ---------------------------------------------------------------------------
# Formato de números (coma decimal y punto de miles, como el informe de P01)
# ---------------------------------------------------------------------------
def n(valor, dec=1):
    if round(valor, dec) == 0:
        valor = 0.0  # evita "-0,0"
    texto = f"{valor:,.{dec}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".").replace("-", "−")


def dif(cociente, dec=1):
    """Diferencia porcentual con signo a partir de un cociente (1 = igual)."""
    valor = (cociente - 1) * 100
    if round(valor, dec) == 0:
        return n(0, dec) + " %"
    return ("+" if valor > 0 else "−") + n(abs(valor), dec) + " %"


def e(valor):
    return f"{valor:.3e}".replace(".", ",")


def x(valor, dec=1):
    return n(valor, dec) + "×"


def pct(valor, dec=1):
    return n(valor, dec) + " %"


def conf(filtro, k, lado=None):
    texto = f"{ETIQUETA_FILTRO[filtro]} {k}×{k}"
    return texto if lado is None else f"{texto}, {lado}×{lado}"


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def _guardar(nombre):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIGURAS / nombre, dpi=170)
    plt.close()
    return FIGURAS / nombre


def figura_comparacion(d, nombre, titulo, configuraciones, etiquetas):
    series = (("C++ secuencial", "cpp", None), ("Python secuencial", "py", None),
              ("CUDA C: kernel", "cu_kernel", "cu_k"), ("CUDA C: total", "cu_total", "cu_t"),
              ("PyCUDA: kernel", "pc_kernel", "pc_k"), ("PyCUDA: total", "pc_total", "pc_t"))
    filas = [d.configuracion(*c) for c in configuraciones]
    ancho = 0.8 / len(series)
    fig, eje = plt.subplots(figsize=(10, 5.2))
    for i, (etiqueta, clave, color) in enumerate(series):
        color = COLORES[color or clave]
        xs = [p + (i - (len(series) - 1) / 2) * ancho for p in range(len(filas))]
        for xp, r in zip(xs, filas):
            res = r[clave]
            if res is None:  # Python no completada: barra vacía hasta el límite
                lim = r["py_nc"]["total"]
                eje.bar(xp, lim, ancho, facecolor="none", edgecolor=color, hatch="///",
                        linewidth=1)
                eje.text(xp, 300, "no completada (>120 s)", ha="center", va="bottom",
                         rotation=90, fontsize=7, color="#1f3b5c",
                         bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
            else:
                eje.bar(xp, res.mediana, ancho, color=color, yerr=res.de, capsize=2,
                        error_kw={"elinewidth": 0.8})
        eje.bar(0, 0, 0, color=color, label=etiqueta)
    eje.set_yscale("log")
    eje.set_ylim(0.1, 1e6)
    eje.set_xticks(range(len(filas)), etiquetas)
    eje.set_ylabel("Tiempo (ms)")
    eje.set_title(titulo)
    eje.grid(axis="y", alpha=0.3)
    eje.legend(fontsize=8, ncol=3, loc="upper left")
    return _guardar(nombre)


def figura_hilos(d):
    fig, eje = plt.subplots(1, 2, figsize=(10, 4.2))
    hilos = [c[3] for c in EXP_HILOS]
    filas = [d.configuracion(*c) for c in EXP_HILOS]
    for ax, campo, titulo in ((eje[0], "kernel", "Kernel"), (eje[1], "total", "Tiempo conjunto GPU")):
        for i, (pref, nombre, color) in enumerate((("cu", "CUDA C", "cu_k"), ("pc", "PyCUDA", "pc_k"))):
            res = [r[f"{pref}_{campo}"] for r in filas]
            xs = [p + (i - 0.5) * 0.38 for p in range(len(hilos))]
            barras = ax.bar(xs, [s.mediana for s in res], 0.38, yerr=[s.de for s in res],
                            capsize=3, color=COLORES[color] if campo == "kernel" else
                            COLORES[color.replace("_k", "_t")], label=nombre)
            ax.bar_label(barras, [n(s.mediana, 3 if campo == "kernel" else 2) for s in res],
                         fontsize=7, padding=2)
        ax.set_xticks(range(len(hilos)), [str(h) for h in hilos])
        ax.set_xlabel("Hilos por bloque")
        ax.set_ylabel("ms")
        ax.set_title(f"{titulo} (media 9×9, 4000×4000)", fontsize=10)
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.25)
        ax.legend(fontsize=8, loc="upper left", ncol=2)
    return _guardar("comparacion_hilos.png")


def figura_distribucion(d):
    configuraciones = [("media", 3, 4000, 256), ("nitidez", 3, 4000, 256),
                       ("laplaciano", 3, 4000, 256), ("media", 9, 4000, 256),
                       ("media", 21, 4000, 256)]
    etiquetas = ["Media 3×3", "Nitidez 3×3", "Laplaciano 3×3", "Media 9×9", "Media 21×21"]
    fig, ejes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for eje, (pref, titulo) in zip(ejes, (("cu", "CUDA C"), ("pc", "PyCUDA"))):
        filas = [d.configuracion(*c) for c in configuraciones]
        h2d = [r[f"{pref}_h2d"].mediana for r in filas]
        ker = [r[f"{pref}_kernel"].mediana for r in filas]
        d2h = [r[f"{pref}_d2h"].mediana for r in filas]
        xs = range(len(filas))
        eje.bar(xs, h2d, color="#8c96a8", label="Copia CPU→GPU (H2D)")
        eje.bar(xs, ker, bottom=h2d, color="#b5541b", label="Kernel")
        eje.bar(xs, d2h, bottom=[a + b for a, b in zip(h2d, ker)], color="#b7bfcc",
                label="Copia GPU→CPU (D2H)")
        for xp, a, b, c in zip(xs, h2d, ker, d2h):
            eje.text(xp, a + b + c + 0.4, f"{n(100 * (a + c) / (a + b + c), 0)} %\ncopias",
                     ha="center", fontsize=7)
        eje.set_xticks(list(xs), etiquetas, rotation=15, fontsize=8)
        eje.set_title(f"{titulo} (4000×4000, 256 hilos)", fontsize=10)
        eje.grid(axis="y", alpha=0.3)
        eje.set_ylim(0, 33)
    ejes[0].set_ylabel("Milisegundos (medianas)")
    ejes[1].legend(fontsize=7.5, loc="upper left")
    return _guardar("distribucion_tiempo_gpu.png")


def figura_aceleracion(d):
    todas = EXP_FILTROS + [c for c in EXP_RESOLUCION] + [EXP_MASCARA[2]]
    etiquetas = {c: f"{ETIQUETA_FILTRO[c[0]]} {c[1]}×{c[1]}\n{c[2]}²" for c in todas}
    fig, ejes = plt.subplots(1, 2, figsize=(10.5, 4.4), gridspec_kw={"width_ratios": [7, 4]})
    for eje, (clave, titulo, lista) in zip(ejes, (
            ("cu", "CUDA C frente a C++ secuencial", todas),
            ("pc", "PyCUDA frente a Python secuencial", [c for c in todas if d.configuracion(*c)["py"]]))):
        filas = [d.configuracion(*c) for c in lista]
        xs = np.arange(len(filas))
        k = [r[f"acel_{clave}_kernel"] for r in filas]
        t = [r[f"acel_{clave}_total"] for r in filas]
        b1 = eje.bar(xs - 0.2, k, 0.4, label="Solo kernel", color="#b5541b")
        b2 = eje.bar(xs + 0.2, t, 0.4, label="Con transferencias", color="#8c96a8")
        eje.bar_label(b1, [n(v, 0) for v in k], fontsize=6.5, padding=1)
        eje.bar_label(b2, [n(v, 0) for v in t], fontsize=6.5, padding=1)
        eje.set_xticks(xs, [etiquetas[c] for c in lista], fontsize=7.5)
        eje.set_yscale("log")
        eje.set_ylim(1, max(k) * 6)
        eje.set_title(titulo, fontsize=10)
        eje.grid(axis="y", alpha=0.3)
    ejes[0].set_ylabel("Aceleración (veces, escala log.)")
    ejes[0].legend(fontsize=8, loc="upper left")
    return _guardar("aceleracion.png")


def figura_cuda_vs_pycuda(d):
    lista = EXP_FILTROS + EXP_RESOLUCION + [EXP_MASCARA[2], EXP_HILOS[0], EXP_HILOS[2]]
    filas = [d.configuracion(*c) for c in lista]
    etiquetas = [f"{ETIQUETA_FILTRO[c[0]][:3]}. {c[1]}×{c[1]}\n{c[2]}², {c[3]} h" for c in lista]
    xs = np.arange(len(filas))
    fig, eje = plt.subplots(figsize=(10.5, 4.2))
    b1 = eje.bar(xs - 0.2, [r["pc_vs_cu_kernel"] for r in filas], 0.4, color=COLORES["pc_k"],
                 label="Kernel")
    b2 = eje.bar(xs + 0.2, [r["pc_vs_cu_total"] for r in filas], 0.4, color=COLORES["pc_t"],
                 label="Tiempo conjunto (H2D + kernel + D2H)")
    eje.bar_label(b1, [n(r["pc_vs_cu_kernel"], 2) for r in filas], fontsize=6.5, padding=1)
    eje.bar_label(b2, [n(r["pc_vs_cu_total"], 2) for r in filas], fontsize=6.5, padding=1)
    eje.axhline(1, color="#333333", linewidth=1, linestyle="--")
    eje.set_xticks(xs, etiquetas, fontsize=7)
    eje.set_ylim(0, 1.45)
    eje.set_ylabel("Mediana PyCUDA / mediana CUDA C")
    eje.set_title("PyCUDA frente a CUDA C (1 = mismo tiempo; > 1 = PyCUDA más lento)", fontsize=10)
    eje.grid(axis="y", alpha=0.3)
    eje.legend(fontsize=8, loc="upper left")
    return _guardar("cuda_c_vs_pycuda.png")


def figuras_preparacion():
    """Miniaturas de la imagen original (con el recorte) y de las tres resoluciones."""
    FIGURAS.mkdir(parents=True, exist_ok=True)
    Image.MAX_IMAGE_PIXELS = None
    original = Image.open(RAIZ / "imagenes" / "ImagenGrande.jpg").convert("L")
    escala = 300 / original.height
    mini = original.resize((round(original.width * escala), 300)).convert("RGB")
    lado = min(original.size)
    x0 = (original.width - lado) // 2
    y0 = (original.height - lado) // 2
    ImageDraw.Draw(mini).rectangle(
        [x0 * escala, y0 * escala, (x0 + lado) * escala - 1, (y0 + lado) * escala - 1],
        outline=(255, 128, 0), width=3)
    mini.save(FIGURAS / "original_recorte.png")
    rutas = [FIGURAS / "original_recorte.png"]
    for lado_img in (6000, 4000, 2000):
        img = Image.open(RAIZ / "datos" / f"base_{lado_img}.pgm").resize((300, 300), Image.LANCZOS)
        img.save(FIGURAS / f"base_{lado_img}.png")
        rutas.append(FIGURAS / f"base_{lado_img}.png")
    # Imagen original 4000 reducida con el recuadro del acercamiento
    reducida = Image.open(IMAGENES / "original_4000_reducida.png").convert("RGB")
    f = reducida.width / 4000
    from scripts.evidencia_visual import RECORTE
    ImageDraw.Draw(reducida).rectangle([v * f for v in RECORTE], outline=(255, 128, 0), width=6)
    reducida.save(FIGURAS / "original_4000_marcada.png")
    return rutas


# ---------------------------------------------------------------------------
# Utilidades de python-docx
# ---------------------------------------------------------------------------
def _borde_xml(padre, nombre, lados, val="single", tam=4, color="000000"):
    bordes = OxmlElement(nombre)
    for lado in lados:
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), str(tam))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        bordes.append(el)
    padre.append(bordes)


def bordes_tabla(tabla, val="single", tam=4, color="000000"):
    _borde_xml(tabla._tbl.tblPr, "w:tblBorders",
               ("top", "left", "bottom", "right", "insideH", "insideV"), val, tam, color)


def anchos(tabla, lista_pt):
    tabla.autofit = False
    tbl_pr = tabla._tbl.tblPr
    diseno = OxmlElement("w:tblLayout")
    diseno.set(qn("w:type"), "fixed")
    tbl_pr.append(diseno)
    rejilla = tabla._tbl.tblGrid.findall(qn("w:gridCol"))
    for col, w in zip(rejilla, lista_pt):
        col.set(qn("w:w"), str(int(w * 20)))
    for fila in tabla.rows:
        for celda, w in zip(fila.cells, lista_pt):
            celda.width = Pt(w)


def sombrear(celda, color):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    celda._tc.get_or_add_tcPr().append(shd)


def margenes_celda(tabla, izq=60, der=60, arr=20, aba=20):
    mar = OxmlElement("w:tblCellMar")
    for lado, v in (("top", arr), ("left", izq), ("bottom", aba), ("right", der)):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tabla._tbl.tblPr.append(mar)


def repetir_encabezado(fila):
    tr_pr = fila._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def no_dividir(fila):
    tr_pr = fila._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def formato_parrafo(p, tam=11, alinear=None, antes=0, despues=6, interlineado=1.1, sangria=None):
    pf = p.paragraph_format
    pf.space_before = Pt(antes)
    pf.space_after = Pt(despues)
    pf.line_spacing = interlineado
    if alinear is not None:
        p.alignment = alinear
    if sangria is not None:
        pf.left_indent = Pt(sangria)


def texto_rico(p, texto, tam=11, negrita=False, cursiva=False, color=None):
    """**negrita**, `código`, [[resaltado]] y enlaces http(s) dentro del texto."""
    partes = re.split(r"(\*\*.+?\*\*|`.+?`|\[\[.+?\]\]|https?://\S+)", texto)
    for parte in partes:
        if not parte:
            continue
        estilo = {"bold": negrita, "italic": cursiva, "font": FUENTE, "size": tam,
                  "color": color, "hl": None, "under": False}
        if parte.startswith("**") and parte.endswith("**"):
            parte, estilo["bold"] = parte[2:-2], True
        elif parte.startswith("`") and parte.endswith("`"):
            parte, estilo["font"], estilo["size"] = parte[1:-1], CODIGO, tam - 1
        elif parte.startswith("[[") and parte.endswith("]]"):
            parte, estilo["hl"], estilo["bold"] = parte[2:-2], WD_COLOR_INDEX.YELLOW, True
        elif parte.startswith("http"):
            estilo["color"], estilo["under"] = RGBColor(0x05, 0x63, 0xC1), True
        run = p.add_run(parte)
        run.bold, run.italic, run.underline = estilo["bold"], estilo["italic"], estilo["under"]
        run.font.name = estilo["font"]
        run._element.rPr.rFonts.set(qn("w:eastAsia"), estilo["font"])
        run.font.size = Pt(estilo["size"])
        if estilo["color"] is not None:
            run.font.color.rgb = estilo["color"]
        if estilo["hl"] is not None:
            run.font.highlight_color = estilo["hl"]
    return p


class Bloque:
    """Escribe contenido dentro de una celda (o del cuerpo del documento)."""

    def __init__(self, contenedor, ancho_pt):
        self.c = contenedor
        self.ancho = ancho_pt
        self.libre = contenedor.paragraphs[0] if contenedor.paragraphs and not \
            contenedor.paragraphs[0].text else None

    def _parrafo(self):
        if self.libre is not None:
            p, self.libre = self.libre, None
            return p
        return self.c.add_paragraph()

    def p(self, texto, tam=11, alinear=WD_ALIGN_PARAGRAPH.JUSTIFY, antes=0, despues=6,
          negrita=False, cursiva=False, sangria=None, mantener=False):
        par = self._parrafo()
        formato_parrafo(par, tam, alinear, antes, despues, sangria=sangria)
        par.paragraph_format.keep_with_next = False  # en filas de tabla Word mueve la fila entera
        return texto_rico(par, texto, tam, negrita, cursiva)

    def titulo(self, texto, tam=12, antes=4):
        return self.p(texto, tam=tam, alinear=WD_ALIGN_PARAGRAPH.LEFT, antes=antes,
                      despues=5, negrita=True, mantener=True)

    def subtitulo(self, texto):
        return self.titulo(texto, tam=11.5, antes=6)

    def vinetas(self, lista, tam=11, alinear=WD_ALIGN_PARAGRAPH.JUSTIFY):
        for item in lista:
            par = self._parrafo()
            par.style = "List Bullet"
            formato_parrafo(par, tam, alinear, 0, 3)
            texto_rico(par, item, tam)

    def codigo(self, lineas):
        for i, linea in enumerate(lineas):
            par = self._parrafo()
            formato_parrafo(par, 8.5, WD_ALIGN_PARAGRAPH.LEFT, 4 if i == 0 else 0,
                            6 if i == len(lineas) - 1 else 0, interlineado=1.0)
            par.paragraph_format.keep_with_next = False
            run = par.add_run(linea if linea else " ")
            run.font.name = CODIGO
            run._element.rPr.rFonts.set(qn("w:eastAsia"), CODIGO)
            run.font.size = Pt(8.5)

    def pie(self, texto):
        return self.p(texto, tam=9, alinear=WD_ALIGN_PARAGRAPH.CENTER, cursiva=True,
                      despues=8)

    def imagen(self, ruta, ancho_pulg):
        par = self._parrafo()
        formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.CENTER, antes=4, despues=2)
        par.paragraph_format.keep_with_next = False
        par.add_run().add_picture(str(ruta), width=Inches(ancho_pulg))

    def figura(self, ruta, ancho_pulg, pie):
        """Figura y pie en una tabla de dos filas sin bordes que no se separa."""
        t = self.c.add_table(rows=2, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        bordes_tabla(t, val="nil")
        margenes_celda(t, 0, 0, 0, 0)
        anchos(t, [self.ancho])
        no_dividir(t.rows[0])
        par = t.rows[0].cells[0].paragraphs[0]
        formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.CENTER, antes=6, despues=2)
        par.paragraph_format.keep_with_next = True
        par.add_run().add_picture(str(ruta), width=Inches(ancho_pulg))
        par = t.rows[1].cells[0].paragraphs[0]
        formato_parrafo(par, 9, WD_ALIGN_PARAGRAPH.CENTER, 0, 6)
        texto_rico(par, pie, 9, cursiva=True)
        if self.c.paragraphs and not self.c.paragraphs[-1].text:
            formato_parrafo(self.c.paragraphs[-1], 4, despues=0, interlineado=1.0)

    def tabla(self, encabezado, filas, anchos_pt, alinear=None, tam=8, negrita_col0=True,
              negritas=None, encabezado_centrado=True):
        """Tabla de datos: encabezado gris, primera columna en negrita."""
        alinear = alinear or ["l"] + ["r"] * (len(encabezado) - 1)
        mapa = {"l": WD_ALIGN_PARAGRAPH.LEFT, "r": WD_ALIGN_PARAGRAPH.RIGHT,
                "c": WD_ALIGN_PARAGRAPH.CENTER}
        t = self.c.add_table(rows=1 + len(filas), cols=len(encabezado))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        bordes_tabla(t, tam=4, color=BORDE)
        margenes_celda(t)
        anchos(t, anchos_pt)
        repetir_encabezado(t.rows[0])
        for j, texto in enumerate(encabezado):
            celda = t.rows[0].cells[j]
            sombrear(celda, GRIS)
            celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            par = celda.paragraphs[0]
            formato_parrafo(par, tam, WD_ALIGN_PARAGRAPH.CENTER if encabezado_centrado
                            else mapa[alinear[j]], 1, 1, 1.0)
            texto_rico(par, texto, tam, negrita=True)
        for i, fila in enumerate(filas, start=1):
            no_dividir(t.rows[i])
            for j, texto in enumerate(fila):
                celda = t.rows[i].cells[j]
                celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                par = celda.paragraphs[0]
                formato_parrafo(par, tam, mapa[alinear[j]], 1, 1, 1.0)
                negrita = (j == 0 and negrita_col0) or bool(negritas and (i - 1, j) in negritas)
                texto_rico(par, str(texto), tam, negrita=negrita)
        # Celda: Word agrega un párrafo vacío después de la tabla; se reutiliza.
        if hasattr(self.c, "paragraphs") and self.c.paragraphs:
            ultimo = self.c.paragraphs[-1]
            if not ultimo.text:
                formato_parrafo(ultimo, 4, despues=0, interlineado=1.0)
                self.libre = None
        return t

    def rejilla_imagenes(self, items, columnas, ancho_img, titulo=None, descripcion=None):
        """items: lista de (ruta, pie). Tabla sin bordes de imágenes con pie.

        Con título, este va en la primera fila y todas las filas se mantienen juntas
        (en una tabla pequeña "conservar con el siguiente" sí funciona como se espera).
        """
        filas = (len(items) + columnas - 1) // columnas
        extra = 1 if titulo else 0
        t = self.c.add_table(rows=filas * 2 + extra, cols=columnas)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        bordes_tabla(t, val="nil")
        margenes_celda(t, 30, 30, 10, 10)
        anchos(t, [self.ancho / columnas] * columnas)
        if titulo:
            celda = t.rows[0].cells[0].merge(t.rows[0].cells[columnas - 1])
            par = celda.paragraphs[0]
            formato_parrafo(par, 11.5, WD_ALIGN_PARAGRAPH.LEFT, 6, 3)
            texto_rico(par, f"**{titulo}**", 11.5)
            par.paragraph_format.keep_with_next = True
            if descripcion:
                par = celda.add_paragraph()
                formato_parrafo(par, 11, WD_ALIGN_PARAGRAPH.LEFT, 0, 3)
                texto_rico(par, descripcion, 11)
                par.paragraph_format.keep_with_next = True
        for idx, (ruta, pie) in enumerate(items):
            f, c = divmod(idx, columnas)
            fila_img, fila_pie = t.rows[2 * f + extra], t.rows[2 * f + 1 + extra]
            no_dividir(fila_img)
            ultima = f == filas - 1
            par = fila_img.cells[c].paragraphs[0]
            formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.CENTER, despues=0)
            par.paragraph_format.keep_with_next = bool(titulo)
            par.add_run().add_picture(str(ruta), width=Inches(ancho_img))
            par = fila_pie.cells[c].paragraphs[0]
            formato_parrafo(par, 8, WD_ALIGN_PARAGRAPH.CENTER, 0, 4, 1.0)
            par.paragraph_format.keep_with_next = bool(titulo) and not ultima
            texto_rico(par, pie, 8)
        if self.c.paragraphs and not self.c.paragraphs[-1].text:
            formato_parrafo(self.c.paragraphs[-1], 4, despues=0, interlineado=1.0)
        return t


# ---------------------------------------------------------------------------
# Documento: encabezado UPS, marco principal y pie
# ---------------------------------------------------------------------------
def recursos_guia():
    """Logotipo UPS y firmas tomados del PDF de la guía (sin duplicarlos)."""
    lector = pypdf.PdfReader(str(GUIA))
    logo, firmas = None, {}
    for imagen in lector.pages[-1].images:
        tam = Image.open(io.BytesIO(imagen.data)).size
        if tam == (300, 81) and logo is None:
            logo = io.BytesIO(imagen.data)
        elif tam == (528, 252):
            firmas["izquierda"] = imagen.data
        elif tam == (290, 117):
            firmas["derecha"] = imagen.data
    return logo, firmas


def encabezado_pie(doc, logo):
    seccion = doc.sections[0]
    seccion.page_width, seccion.page_height = Inches(8.5), Inches(11)
    seccion.left_margin, seccion.right_margin = Pt(51), Pt(49)
    seccion.top_margin, seccion.bottom_margin = Pt(104), Pt(60)
    seccion.header_distance, seccion.footer_distance = Pt(30), Pt(30)

    cab = seccion.header
    t = cab.add_table(rows=3, cols=3, width=Pt(438))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    bordes_tabla(t, tam=6)
    margenes_celda(t, 60, 60, 20, 20)
    anchos(t, [138, 160, 140])
    textos = {(0, 1): "**VICERRECTORADO DOCENTE**", (0, 2): "**Código:** GUIA-PRL-001",
              (1, 1): "CONSEJO ACADÉMICO", (1, 2): "**Aprobación:** 2016/04/06"}
    for (f, c), texto in textos.items():
        par = t.rows[f].cells[c].paragraphs[0]
        formato_parrafo(par, 8, WD_ALIGN_PARAGRAPH.CENTER if c == 1 else WD_ALIGN_PARAGRAPH.LEFT,
                        3, 3, 1.0)
        t.rows[f].cells[c].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        texto_rico(par, texto, 8)
    logo_celda = t.rows[0].cells[0].merge(t.rows[1].cells[0])
    logo_celda.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    par = logo_celda.paragraphs[0]
    formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.CENTER, despues=0)
    logo.seek(0)
    par.add_run().add_picture(logo, width=Pt(113))
    formato = t.rows[2].cells[0].merge(t.rows[2].cells[2])
    par = formato.paragraphs[0]
    formato_parrafo(par, 7.5, WD_ALIGN_PARAGRAPH.CENTER, 2, 2, 1.0)
    texto_rico(par, "**Formato:** Guía de Práctica de Laboratorio / Talleres / Centros de Simulación", 7.5)
    vacio = cab.paragraphs[0]
    formato_parrafo(vacio, 2, despues=0)

    pie = seccion.footer.paragraphs[0]
    formato_parrafo(pie, 8, WD_ALIGN_PARAGRAPH.RIGHT, 0, 0)
    texto_rico(pie, "**Resolución CS N° 076-04-2016-04-20**", 8)


def estilos(doc):
    normal = doc.styles["Normal"]
    normal.font.name = FUENTE
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FUENTE)
    lista = doc.styles["List Bullet"]
    lista.font.name = FUENTE
    lista.font.size = Pt(11)


ANCHO_MARCO = [170, 84, 86, 172]  # 512 pt = ancho útil
ANCHO_UTIL = sum(ANCHO_MARCO) - 12


class Marco:
    """Tabla principal con borde, como el formato de la guía."""

    def __init__(self, doc, logo):
        self.t = doc.add_table(rows=3, cols=4)
        self.t.alignment = WD_TABLE_ALIGNMENT.CENTER
        bordes_tabla(self.t, tam=6)
        margenes_celda(self.t, 90, 90, 40, 40)
        anchos(self.t, ANCHO_MARCO)
        f0, f1, f2 = self.t.rows
        celda = f0.cells[0].merge(f0.cells[1])
        par = celda.paragraphs[0]
        formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.LEFT, antes=4, despues=26)
        logo.seek(0)
        par.add_run().add_picture(logo, width=Pt(140))
        celda = f0.cells[2].merge(f0.cells[3])
        par = celda.paragraphs[0]
        formato_parrafo(par, alinear=WD_ALIGN_PARAGRAPH.CENTER, antes=16)
        texto_rico(par, "**PRÁCTICA DE LABORATORIO**", 11)
        celda = f1.cells[0].merge(f1.cells[2])
        texto_rico(celda.paragraphs[0], "**CARRERA**: Computación", 11)
        texto_rico(f1.cells[3].paragraphs[0], "**ASIGNATURA**: Computación Paralela", 11)
        texto_rico(f2.cells[0].paragraphs[0], "**NRO. PRÁCTICA**:", 11)
        par = f2.cells[1].paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        texto_rico(par, "2", 11)
        celda = f2.cells[2].merge(f2.cells[3])
        texto_rico(celda.paragraphs[0], "**TÍTULO PRÁCTICA**: Convolución de imágenes de alta "
                   "resolución mediante PyCUDA", 11)
        for fila in (f1, f2):
            for c in fila.cells:
                formato_parrafo(c.paragraphs[0], 11, None, 2, 2, 1.0)

    def fila(self, centrado=None):
        fila = self.t.add_row()
        celda = fila.cells[0].merge(fila.cells[3])
        if centrado:
            par = celda.paragraphs[0]
            formato_parrafo(par, 11, WD_ALIGN_PARAGRAPH.CENTER, 2, 2)
            texto_rico(par, f"**{centrado}**", 11)
            no_dividir(fila)
            return None
        return Bloque(celda, ANCHO_UTIL)


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------
def tabla_experimento(b, d, configuraciones, etiquetas):
    """Filas pareadas: CUDA C (frente a C++) y PyCUDA (frente a Python)."""
    filas, resumen = [], []
    for c, etiqueta in zip(configuraciones, etiquetas):
        r = d.configuracion(*c)
        resumen.append(r)
        for pref, nombre, sec in (("cu", "CUDA C", "cpp"), ("pc", "PyCUDA", "py")):
            if r[sec] is None:
                secuencial = "no completada"
                ak = at = "—"
            else:
                secuencial = f"{n(r[sec].mediana)} ({n(r[sec].iqr)})"
                ak = x(r[f"acel_{pref}_kernel"])
                at = x(r[f"acel_{pref}_total"])
            filas.append([etiqueta if pref == "cu" else "",
                          f"{nombre} / {'C++' if sec == 'cpp' else 'Python'}", secuencial,
                          n(r[f"{pref}_h2d"].mediana, 2),
                          f"{n(r[f'{pref}_kernel'].mediana, 3)} ({n(r[f'{pref}_kernel'].iqr, 3)})",
                          n(r[f"{pref}_d2h"].mediana, 2),
                          f"{n(r[f'{pref}_total'].mediana, 2)} ({n(r[f'{pref}_total'].iqr, 2)})",
                          ak, at, pct(r[f"{pref}_pct_transf"])])
    # Negrita en la mejor aceleración de cada columna y versión
    negritas = set()
    for col, clave in ((7, "kernel"), (8, "total")):
        for desplaz, pref in ((0, "cu"), (1, "pc")):
            valores = [(i, r.get(f"acel_{pref}_{clave}")) for i, r in enumerate(resumen)]
            valores = [(i, v) for i, v in valores if v]
            if valores:
                mejor = max(valores, key=lambda t: t[1])[0]
                negritas.add((2 * mejor + desplaz, col))
    b.tabla(["Configuración", "Versión / secuencial", "Secuencial (IQR)", "H2D", "Kernel (IQR)",
             "D2H", "Total GPU (IQR)", "Acel. kernel", "Acel. c/ transf.", "% transf."],
            filas, [62, 74, 62, 29, 56, 29, 56, 48, 44, 38], negritas=negritas, tam=7.5,
            alinear=["l", "l"] + ["r"] * 8)
    return resumen


def construir(d, logo, firmas, figs):
    doc = Document()
    estilos(doc)
    encabezado_pie(doc, logo)
    marco = Marco(doc, logo)

    cfg = {c: d.configuracion(*c) for c in EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA + EXP_HILOS}
    ent = d.entorno
    err = d.errores_por_version()
    ini = d.tiempos_inicializacion()
    nc = d.no_completadas()
    completas = [c for c in cfg if cfg[c]["py"]]
    con_cpp = list(dict.fromkeys(EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA))
    acel_cu_k = [cfg[c]["acel_cu_kernel"] for c in con_cpp]
    acel_cu_t = [cfg[c]["acel_cu_total"] for c in con_cpp]
    acel_pc_k = [cfg[c]["acel_pc_kernel"] for c in completas]
    acel_pc_t = [cfg[c]["acel_pc_total"] for c in completas]
    py_cpp = [cfg[c]["py_vs_cpp"] for c in completas]
    todas = list(dict.fromkeys(EXP_FILTROS + EXP_RESOLUCION + EXP_MASCARA + EXP_HILOS))
    rk = [cfg[c]["pc_vs_cu_kernel"] for c in todas]
    rt = [cfg[c]["pc_vs_cu_total"] for c in todas]
    transf = [cfg[c][f"{p}_pct_transf"] for c in con_cpp for p in ("cu", "pc")]
    f3 = [cfg[c] for c in EXP_FILTROS]
    m9_2000, m9_4000, m9_6000 = (cfg[c] for c in EXP_RESOLUCION)
    m3, m21 = cfg[EXP_MASCARA[0]], cfg[EXP_MASCARA[2]]
    hil = [cfg[c] for c in EXP_HILOS]
    gpu = ent["gpu"]
    ver = ent["versiones"]
    eq = ent["equipo"]

    # --- Objetivo ---------------------------------------------------------
    b = marco.fila()
    b.p("**OBJETIVO ALCANZADO:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Migrar a Python el programa anfitrión de la práctica 01 (carga de imágenes, máscaras, "
        "selección del filtro, ejecución, validación, mediciones y CSV) y ejecutar desde Python, "
        "mediante PyCUDA, el mismo kernel de convolución escrito en CUDA C.",
        "Implementar una versión secuencial en Python con recorridos explícitos y verificar que "
        "las cuatro versiones (C++ secuencial, CUDA C, Python secuencial y PyCUDA) producen "
        "resultados equivalentes.",
        "Comparar el rendimiento de las cuatro versiones al variar el filtro, la resolución, el "
        "tamaño de la máscara y los hilos por bloque, y comunicar resultados reproducibles: "
        "código, datos de entrada, registros CSV y gráficas."])
    marco.fila("ACTIVIDADES DESARROLLADAS")

    # --- 1. Entorno ---------------------------------------------------------
    b = marco.fila()
    b.titulo("1. Revisar la práctica 01 y preparar el entorno Python/PyCUDA.")
    b.p(f"**Repositorio de la presente práctica:** {REPOSITORIO}", alinear=WD_ALIGN_PARAGRAPH.LEFT)
    b.p(f"**Práctica 01 (base):** etiqueta git `{TAG_P01}`, commit {COMMIT_P01}.",
        alinear=WD_ALIGN_PARAGRAPH.LEFT)
    b.p("**Commit evaluado (práctica 02):** [[PENDIENTE: escribir aquí el hash del commit que "
        "contiene este código y estos CSV]]", alinear=WD_ALIGN_PARAGRAPH.LEFT)
    b.p("La práctica 02 continúa la práctica 01: se conservan las imágenes, los tres filtros, sus "
        "coeficientes, la extensión con ceros y el kernel `convolucionGPU`. El código de la "
        "práctica 01 (C/C++ y CUDA C) está en `src/secuencial_c/`, `src/cuda_c/` y "
        "`src/filtros.cu`; lo nuevo está en `src/python/` (Python secuencial) y `src/pycuda/` "
        "(PyCUDA). Las cuatro versiones leen los mismos archivos de `datos/` y escriben en "
        "`resultados/`. `ejecutar_cuda.bat` compila y ejecuta C++ y CUDA C; `ejecutar_pycuda.bat` "
        "prepara el entorno de Visual Studio, ejecuta las pruebas (pytest), valida y mide Python y "
        "PyCUDA; `ejecutar_paralelo.bat` ejecuta solo CUDA C y PyCUDA sobre cualquier imagen. El "
        "README indica las dependencias (`requirements.txt`) y los comandos.")
    b.subtitulo("Equipo y herramientas utilizados")
    b.tabla(["Componente", "Detalle"], [
        ["CPU", f"{eq['cpu'].replace('12th Gen Intel(R) Core(TM)', 'Intel Core')} (12th Gen): "
                f"{eq['nucleos_fisicos']} núcleos, {eq['hilos_logicos']} hilos; RAM de "
                f"{n(eq['ram_gib'])} GB"],
        ["GPU", f"{gpu['nombre']}: capacidad de cómputo {gpu['capacidad_computo']}, "
                f"{gpu['memoria_mib']} MiB; se compila para {gpu['arquitectura_compilacion']} "
                "(coincide con la GPU)"],
        ["Sistema operativo", eq["so"]],
        ["CUDA y compilador", f"Toolkit 12.9 (nvcc V12.9.86), controlador 596.36 (CUDA "
                              f"{gpu['cuda_soportada_por_controlador']}), {ver['compilador_cl']} "
                              "(Visual Studio 2022). Flags: -O3 -arch=sm_86, sin --use_fast_math"],
        ["Python", f"Python {ver['python']} (64 bits), NumPy {ver['numpy']}, PyCUDA {ver['pycuda']} "
                   f"(compilado con CUDA {gpu['pycuda_compilado_con_cuda']}), Pillow {ver['pillow']}, "
                   f"Matplotlib {ver['matplotlib']}, pytest {ver['pytest']}"],
        ["Registro", "resultados/mediciones/entorno.json (generado por scripts/registrar_entorno.py)"],
    ], [92, 408], alinear=["l", "l"])
    b.subtitulo("Preparación del entorno")
    b.p("Se crea un entorno virtual con las versiones fijas de `requirements.txt`. PyCUDA llama a "
        "`nvcc`, que necesita `cl.exe`; `scripts/entorno_vs.bat` carga `vcvars64.bat` de Visual "
        "Studio 2022 antes de compilar, igual que `compilar.bat` de la práctica 01.")
    b.codigo(["py -3.12 -m venv .venv",
              'cmd /c "call scripts\\entorno_vs.bat && .venv\\Scripts\\python.exe -m pip install -r requirements.txt"',
              ".\\ejecutar_cuda.bat      :: C++ secuencial y CUDA C",
              ".\\ejecutar_pycuda.bat    :: Python secuencial y PyCUDA"])
    b.subtitulo("Imágenes de entrada")
    b.p("Se usan exactamente los archivos de la práctica 01: el recorte cuadrado central de la "
        "imagen original (8000×12000 px) redimensionado con Lanczos a 6000×6000, 4000×4000 y "
        "2000×2000, y la imagen de 1013×757 para la prueba de dimensiones no múltiplo. Su SHA-256 "
        "está registrado en `datos/hashes_p01.json` y el programa Python lo comprueba al iniciar; "
        "en todas las ejecuciones coincidió con el de la práctica 01. La imagen pequeña "
        "`base_250.pgm` se generó con el mismo procedimiento y solo se usa para validar Python "
        "secuencial.")
    b.rejilla_imagenes([(figs["prep"][0], "Original 8000×12000 (recorte en naranja)"),
                        (figs["prep"][1], "6000×6000"), (figs["prep"][2], "4000×4000"),
                        (figs["prep"][3], "2000×2000")], 4, 1.55)

    # --- 2. Migración y Python secuencial ----------------------------------
    b = marco.fila()
    b.titulo("2. Migrar el programa anfitrión e implementar Python secuencial.")
    b.p("Todo lo que en la práctica 01 hacía el programa anfitrión en C/C++ pasó a Python, "
        "conservando los nombres en español y la organización por módulos:")
    b.tabla(["Parte del programa", "Práctica 01 (C/C++)", "Práctica 02 (Python)"], [
        ["Inicio y orden de ejecución", "main.cu, src/experimentos.cu",
         "main.py, scripts/medir_python_pycuda.py"],
        ["Parámetros", "src/configuracion.h",
         "src/python/comun/configuracion.py (10 repeticiones, 2 s de calentamiento GPU, límite de 120 s)"],
        ["Lectura y escritura de imágenes", "src/imagenes.cpp (leerPGM, guardarPGM)",
         "src/python/comun/imagenes.py (leer_pgm, a_bytes_visibles, guardar_png)"],
        ["Máscaras", "src/filtros/*.cpp", "src/python/filtros/media.py, nitidez.py, laplaciano.py"],
        ["Convolución secuencial", "convolucionCPU (src/filtros.cu)",
         "convolucion_cpu (src/python/convolucion.py)"],
        ["Lanzamiento GPU y tiempos", "ejecutarGPU (src/filtros.cu)",
         "ejecutar_gpu (src/pycuda/convolucion.py)"],
        ["Contexto y compilación", "nvcc en compilar.bat",
         "src/pycuda/contexto_cuda.py (cuda.init, make_context, SourceModule)"],
        ["Pruebas y validación", "pruebaManual, pruebaNoMultiplo, compararCPUyGPU",
         "src/python/comun/experimentos.py, tests/ (pytest), comparar"],
        ["Kernel", "convolucionGPU en src/filtros.cu",
         "src/pycuda/kernels/convolucion.cu: mismo código, sin cambios de lógica"],
    ], [110, 160, 230], alinear=["l", "l", "l"])
    b.p("La convolución secuencial en Python es una traducción literal de `convolucionCPU`: cuatro "
        "bucles explícitos en el mismo orden (fila `y`, columna `x`, luego `j` externo e `i` "
        "interno). No se usa vectorización de NumPy, `scipy`, OpenCV, JIT, multiprocesamiento ni "
        "llamadas al código en C; NumPy solo almacena los arreglos y calcula los errores. Antes "
        "del recorrido la imagen y la máscara se pasan a listas de `np.float32`, de modo que cada "
        "producto y cada suma se redondean en 32 bits como el `float` de C:", antes=6)
    b.codigo(["# src/python/convolucion.py - convolucion_cpu",
              "radio = k // 2",
              "datos, coeficientes = list(entrada), list(mascara)   # escalares np.float32",
              "for y in range(alto):",
              "    if limite_segundos is not None and time.perf_counter() - inicio > limite_segundos:",
              "        raise TiempoExcedido(transcurrido, y, limite_segundos)  # filas procesadas = y",
              "    for x in range(ancho):",
              "        suma = np.float32(0)",
              "        for j in range(-radio, radio + 1):",
              "            for i in range(-radio, radio + 1):",
              "                yy, xx = y + j, x + i",
              "                if 0 <= yy < alto and 0 <= xx < ancho:       # extension con ceros",
              "                    suma += datos[yy * ancho + xx] * coeficientes[(j + radio) * k + i + radio]",
              "        salida[y * ancho + x] = suma                      # arreglo de salida separado"])
    b.p("El tiempo de Python se mide con `time.perf_counter()` alrededor de `convolucion_cpu`, sin "
        "leer ni guardar la imagen. Como Python secuencial es muy lento, cada ejecución tiene un "
        "límite configurable (`LIMITE_PYTHON_SEGUNDOS = 120`): al empezar cada fila se revisa el "
        "tiempo y, si se superó, la ejecución se aborta y se registran el tiempo transcurrido y "
        "las filas procesadas.")
    b.subtitulo("Condiciones comunes a las cuatro versiones")
    b.tabla(["Aspecto", "Condición aplicada"], [
        ["Datos", "La misma imagen en escala de grises (8 bits) convertida a float de 32 bits; las "
                  "cuatro versiones reciben el mismo arreglo y la misma máscara."],
        ["Tipo numérico", "float32 en entrada, máscara, acumulador y salida. En Python: arreglos "
                          "np.float32 y acumulador np.float32(0). La media usa 1.0f/(k·k) calculado "
                          "en float32; un test comprueba que las máscaras son idénticas bit a bit a las de C."],
        ["Bordes", "Extensión con ceros: si un vecino cae fuera de la imagen no se suma."],
        ["Arreglos", "La entrada nunca se sobrescribe; la salida va en un arreglo distinto."],
        ["Visualización", "Solo al guardar y después de validar: media y nitidez se recortan a "
                          "[0, 255]; el laplaciano se guarda como min(255, |v|·4), igual que guardarPGM."],
    ], [92, 408], alinear=["l", "l"])

    # --- 3. PyCUDA -----------------------------------------------------------
    b = marco.fila()
    b.titulo("3. Integrar y ejecutar los kernels con PyCUDA.")
    b.p("El kernel `convolucionGPU` se copió sin cambios de lógica a `src/pycuda/kernels/"
        "convolucion.cu`. Python lee ese archivo y lo compila con `SourceModule(codigo, "
        "options=[\"-O3\"], arch=\"sm_86\")`, los mismos flags de `compilar.bat` (sin "
        "`--use_fast_math`); `entorno.json` confirma que la GPU tiene capacidad 8.6. El contexto "
        "se crea a mano (`cuda.init()` y `Device(0).make_context()`) en lugar de `pycuda.autoinit`, "
        "para poder medirlo aparte. La distribución es la misma de la práctica 01: bloques e "
        "hilos solo en X, un píxel por hilo, `id = blockIdx.x · blockDim.x + threadIdx.x`, "
        "`if (id >= n) return;`, `y = id / ancho`, `x = id % ancho`, vecinos leídos de memoria "
        "global y `bloques = ⌈n / hilos⌉`.")
    b.codigo(["# src/pycuda/convolucion.py - ejecutar_gpu (memoria reservada antes con cuda.mem_alloc)",
              "bloques = (ancho * alto + hilos - 1) // hilos",
              "e = [cuda.Event() for _ in range(4)]",
              "e[0].record()",
              "cuda.memcpy_htod(d_entrada, entrada)            # imagen float32 contigua",
              "cuda.memcpy_htod(d_mascara, mascara)            # mascara float32",
              "e[1].record()",
              "kernel(d_entrada, d_salida, d_mascara, np.int32(ancho), np.int32(alto), np.int32(k),",
              "       block=(hilos, 1, 1), grid=(bloques, 1))",
              "e[2].record()",
              "cuda.memcpy_dtoh(salida, d_salida)",
              "e[3].record()",
              "e[3].synchronize()                              # esperar antes de leer los tiempos",
              "return e[0].time_till(e[1]), e[1].time_till(e[2]), e[2].time_till(e[3]), e[0].time_till(e[3])"])
    b.subtitulo("Tipos en NumPy y en el kernel")
    b.tabla(["Argumento", "Python (NumPy / PyCUDA)", "Kernel (CUDA C)", "Paso a la GPU"], [
        ["entrada", "np.float32, 1-D, C-contiguo (np.ascontiguousarray)", "const float*",
         "cuda.mem_alloc + memcpy_htod"],
        ["máscara", "np.float32, k·k valores", "const float*", "cuda.mem_alloc + memcpy_htod"],
        ["salida", "np.float32 (np.empty)", "float*", "cuda.mem_alloc; memcpy_dtoh al final"],
        ["ancho, alto, k", "np.int32", "int", "por valor"],
        ["block / grid", "(hilos, 1, 1) / (bloques, 1)", "blockDim.x / gridDim.x", "explícitos en la llamada"],
    ], [70, 170, 90, 170], alinear=["l", "l", "l", "l"])
    b.p("`ejecutar_gpu` rechaza cualquier arreglo que no sea `float32` o no sea contiguo, para que "
        "nunca se copie a la GPU un arreglo en `float64` por defecto.", antes=4)
    b.subtitulo("Bloques e hilos por configuración")
    filas_bloques = []
    for nombre, lado_x, lado_y, hilos_lista in (("2000×2000", 2000, 2000, (256,)),
                                                ("4000×4000", 4000, 4000, (128, 256, 512)),
                                                ("6000×6000", 6000, 6000, (256,)),
                                                ("1013×757", 1013, 757, (128, 256, 512))):
        px = lado_x * lado_y
        celdas = []
        for h in (128, 256, 512):
            if h not in hilos_lista:
                celdas.append("—")
                continue
            bl = (px + h - 1) // h
            sobra = bl * h - px
            celdas.append(f"{n(bl, 0)} bloques" + (f" (sobran {sobra})" if sobra else ""))
        filas_bloques.append([nombre, n(px, 0)] + celdas)
    b.tabla(["Imagen", "Píxeles (n)", "128 hilos/bloque", "256 hilos/bloque", "512 hilos/bloque"],
            filas_bloques, [80, 80, 113, 113, 114])
    b.subtitulo("Inicialización y compilación (medidas aparte)")
    b.p("La creación del contexto y la compilación o carga del kernel se hacen una sola vez por "
        "proceso y se registran en `inicializacion.csv`; no forman parte de ninguna medición del "
        "kernel ni del tiempo conjunto.")
    b.tabla(["Etapa", "Tiempo (ms)", "Caché", "Detalle"], [
        ["Contexto CUDA", n(ini["contexto"], 1), "—", "cuda.init + Device(0).make_context"],
        ["Compilación con nvcc", n(ini["compilacion_sin_cache"], 1), "no",
         "SourceModule sin caché: nvcc -O3 -arch=sm_86"],
        ["Carga del módulo", n(ini["carga_con_cache"], 1), "sí", "SourceModule con acierto de caché"],
        ["Obtener la función", n(ini["get_function"], 2), "—", "get_function(\"convolucionGPU\")"],
    ], [110, 70, 50, 270], alinear=["l", "r", "c", "l"])

    # --- 4. Validación -------------------------------------------------------
    b = marco.fila()
    b.titulo("4. Validar las cuatro versiones.")
    total_ok = (len(d.manual_c) + len(d.manual_py) + len(d.validacion_c) + len(d.validacion_py)
                + len(d.visual))
    b.p(f"Todas las pruebas terminaron en OK ({total_ok} filas en `prueba_manual*.csv`, "
        "`validacion*.csv` y `evidencia_visual.csv`). La referencia numérica es C++ secuencial. "
        f"Python secuencial coincide **exactamente** con C++ (error máximo "
        f"{e(err['python_secuencial']['max'])}) y PyCUDA coincide **exactamente** con CUDA C "
        f"({e(err['pycuda_vs_cuda_c']['max'])}). El mayor error de CUDA C y PyCUDA frente a C++ fue "
        f"{e(err['pycuda']['max'])}.")
    b.subtitulo("Prueba manual con una matriz pequeña")
    b.p("Se usa la matriz 5×5 de la Figura 1 de la guía, con los valores calculados a mano y la "
        "misma tolerancia de 1e-3 de la práctica 01. Por ejemplo, la media 3×3 en (2,2) es "
        "445/9 = 49,4444 y el laplaciano en la esquina (4,4) es (60 + 70 + 0 + 0) − 4·75 = −170.")
    manual = {}
    for f in d.manual_py:
        manual.setdefault((f["mascara"], f["fila"], f["columna"], f["esperado_manual"]), {})[f["version"]] = f
    nombres_m = {"figura1": "Figura 1", "media": "Media", "nitidez": "Nitidez", "laplaciano": "Laplaciano"}
    filas = []
    for (mascara, fila, col, esperado), vs in manual.items():
        filas.append([nombres_m[mascara], f"({fila}, {col})", n(float(esperado), 4)]
                     + [n(float(vs[v]["obtenido"]), 4) for v in ("cpp_secuencial", "cuda_c",
                                                                  "python_secuencial", "pycuda")]
                     + ["OK" if all(vs[v]["resultado"] == "OK" for v in vs) else "FALLA"])
    b.tabla(["Máscara", "Posición", "Valor a mano", "C++", "CUDA C", "Python", "PyCUDA", "Resultado"],
            filas, [70, 60, 66, 58, 58, 58, 58, 72],
            alinear=["l", "c", "r", "r", "r", "r", "r", "c"])
    b.subtitulo("Dimensiones no múltiplo del número de hilos por bloque")
    b.p("La imagen de 1013×757 (766.841 píxeles) no es múltiplo de 128, 256 ni 512, por lo que el "
        "último bloque queda incompleto. Para cada configuración se aplican cuatro filtros y se "
        "compara la salida completa con C++. Los hilos sobrantes salen por `id >= n` y los "
        "errores son los mismos que en las imágenes múltiplo. Python no usa hilos: se valida una "
        "vez por filtro.")
    val = {}
    for f in d.validacion_py:
        if f["prueba"] == "no_multiplo":
            val.setdefault((f["filtro"], f["mascara"], f["hilos_bloque"]), {})[(f["version"], f["referencia"])] = f
    py_nm = {(f["filtro"], f["mascara"]): f for f in d.validacion_py
             if f["prueba"] == "no_multiplo" and f["version"] == "python_secuencial"}
    filas = []
    for h in ("128", "256", "512"):
        bl = (766841 + int(h) - 1) // int(h)
        for filtro, k in (("media", "3"), ("nitidez", "3"), ("laplaciano", "3"), ("media", "9")):
            vs = val[(filtro, k, h)]
            filas.append([h, n(bl, 0), str(bl * int(h) - 766841), conf(filtro, int(k)),
                          e(float(vs[("cuda_c", "cpp_secuencial")]["error_max"])),
                          e(float(vs[("pycuda", "cpp_secuencial")]["error_max"])),
                          e(float(vs[("pycuda", "cuda_c")]["error_max"])),
                          e(float(py_nm[(filtro, k)]["error_max"])),
                          "OK" if all(v["resultado"] == "OK" for v in vs.values()) else "FALLA"])
    b.tabla(["Hilos/ bloque", "Bloques", "Sobran", "Filtro", "CUDA C vs C++",
             "PyCUDA vs C++", "PyCUDA vs CUDA C", "Python vs C++", "Resultado"],
            filas, [38, 42, 44, 70, 60, 60, 62, 60, 64],
            alinear=["c", "r", "r", "l", "r", "r", "r", "r", "c"], negrita_col0=False)
    b.subtitulo("Comparación numérica en los experimentos (error máximo y medio frente a C++)")
    b.p("Las salidas float completas se comparan antes de convertirlas a 0–255. Python secuencial "
        "tarda varios minutos en las configuraciones grandes, por eso se validó en 4000×4000 con "
        "los tres filtros 3×3 (`evidencia_visual.csv`) y en 250×250 con las cinco máscaras.")
    vis = {(f["version"], f["referencia"], f["filtro"]): f for f in d.visual}
    filas = []
    for f in d.validacion_py:
        if f["prueba"] not in ("experimento", "pequena") or f["referencia"] != "cpp_secuencial":
            continue
        if f["version"] != "cuda_c":
            continue
        clave = (f["filtro"], f["mascara"], f["ancho"], f["hilos_bloque"])
        pc = next(g for g in d.validacion_py if g["prueba"] == f["prueba"] and g["version"] == "pycuda"
                  and g["referencia"] == "cpp_secuencial" and
                  (g["filtro"], g["mascara"], g["ancho"], g["hilos_bloque"]) == clave)
        py = next((g for g in d.validacion_py if g["prueba"] == f["prueba"] and
                   g["version"] == "python_secuencial" and (g["filtro"], g["mascara"], g["ancho"]) ==
                   clave[:3]), None)
        if py is None and f["ancho"] == "4000" and f["mascara"] == "3":
            py = vis.get(("python_secuencial", "cpp_secuencial", f["filtro"]))
        filas.append([conf(f["filtro"], int(f["mascara"])), f"{f['ancho']}×{f['alto']}", f["hilos_bloque"],
                      f"{e(float(f['error_max']))} ({e(float(f['error_medio']))})",
                      f"{e(float(pc['error_max']))} ({e(float(pc['error_medio']))})",
                      f"{e(float(py['error_max']))}" if py else "no evaluado",
                      e(float(f["tolerancia"])),
                      "OK" if f["resultado"] == pc["resultado"] == "OK" and (py is None or py["resultado"] == "OK") else "FALLA"])
    b.tabla(["Filtro", "Imagen", "Hilos", "CUDA C: máx. (medio)", "PyCUDA: máx. (medio)",
             "Python: máx.", "Tolerancia", "Resultado"],
            filas, [72, 58, 34, 90, 90, 56, 52, 48], alinear=["l", "c", "c", "r", "r", "r", "r", "c"])
    b.subtitulo("Tolerancia y origen de las diferencias")
    b.p("La práctica 01 usó una tolerancia fija de 0,01. En esta práctica la tolerancia se deduce "
        "de la precisión float32: cada configuración usa la cota del error de una suma de n = k·k "
        "productos (Higham), |error| ≤ 2·γₙ·255·Σ|h|, con γₙ = n·u/(1 − n·u) y u = 2⁻²⁴ ≈ 5,96e-8 "
        "(la mitad de ε = 1,19e-7). 255·Σ|h| es la mayor magnitud posible de la suma parcial y el "
        "factor 2 cubre que ambas versiones redondean. Se obtiene 2,7e-4 para la media 3×3, "
        "2,5e-3 para la media 9×9 y la nitidez, 2,2e-3 para el laplaciano y 1,3e-2 para la media "
        "21×21. Todos los errores observados quedan por debajo de su cota; el más ajustado es la "
        "media 3×3 (6,1e-5 frente a 2,7e-4).")
    b.p("Python secuencial da error 0 porque hace las mismas operaciones que C++, en el mismo orden "
        "y con un redondeo float32 por operación. PyCUDA da error 0 frente a CUDA C porque ejecuta "
        "el mismo kernel compilado con los mismos flags. La diferencia GPU–CPU aparece solo en la "
        "media: 1/9, 1/81 y 1/441 no son exactos en binario y nvcc usa por defecto multiplicación "
        "y suma fusionadas (FMA, un solo redondeo), mientras que la CPU redondea dos veces. En "
        "nitidez y laplaciano los coeficientes y píxeles son enteros y todas las operaciones son "
        "exactas, por lo que el error es 0 en las cuatro versiones.")
    b.subtitulo("Evidencia visual de las cuatro versiones")
    b.p("Para cada filtro se muestran la imagen original y la salida de las cuatro versiones "
        "(`resultados/imagenes/*_4000_reducida.png` y `*_recorte.png`). La primera fila es la "
        "imagen completa de 4000×4000 reducida; como a ese tamaño el efecto de una máscara 3×3 "
        "casi no se aprecia, la segunda fila muestra un recorte de 600×600 píxeles a resolución "
        "completa de la zona marcada con el recuadro naranja. Las cuatro salidas se ven iguales, "
        "lo que concuerda con la comparación numérica.")
    descripciones = {"media": "Suaviza ligeramente la imagen.",
                     "nitidez": "Acentúa detalles y contornos.",
                     "laplaciano": "Muestra principalmente los bordes; se guarda como |v|·4 para hacerlos visibles."}
    versiones = (("cpp_secuencial", "C++"), ("cuda_c", "CUDA C"), ("python_secuencial", "Python"),
                 ("pycuda", "PyCUDA"))
    for filtro in ("media", "nitidez", "laplaciano"):
        items = [(figs["marcada"], "Original")]
        items += [(IMAGENES / f"{v}_{filtro}3_4000_reducida.png", nombre) for v, nombre in versiones]
        items += [(IMAGENES / "original_4000_recorte.png", "Recorte: original")]
        items += [(IMAGENES / f"{v}_{filtro}3_4000_recorte.png", f"Recorte: {nombre}")
                  for v, nombre in versiones]
        b.rejilla_imagenes(items, 5, 1.28, titulo=f"Filtro de {filtro} 3×3",
                           descripcion=descripciones[filtro])

    # --- 5. Diseño de experimentos -------------------------------------------
    b = marco.fila()
    b.titulo("5. Diseñar los experimentos y definir cómo se mide el rendimiento.")
    b.tabla(["Experimento", "Configuración", "Hilos por bloque", "Versiones"], [
        ["Filtro", "Media, nitidez y laplaciano 3×3; 4000×4000", "256", "Las cuatro"],
        ["Resolución", "Media 9×9; 2000, 4000 y 6000", "256", "Las cuatro"],
        ["Máscara", "Media 3×3, 9×9 y 21×21; 4000×4000", "256", "Las cuatro"],
        ["Hilos por bloque", "Media 9×9; 4000×4000", "128, 256, 512", "CUDA C y PyCUDA"],
    ], [80, 200, 90, 130], alinear=["l", "l", "c", "l"])
    b.p("Se modifica un factor a la vez; fuera del experimento de hilos se fijan 256 hilos por "
        "bloque y la cantidad de bloques se ajusta a la imagen. Las configuraciones repetidas "
        "entre experimentos (media 3×3 y media 9×9 a 4000×4000 con 256 hilos) se midieron una sola "
        "vez y se comparten. Python secuencial no depende de los hilos por bloque, por eso no "
        "participa en ese experimento.", antes=6)
    b.subtitulo("Medición del rendimiento")
    b.tabla(["Aspecto", "Procedimiento"], [
        ["Repeticiones", f"10 por configuración en C++, CUDA C y PyCUDA; 5 en Python secuencial "
                         "(mínimo de la guía), porque cada ejecución tarda de 27 a 50 s. Se reporta la "
                         "mediana, el rango intercuartílico (IQR = Q3 − Q1) y el coeficiente de "
                         "variación (CV = desviación estándar / media); las gráficas muestran la "
                         "mediana con la desviación estándar."],
        ["Calentamiento", "C++: 1 ejecución previa no registrada. CUDA C y PyCUDA: ejecuciones "
                          "completas no registradas durante 2 segundos, para medir con la GPU a "
                          "frecuencia de trabajo. Python secuencial: sin ejecución previa."],
        ["Medición CPU", "C++: std::chrono::steady_clock. Python: time.perf_counter(). Ambos solo "
                         "alrededor de la convolución, en milisegundos."],
        ["Medición GPU", "Cuatro eventos CUDA de PyCUDA (los mismos que en CUDA C) separan la copia "
                         "CPU→GPU (imagen y máscara), el kernel, la copia GPU→CPU y el tiempo "
                         "conjunto; e3.synchronize() espera a la GPU antes de leer los tiempos."],
        ["Alcance", "Se excluyen lectura y escritura de imágenes, conversión a 0–255 y "
                    "visualización. La reserva de memoria (mem_alloc) se hace una vez por "
                    "configuración, antes del calentamiento, y NO forma parte del tiempo "
                    "conjunto; el contexto y la compilación se miden aparte. Memoria del host "
                    "paginable en las dos versiones GPU."],
        ["Límite de Python", "120 s por ejecución. Si se alcanza, la configuración se marca como "
                             "«no completada» y se registran el tiempo transcurrido y las filas "
                             "procesadas. No se extrapola el tiempo total ni se calculan "
                             "aceleraciones con esas ejecuciones."],
        ["Aceleraciones", "De cómputo = mediana secuencial / mediana del kernel. Con transferencias "
                          "= mediana secuencial / mediana del tiempo conjunto GPU. CUDA C se compara "
                          "con C++ y PyCUDA con Python."],
        ["Registro", "mediciones.csv (C++ y CUDA C) y mediciones_python_pycuda.csv (Python y PyCUDA): "
                     "versión, estado, filtro, máscara, ancho, alto, hilos, repetición, t_h2d, "
                     "t_kernel, t_d2h, t_total (ms)."],
    ], [92, 408], alinear=["l", "l"])
    b.subtitulo("Viabilidad de Python secuencial")
    b.p("Primero se validó Python con imágenes de 250×250. En alta resolución completaron las cinco "
        f"repeticiones los tres filtros 3×3 a 4000×4000 ({n(min(r['py'].mediana for r in f3) / 1000)}–"
        f"{n(max(r['py'].mediana for r in f3) / 1000)} s) y la media 9×9 a 2000×2000 "
        f"({n(m9_2000['py'].mediana / 1000)} s). Las demás alcanzaron el límite en el primer intento:")
    filas = []
    for f in nc:
        filas.append([conf(f["filtro"], f["k"], f["lado"]), n(f["total"] / 1000, 1) + " s",
                      f"{n(f['filas_procesadas'], 0)} de {n(f['alto'], 0)}",
                      pct(100 * f["filas_procesadas"] / f["alto"]),
                      "Límite de 120 s alcanzado"])
    b.tabla(["Configuración", "Tiempo transcurrido", "Filas procesadas", "Avance", "Estado"],
            filas, [130, 90, 100, 60, 120], alinear=["l", "r", "r", "r", "l"])
    extra = [f for f in d.intentos_no_completados() if f not in nc]
    if extra:
        b.p("El script también ejecutó Python en las filas del experimento de hilos (128 y 512); "
            "como Python no usa hilos, son intentos repetidos de la media 9×9 a 4000×4000 "
            f"({', '.join(n(f['filas_procesadas'], 0) for f in extra)} filas en 120 s) y no se usan.",
            antes=4)
    b.p("Por eso la comparación de las cuatro versiones con tiempos completos se hace en los tres "
        "filtros 3×3 (4000×4000) y en la resolución menor común del experimento de resolución "
        "(2000×2000 con media 9×9). En 4000×4000 y 6000×6000 con media 9×9, y en la media 21×21, "
        "solo se reportan C++, CUDA C y PyCUDA.", antes=4)
    b.subtitulo("Origen de los resultados")
    b.p("Todos los tiempos de este informe son **nuevos** (13/11/2026, mismo equipo); no se "
        "reutilizó ningún tiempo de la práctica 01. Una primera corrida GPU se descartó: PyCUDA se "
        "calentaba con una sola ejecución y medía con la GPU todavía en reposo (CV de hasta 167 %), "
        "y CUDA C dio 4,66 ms en la media 9×9 a 4000×4000 con 256 hilos, frente a 1,876 ms en la "
        "práctica 01. Se agregó a PyCUDA el calentamiento de 2 s de la práctica 01 y se repitieron "
        "C++, CUDA C y PyCUDA; las filas de Python secuencial se conservaron porque no usan la "
        f"GPU. En la repetición, ese kernel tardó {n(m9_4000['cu_kernel'].mediana, 3)} ms. Los CSV "
        "descartados se guardan en `resultados/mediciones/corrida_descartada_2026-11-13/`.")

    # --- 6. Resultados -------------------------------------------------------
    b = marco.fila()
    b.titulo("6. Ejecutar los experimentos y presentar los resultados.")
    b.p("Todos los tiempos son **medianas en milisegundos** calculadas de los CSV (10 repeticiones; "
        "5 en Python); entre paréntesis va el IQR. «% transf.» es la parte del tiempo conjunto GPU "
        "que corresponde a copias (H2D + D2H), calculada en cada repetición. En las tablas de "
        "experimentos cada configuración tiene dos filas: CUDA C con su aceleración frente a C++, "
        "y PyCUDA con su aceleración frente a Python. La negrita marca la mejor aceleración de "
        "cada columna y versión.")
    b.subtitulo("Comparación directa de las cuatro versiones (imagen de 4000×4000, filtros 3×3)")
    filas = []
    for r in f3:
        filas.append([conf(r["filtro"], 3), n(r["cpp"].mediana), n(r["py"].mediana),
                      n(r["cu_kernel"].mediana, 3), n(r["cu_total"].mediana, 2),
                      n(r["pc_kernel"].mediana, 3), n(r["pc_total"].mediana, 2), "Sí"])
    b.tabla(["Filtro", "C++ secuencial", "Python secuencial", "CUDA C: kernel", "CUDA C: total",
             "PyCUDA: kernel", "PyCUDA: total", "¿Coinciden?"], filas,
            [70, 60, 66, 60, 60, 60, 60, 64], alinear=["l", "r", "r", "r", "r", "r", "r", "c"])
    b.p(f"Python secuencial tarda unos {n(min(r['py'].mediana for r in f3) / 1000)}–"
        f"{n(max(r['py'].mediana for r in f3) / 1000)} s, unas {n(min(py_cpp), 0)}–"
        f"{n(max(py_cpp), 0)} veces más que C++. Los kernels de CUDA C y PyCUDA tardan lo mismo "
        f"(unos {n(f3[0]['cu_kernel'].mediana, 2)} ms) y, con las copias, la GPU queda en unos "
        "15 ms en ambas versiones.", antes=6)
    b.subtitulo("Experimento Filtro (3×3, 4000×4000, 256 hilos/bloque)")
    tabla_experimento(b, d, EXP_FILTROS, ["Media 3×3", "Nitidez 3×3", "Laplaciano 3×3"])
    b.figura(figs["filtros"], 6.6, "Figura 1. Tiempos por filtro, comparacion_filtros.png (mediana; escala logarítmica; "
          "barras de error = desviación estándar).")
    b.subtitulo("Experimento Resolución (media 9×9, 256 hilos/bloque)")
    tabla_experimento(b, d, EXP_RESOLUCION, ["2000×2000", "4000×4000", "6000×6000"])
    b.figura(figs["resolucion"], 6.6, "Figura 2. Crecimiento del tiempo con la resolución, comparacion_resolucion.png. Las "
          "barras rayadas vacías indican que Python no terminó en 120 s (no son tiempos medidos).")
    b.subtitulo("Experimento Máscara (media, 4000×4000, 256 hilos/bloque)")
    tabla_experimento(b, d, EXP_MASCARA, ["Media 3×3", "Media 9×9", "Media 21×21"])
    b.figura(figs["mascaras"], 6.6, "Figura 3. Crecimiento del tiempo con el tamaño de la máscara, comparacion_mascaras.png "
          "(escala logarítmica; rayado = Python no completada).")
    b.subtitulo("Experimento Hilos por bloque (media 9×9, 4000×4000)")
    filas = []
    for r in hil:
        for pref, nombre in (("cu", "CUDA C"), ("pc", "PyCUDA")):
            k = r[f"{pref}_kernel"]
            filas.append([str(r["hilos"]) if pref == "cu" else "",
                          n(r["bloques"], 0) if pref == "cu" else "", nombre,
                          n(k.mediana, 3), n(k.q1, 3), n(k.q3, 3), n(k.iqr, 3), pct(100 * k.cv, 2),
                          n(k.minimo, 3), n(k.maximo, 3), n(r[f"{pref}_total"].mediana, 2)])
    b.tabla(["Hilos/ bloque", "Bloques", "Versión", "Kernel mediana", "Q1", "Q3", "IQR", "CV",
             "Mín.", "Máx.", "Total GPU"], filas, [38, 46, 50, 50, 42, 42, 40, 40, 42, 42, 48],
            alinear=["c", "r", "l", "r", "r", "r", "r", "r", "r", "r", "r"])
    b.figura(figs["hilos"], 6.6, "Figura 4. Kernel y tiempo conjunto GPU por hilos por bloque, comparacion_hilos.png "
          "(barras de error = desviación estándar).")
    b.subtitulo("Transferencias y aceleraciones")
    b.figura(figs["distribucion"], 6.6, "Figura 5. Reparto del tiempo GPU entre copias y kernel (4000×4000, 256 hilos), "
          "distribucion_tiempo_gpu.png.")
    b.figura(figs["aceleracion"], 6.6, "Figura 6. Aceleración solo kernel y con transferencias (256 hilos), aceleracion.png. "
          "PyCUDA solo se compara en las configuraciones en las que Python terminó.")
    b.subtitulo("CUDA C frente a PyCUDA (mismas condiciones)")
    filas = []
    for c in todas:
        r = cfg[c]
        filas.append([f"{conf(c[0], c[1])}, {c[2]}², {c[3]} h",
                      n(r["cu_kernel"].mediana, 3), n(r["pc_kernel"].mediana, 3),
                      dif(r['pc_vs_cu_kernel']),
                      n(r["cu_total"].mediana, 2), n(r["pc_total"].mediana, 2),
                      dif(r['pc_vs_cu_total'])])
    b.tabla(["Configuración", "Kernel CUDA C", "Kernel PyCUDA", "Dif. kernel", "Total CUDA C",
             "Total PyCUDA", "Dif. total"], filas, [150, 58, 58, 58, 58, 58, 60])
    b.figura(figs["cuda_pycuda"], 6.6, "Figura 7. Cociente PyCUDA / CUDA C de las medianas, cuda_c_vs_pycuda.png.")
    b.subtitulo("Python secuencial frente a C++ secuencial")
    filas = [[conf(c[0], c[1], c[2]), n(cfg[c]["cpp"].mediana), n(cfg[c]["py"].mediana),
              f"{n(100 * cfg[c]['py'].cv)} %", x(cfg[c]["py_vs_cpp"])] for c in completas]
    b.tabla(["Configuración", "C++ (ms)", "Python (ms)", "CV Python", "Python / C++"], filas,
            [160, 80, 90, 80, 90])

    # --- 7. Análisis -----------------------------------------------------------
    b = marco.fila()
    b.titulo("7. Analizar los resultados.")
    b.subtitulo("1. ¿Qué partes del programa se trasladaron a Python y qué partes del kernel se reutilizaron?")
    b.p("Se trasladó a Python todo el programa anfitrión: lectura y conversión de imágenes, "
        "creación de máscaras, selección del filtro, gestión de memoria y transferencias, "
        "configuración de bloques e hilos, medición con eventos, validación, CSV y guardado de "
        "resultados (tabla de la actividad 2). Del lado de la GPU se reutilizó el kernel "
        "`convolucionGPU` completo, sin cambios de lógica: el cálculo del índice global, la "
        "conversión a fila y columna, el control `id >= n`, la extensión con ceros y la lectura "
        "de vecinos en memoria global. Lo que cambia es quién lo compila (SourceModule en tiempo "
        "de ejecución en lugar de nvcc en compilar.bat) y cómo se pasan los argumentos (arreglos "
        "NumPy float32 contiguos y escalares np.int32).")
    b.subtitulo("2. ¿Las cuatro versiones producen resultados equivalentes?")
    b.p("Sí. Python secuencial reproduce a C++ bit a bit (error 0 en 1013×757, 250×250 y "
        "4000×4000) y PyCUDA reproduce a CUDA C bit a bit en todas las configuraciones. La única "
        f"diferencia es entre CPU y GPU en el filtro de media: hasta {e(err['pycuda']['max'])} de "
        f"error máximo y {e(err['pycuda']['medio_max'])} de error medio, por el uso de FMA en la "
        "GPU con coeficientes no exactos (1/9, 1/81, 1/441). Ese error es miles de veces menor que "
        "un nivel de gris y está por debajo de la cota de float32 de cada configuración. Nitidez y "
        "laplaciano coinciden exactamente en las cuatro versiones.")
    b.subtitulo("3. ¿Cómo influyen la resolución y la máscara en los tiempos de Python secuencial y PyCUDA?")
    pxs_py_2000 = 2000 * 2000 / (m9_2000["py"].mediana / 1000)
    nc_m9_4000 = d.no_completada("media", 9, 4000)
    nc_m21 = d.no_completada("media", 21, 4000)
    pxs_py_4000 = nc_m9_4000["filas_procesadas"] * 4000 / (nc_m9_4000["total"] / 1000)
    pxs_py_m3 = 4000 * 4000 / (m3["py"].mediana / 1000)
    pxs_py_m21 = nc_m21["filas_procesadas"] * 4000 / (nc_m21["total"] / 1000)
    b.p(f"**Python secuencial.** El trabajo por píxel es constante, así que el tiempo es "
        "proporcional al número de píxeles: con media 9×9 procesó "
        f"{n(pxs_py_2000 / 1000, 1)} mil píxeles por segundo a 2000×2000 (ejecución completa) y "
        f"{n(pxs_py_4000 / 1000, 1)} mil píxeles por segundo en las {n(nc_m9_4000['filas_procesadas'], 0)} "
        "filas que alcanzó a procesar a 4000×4000 antes del límite. Con la máscara el costo crece "
        "casi como k²: con media 3×3 procesó "
        f"{n(pxs_py_m3 / 1000, 0)} mil píxeles por segundo y con 21×21 "
        f"{n(pxs_py_m21 / 1000, 1)} mil ({n(pxs_py_m3 / pxs_py_m21, 0)} veces menos para 49 veces "
        f"más coeficientes), mientras que C++ creció solo ×{n(m21['cpp'].mediana / m3['cpp'].mediana)}. "
        "En Python cada producto pasa por el intérprete, de modo que el costo fijo por píxel pesa "
        "poco y domina el número de operaciones. Por eso 4000×4000 y 6000×6000 con media 9×9 y la "
        "media 21×21 superaron los 120 s (estos ritmos describen lo medido; no se usan para "
        "estimar tiempos totales).")
    b.p(f"**PyCUDA.** De 2000² a 6000² (×9 píxeles) el kernel creció "
        f"×{n(m9_6000['pc_kernel'].mediana / m9_2000['pc_kernel'].mediana, 2)} "
        f"({n(m9_2000['pc_kernel'].mediana, 3)} → {n(m9_6000['pc_kernel'].mediana, 3)} ms), casi "
        f"igual que CUDA C (×{n(m9_6000['cu_kernel'].mediana / m9_2000['cu_kernel'].mediana, 2)}), "
        f"y el tiempo conjunto ×{n(m9_6000['pc_total'].mediana / m9_2000['pc_total'].mediana, 1)}, "
        "porque las copias crecen con los bytes (de 16 a 144 MB por sentido). De 3×3 a 21×21 "
        f"(×49 coeficientes) el kernel creció ×{n(m21['pc_kernel'].mediana / m3['pc_kernel'].mediana, 1)} "
        f"y el tiempo conjunto solo ×{n(m21['pc_total'].mediana / m3['pc_total'].mediana, 2)}, "
        "porque las copias no dependen de k. Al crecer el trabajo por píxel la GPU amortiza mejor "
        f"las copias: la parte de transferencias baja de {pct(m3['pc_pct_transf'])} (3×3) a "
        f"{pct(m21['pc_pct_transf'])} (21×21).")
    b.subtitulo("4. ¿Qué diferencias existen entre CUDA C y PyCUDA al medir únicamente el kernel y al "
                "incluir transferencias y gestión desde el host?")
    b.p(f"**Solo kernel:** PyCUDA tardó entre {n((min(rk) - 1) * 100)} % y "
        f"{n((max(rk) - 1) * 100)} % más que CUDA C. Es el mismo código máquina (mismo kernel, "
        "mismos flags), así que lo esperado es el mismo tiempo. La mayor diferencia aparece en el "
        f"kernel más corto (media 9×9 a 2000×2000: {n(m9_2000['cu_kernel'].mediana, 3)} frente a "
        f"{n(m9_2000['pc_kernel'].mediana, 3)} ms). Una posible explicación, no comprobada, es que "
        "el evento e1 se registra antes de que Python termine de preparar la llamada, por lo que el "
        "intervalo del kernel incluye unos microsegundos de lanzamiento desde el intérprete.")
    b.p(f"**Con transferencias:** el cociente PyCUDA / CUDA C del tiempo conjunto va de "
        f"{n(min(rt), 2)} a {n(max(rt), 2)}, en ambos sentidos. Las copias desde memoria paginable "
        "dominan ese tiempo y varían de una ejecución a otra (IQR de hasta "
        f"{n(max(cfg[c]['pc_total'].iqr for c in todas), 2)} ms), por lo que estas diferencias no "
        "indican que una versión copie más rápido que la otra: ambas usan la misma copia del "
        "controlador.")
    b.p(f"**Gestión desde el host:** lo que sí agrega Python ocurre fuera de las mediciones. Crear "
        f"el contexto costó {n(ini['contexto'], 1)} ms y compilar el kernel con nvcc "
        f"{n(ini['compilacion_sin_cache'], 1)} ms; con la caché de PyCUDA la carga bajó a "
        f"{n(ini['carga_con_cache'], 1)} ms. En CUDA C la compilación ocurre antes, con "
        "compilar.bat. Además, Python secuencial es "
        f"{n(min(py_cpp), 0)}–{n(max(py_cpp), 0)} veces más lento que C++, de modo que la "
        f"aceleración de PyCUDA frente a Python ({n(min(acel_pc_k), 0)}× a {n(max(acel_pc_k), 0)}× "
        f"en el kernel) es mucho mayor que la de CUDA C frente a C++ ({n(min(acel_cu_k), 0)}× a "
        f"{n(max(acel_cu_k), 0)}×) aunque la GPU haga exactamente el mismo trabajo: la diferencia "
        "está en la referencia secuencial, no en la GPU.")
    b.subtitulo("5. ¿Qué configuración de hilos por bloque obtuvo mejores resultados y con qué variabilidad?")
    mejor_cu = min(hil, key=lambda r: r["cu_kernel"].mediana)
    mejor_pc = min(hil, key=lambda r: r["pc_kernel"].mediana)
    peor_cu = max(hil, key=lambda r: r["cu_kernel"].mediana)
    b.p(f"Con media 9×9 a 4000×4000 la menor mediana del kernel se obtuvo con "
        f"{mejor_cu['hilos']} hilos por bloque en CUDA C ({n(mejor_cu['cu_kernel'].mediana, 3)} ms) "
        f"y con {mejor_pc['hilos']} en PyCUDA ({n(mejor_pc['pc_kernel'].mediana, 3)} ms). La "
        f"diferencia con la más lenta ({peor_cu['hilos']} hilos en CUDA C, "
        f"{n(peor_cu['cu_kernel'].mediana, 3)} ms) es de solo "
        f"{n((peor_cu['cu_kernel'].mediana / mejor_cu['cu_kernel'].mediana - 1) * 100)} %. La "
        "variabilidad es muy baja: CV de "
        f"{n(100 * max(r[p + '_kernel'].cv for r in hil for p in ('cu', 'pc')), 2)} % como máximo e "
        f"IQR de {n(max(r[p + '_kernel'].iqr for r in hil for p in ('cu', 'pc')), 3)} ms o menos. "
        "Las tres configuraciones llenan un SM de la RTX 3070 (1536 hilos: 12, 6 o 3 bloques), por "
        "lo que la elección casi no influye; en el tiempo conjunto las diferencias desaparecen "
        f"({', '.join(n(r['pc_total'].mediana, 2) for r in hil)} ms en PyCUDA) porque dominan las copias.")
    b.subtitulo("6. ¿Qué limitaciones del equipo o del procedimiento afectan las conclusiones?")
    b.vinetas([
        "Un solo equipo (i9-12900K con un núcleo para las versiones secuenciales y RTX 3070); los "
        "resultados no se pueden generalizar a otras CPU o GPU.",
        "Python secuencial solo completó 4 de las 7 configuraciones con tiempo; la media 9×9 a "
        "4000² y 6000² y la media 21×21 quedaron «no completadas», así que en el experimento de "
        "máscara no hay aceleración PyCUDA frente a Python para 9×9 y 21×21.",
        "Python secuencial se midió con 5 repeticiones y sin ejecución de calentamiento; las demás "
        f"versiones con 10. Aun así su CV fue bajo ({n(min(100 * cfg[c]['py'].cv for c in completas))}–"
        f"{n(max(100 * cfg[c]['py'].cv for c in completas))} %).",
        "Las filas de Python provienen de la primera corrida y las de C++, CUDA C y PyCUDA de la "
        "repetición del mismo día, con el mismo equipo, datos y código de medición.",
        "Memoria del host paginable y solo memoria global en el kernel; Windows (WDDM) gestiona la "
        "energía de la GPU, por lo que sin calentamiento suficiente los tiempos suben mucho (corrida "
        "descartada).",
        "Las mediciones se hicieron con cambios sin commit en el árbol de trabajo (entorno.json); el "
        "commit evaluado debe contener exactamente este código y estos CSV.",
    ])
    b.subtitulo("¿Qué resultados confirman o contradicen las expectativas iniciales?")
    b.tabla(["Resultado", "Observación"], [
        ["Confirma", "Las cuatro versiones dan el mismo resultado: Python = C++ y PyCUDA = CUDA C bit "
                     "a bit; la diferencia CPU–GPU es solo de redondeo."],
        ["Confirma", f"PyCUDA ejecuta el kernel tan rápido como CUDA C (diferencias de "
                     f"{n((min(rk) - 1) * 100)}–{n((max(rk) - 1) * 100)} %), porque es el mismo código en la "
                     "misma GPU."],
        ["Confirma", f"El tiempo crece de forma lineal con los píxeles: ×"
                     f"{n(m9_6000['cpp'].mediana / m9_2000['cpp'].mediana, 2)} en C++ y ×"
                     f"{n(m9_6000['pc_kernel'].mediana / m9_2000['pc_kernel'].mediana, 2)} en el kernel "
                     "PyCUDA para ×9 píxeles."],
        ["Matiza", f"Python secuencial es {n(min(py_cpp), 0)}–{n(max(py_cpp), 0)} veces más lento que "
                   "C++ con el mismo algoritmo; la diferencia es del lenguaje y su intérprete, no del "
                   "algoritmo."],
        ["Matiza", f"La aceleración de PyCUDA frente a Python ({n(min(acel_pc_k), 0)}×–{n(max(acel_pc_k), 0)}× "
                   "en el kernel) es enorme, pero se debe a lo lento de la referencia en Python."],
        ["Contradice", f"Las copias por PCIe pesan más que el kernel en casi todas las configuraciones "
                       f"({pct(min(transf), 0)}–{pct(max(transf), 0)} del tiempo GPU); con transferencias "
                       f"la ventaja de CUDA C cae a {n(min(acel_cu_t), 1)}×–{n(max(acel_cu_t), 1)}×."],
    ], [70, 430], alinear=["l", "l"])

    # --- 8. Contribuciones ---------------------------------------------------
    b = marco.fila()
    b.titulo("8. Documentar las contribuciones de los integrantes.")
    b.p("[[PENDIENTE: marcar con X quién realizó cada actividad antes de entregar.]]",
        alinear=WD_ALIGN_PARAGRAPH.LEFT)
    actividades = ["Revisión de la práctica 01 y preparación del entorno Python/PyCUDA",
                   "Migración del programa anfitrión (imágenes, máscaras, CSV)",
                   "Convolución secuencial en Python y límite de tiempo",
                   "Integración del kernel con PyCUDA (memoria, tipos, eventos)",
                   "Pruebas de corrección (manual, no múltiplo, cuatro versiones)",
                   "Ejecución de experimentos y CSV",
                   "Análisis, gráficas, informe y presentación",
                   "README y repositorio"]
    b.tabla(["Actividad", "J. Guillén", "A. Solano"], [[a, "", ""] for a in actividades],
            [320, 90, 90], alinear=["l", "c", "c"], negrita_col0=False)

    # --- Resultados, conclusiones, recomendaciones, referencias --------------
    b = marco.fila()
    b.p("**RESULTADO(S) OBTENIDO(S):**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Python secuencial y PyCUDA ejecutan los tres filtros; el kernel propio de la práctica 01 se "
        "compila y lanza desde Python con tipos, transferencias, bloques y límites explícitos.",
        f"Las cuatro versiones son equivalentes: Python = C++ y PyCUDA = CUDA C bit a bit; la mayor "
        f"diferencia CPU–GPU fue {e(err['pycuda']['max'])}, dentro de la cota de float32.",
        f"El kernel de PyCUDA tarda lo mismo que el de CUDA C ({n((min(rk) - 1) * 100)}–"
        f"{n((max(rk) - 1) * 100)} % de diferencia); compilar el kernel cuesta "
        f"{n(ini['compilacion_sin_cache'], 0)} ms la primera vez y {n(ini['carga_con_cache'], 1)} ms con caché.",
        f"Aceleración frente a la versión secuencial de su lenguaje: CUDA C {n(min(acel_cu_k), 0)}×–"
        f"{n(max(acel_cu_k), 0)}× (kernel) y {n(min(acel_cu_t), 1)}×–{n(max(acel_cu_t), 1)}× (con copias); "
        f"PyCUDA {n(min(acel_pc_k), 0)}×–{n(max(acel_pc_k), 0)}× y {n(min(acel_pc_t), 0)}×–"
        f"{n(max(acel_pc_t), 0)}×.",
        f"Las copias CPU↔GPU ocupan entre el {pct(min(transf), 0)} y el {pct(max(transf), 0)} del "
        "tiempo GPU; 128, 256 y 512 hilos por bloque dan prácticamente el mismo tiempo.",
        "Python secuencial no terminó en 120 s tres configuraciones; quedaron registradas como «no "
        "completadas», sin estimaciones."])
    b = marco.fila()
    b.p("**CONCLUSIONES:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Al gestionar la ejecución desde Python cambia el programa anfitrión (memoria, tipos, "
        "compilación en tiempo de ejecución y medición), pero en la GPU se conserva todo: el mismo "
        "kernel, la misma distribución de hilos y el mismo resultado numérico.",
        "Una vez compilado, el kernel lanzado desde PyCUDA rinde igual que desde CUDA C; el costo "
        "propio de Python está en crear el contexto y compilar, que se paga una sola vez.",
        "La gran aceleración de PyCUDA frente a Python se explica sobre todo por la lentitud del "
        "intérprete en bucles explícitos: Python secuencial es unas 210–280 veces más lento que C++.",
        "Como en la práctica 01, las transferencias por PCIe dominan el tiempo de GPU con máscaras "
        "pequeñas; las máscaras grandes amortizan mejor las copias.",
        "Para medir bien la GPU es indispensable calentarla: con una sola ejecución previa el "
        "kernel de PyCUDA llegó a tardar 8,83 ms en lugar de 0,42 ms y la corrida se tuvo que "
        "repetir."])
    b = marco.fila()
    b.p("**RECOMENDACIONES:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "Completar la comparación de máscaras de las cuatro versiones en una resolución menor común "
        "(por ejemplo, 1000×1000), donde Python termine también con 9×9 y 21×21.",
        "Calentar Python secuencial con una ejecución previa y aumentar sus repeticiones a 10 cuando "
        "el tiempo de laboratorio lo permita.",
        "Usar memoria del host fijada (pagelocked) en PyCUDA para reducir y estabilizar las copias.",
        "Registrar el commit y medir con el árbol de trabajo limpio, para que el código entregado "
        "corresponda exactamente a las mediciones.",
        "Comenzar siempre con entradas pequeñas y comprobar tipos (float32, int32), contigüidad y "
        "sincronización antes de medir."])
    b = marco.fila()
    b.p("**REFERENCIAS:**", alinear=WD_ALIGN_PARAGRAPH.LEFT, despues=3)
    b.vinetas([
        "NVIDIA. CUDA C++ Programming Guide (v12.9) y CUDA Runtime API: Event Management.",
        "A. Klöckner et al. PyCUDA documentation: tutorial, Device Interface y pycuda.compiler.SourceModule.",
        "R. C. Gonzalez y R. E. Woods. Digital Image Processing, 4.ª ed., Pearson, 2018 (filtrado espacial, cap. 3).",
        "N. J. Higham. Accuracy and Stability of Numerical Algorithms, 2.ª ed., SIAM, 2002 (error de sumas en punto flotante).",
        "Guías de las prácticas 01 y 02, Computación Paralela, UPS (G. A. León Paredes)."],
        alinear=WD_ALIGN_PARAGRAPH.LEFT)

    # --- Firmas ----------------------------------------------------------------
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
        if "izquierda" in firmas:
            par.add_run().add_picture(io.BytesIO(firmas["izquierda"]), height=Pt(95))
        if "derecha" in firmas:
            par.add_run().add_picture(io.BytesIO(firmas["derecha"]), height=Pt(95))
    return doc


def generar_figuras(d):
    return {
        "prep": figuras_preparacion(),
        "marcada": FIGURAS / "original_4000_marcada.png",
        "filtros": figura_comparacion(d, "comparacion_filtros.png",
                                      "Comparación de filtros en una imagen de 4000×4000",
                                      EXP_FILTROS, ["Media 3×3", "Nitidez 3×3", "Laplaciano 3×3"]),
        "resolucion": figura_comparacion(d, "comparacion_resolucion.png",
                                         "Efecto de la resolución con filtro de media 9×9",
                                         EXP_RESOLUCION, ["2000×2000", "4000×4000", "6000×6000"]),
        "mascaras": figura_comparacion(d, "comparacion_mascaras.png",
                                       "Efecto del tamaño de máscara (media, 4000×4000)",
                                       EXP_MASCARA, ["Media 3×3", "Media 9×9", "Media 21×21"]),
        "hilos": figura_hilos(d),
        "distribucion": figura_distribucion(d),
        "aceleracion": figura_aceleracion(d),
        "cuda_pycuda": figura_cuda_vs_pycuda(d),
    }


def main():
    d = Datos()
    if not d.visual:
        raise SystemExit("Falta resultados/pruebas/evidencia_visual.csv: ejecute scripts.evidencia_visual")
    figs = generar_figuras(d)
    logo, firmas = recursos_guia()
    doc = construir(d, logo, firmas, figs)
    doc.core_properties.title = "Práctica 02: Convolución de imágenes mediante PyCUDA"
    doc.core_properties.author = "Juan Alberto Guillén; Ariel Solano"
    doc.save(SALIDA)
    print(f"Informe: {SALIDA}")


if __name__ == "__main__":
    main()
