"""Formato UPS (GUIA-PRL-001) para el informe, reutilizado del generador de la práctica 02."""
import io
import re
from pathlib import Path

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# Logotipo UPS (versionado) y firmas escaneadas (fuera de Git, ver .gitignore de la raíz).
RECURSOS = Path(__file__).resolve().parents[1] / "informe" / "recursos"
FUENTE = "Arial"
CODIGO = "Consolas"
GRIS = "D9D9D9"
BORDE = "808080"
NUMERO_PRACTICA = "3"
TITULO_PRACTICA = ("Desarrollo y despliegue de un servicio web de convolución de imágenes "
                   "con Docker y PyCUDA")


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


ETIQUETA_FILTRO = {"media": "Media", "nitidez": "Nitidez", "laplaciano": "Laplaciano"}


def conf(filtro, k, lado=None):
    texto = f"{ETIQUETA_FILTRO[filtro]} {k}×{k}"
    return texto if lado is None else f"{texto}, {lado}×{lado}"


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------


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
    """Logotipo UPS y firmas desde informe/recursos/.

    Si faltan las firmas (copia del repositorio), el informe deja el espacio para firmar a mano.
    """
    logo = io.BytesIO((RECURSOS / "logo_ups.png").read_bytes())
    firmas = {}
    for lado in ("izquierda", "derecha"):
        ruta = RECURSOS / "firmas" / f"{lado}.png"
        if ruta.exists():
            firmas[lado] = ruta.read_bytes()
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
        texto_rico(par, NUMERO_PRACTICA, 11)
        celda = f2.cells[2].merge(f2.cells[3])
        texto_rico(celda.paragraphs[0], f"**TÍTULO PRÁCTICA**: {TITULO_PRACTICA}", 11)
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


