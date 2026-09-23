"""
Generación del PDF de una factura o un presupuesto.

Sustituye a `generar_factura_pdf`, que vivía dentro de `ui/homePage.py` y
dibujaba con coordenadas absolutas restando 20 puntos por línea. A partir de
unos 25 conceptos la coordenada se volvía negativa y el texto se dibujaba
fuera del papel: se perdían conceptos y el cuadro de totales, y la aplicación
decía «PDF generado correctamente» (defecto 02 de la auditoría).

Aquí se usa `platypus`, que maqueta con flujo: la tabla se parte sola entre
páginas, repite su cabecera y nunca se sale del margen.

El módulo no importa Qt ni sqlite3. Recibe un diccionario de datos y escribe
un fichero, así que se puede probar sin pantalla y sin base de datos.

Estructura del diccionario:

    {
      "tipo":     "factura" | "presupuesto",
      "numero":   "2025-004",
      "fecha":    "14/02/2025",
      "vencimiento": "16/03/2025",     # opcional (facturas)
      "validez":     "19/09/2025",     # opcional (presupuestos)
      "emisor":   {"nombre", "nif", "direccion", "poblacion", "telefono", "email"},
      "cliente":  {"nombre", "nif", "direccion", "poblacion", "telefono", "email"},
      "lineas":   [core.taxes.Linea, ...],
      "nota":     "Forma de pago: …",  # opcional
    }
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.taxes import calcular, formatear

# Monocromo, como la plantilla aprobada: imprime igual de bien en una
# impresora en blanco y negro y no compite con el contenido.
TINTA = colors.HexColor("#0A0A0B")
GRIS = colors.HexColor("#5A5A5A")
GRIS_CLARO = colors.HexColor("#8A8A8A")
FILETE = colors.HexColor("#E8E8E4")

# Helvetica es una de las catorce fuentes que todo lector de PDF trae de
# serie, así que el documento se ve igual en cualquier ordenador sin
# empaquetar nada. La tipografía matricial del diseño llegará cuando se
# incruste el fichero de la fuente.
FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"

MARGEN = 18 * mm


def _texto(valor):
    """
    Pasa un valor de la base a texto presentable.

    Los códigos postales y los teléfonos están declarados `REAL` en el
    esquema actual, así que SQLite devuelve 28001.0 y 612345678.0. Sin esto,
    el PDF imprime «CP: 28001.0» (defecto 04). La migración 001 de la fase 2
    arregla el origen; esto evita que se siga viendo mientras tanto.
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _estilos():
    base = ParagraphStyle(
        "base", fontName=FUENTE, fontSize=8.5, leading=11.5, textColor=TINTA
    )
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base, fontName=FUENTE_NEGRITA, fontSize=22, leading=24
        ),
        "meta": ParagraphStyle(
            "meta", parent=base, fontSize=8, leading=12, alignment=TA_RIGHT, textColor=GRIS
        ),
        "meta_dato": ParagraphStyle(
            "meta_dato", parent=base, fontName=FUENTE_NEGRITA, fontSize=8.5, alignment=TA_RIGHT
        ),
        "banda": ParagraphStyle(
            "banda", parent=base, fontSize=6.5, leading=9, textColor=GRIS_CLARO
        ),
        "banda_der": ParagraphStyle(
            "banda_der", parent=base, fontSize=6.5, leading=9,
            textColor=GRIS_CLARO, alignment=TA_RIGHT,
        ),
        "etiqueta": ParagraphStyle(
            "etiqueta", parent=base, fontSize=6.5, leading=10, textColor=GRIS_CLARO
        ),
        "parte": ParagraphStyle("parte", parent=base, fontSize=8.5, leading=11.5, textColor=GRIS),
        "parte_nombre": ParagraphStyle(
            "parte_nombre", parent=base, fontName=FUENTE_NEGRITA, fontSize=9.5, leading=13
        ),
        "th": ParagraphStyle(
            "th", parent=base, fontSize=6.5, leading=9, textColor=GRIS_CLARO
        ),
        "th_der": ParagraphStyle(
            "th_der", parent=base, fontSize=6.5, leading=9,
            textColor=GRIS_CLARO, alignment=TA_RIGHT,
        ),
        "concepto": ParagraphStyle("concepto", parent=base, fontSize=8.5, leading=11.5),
        "celda_der": ParagraphStyle("celda_der", parent=base, fontSize=8.5, alignment=TA_RIGHT),
        "total_etq": ParagraphStyle("total_etq", parent=base, fontSize=8, textColor=GRIS),
        "total_val": ParagraphStyle("total_val", parent=base, fontSize=8, alignment=TA_RIGHT, textColor=GRIS),
        "total_final_etq": ParagraphStyle(
            "tfe", parent=base, fontSize=7, textColor=TINTA
        ),
        "total_final_val": ParagraphStyle(
            "tfv", parent=base, fontName=FUENTE_NEGRITA, fontSize=15,
            leading=18, alignment=TA_RIGHT,
        ),
        "nota": ParagraphStyle("nota", parent=base, fontSize=7.5, leading=11, textColor=GRIS),
    }


class _LienzoNumerado(rl_canvas.Canvas):
    """
    Lienzo que sabe cuántas páginas tiene el documento terminado.

    Para escribir «Página 1 de 3» hay que conocer el total, que no se sabe
    hasta haber maquetado todo. Se guardan los estados de página y se pinta
    el pie al final, cuando ya se conoce el número.
    """

    def __init__(self, *args, referencia="", **kwargs):
        super().__init__(*args, **kwargs)
        self.referencia = referencia
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._pie(total)
            super().showPage()
        super().save()

    def _pie(self, total):
        ancho, _ = self._pagesize
        y = MARGEN - 6 * mm
        self.setStrokeColor(FILETE)
        self.setLineWidth(0.5)
        self.line(MARGEN, y + 4 * mm, ancho - MARGEN, y + 4 * mm)
        self.setFont(FUENTE, 6.5)
        self.setFillColor(GRIS_CLARO)
        self.drawString(MARGEN, y, self.referencia)
        self.drawRightString(
            ancho - MARGEN, y, f"Página {self._pageNumber} de {total}"
        )


def _cabecera(datos, est):
    """Rótulo del documento a la izquierda y sus datos a la derecha."""
    es_presupuesto = datos.get("tipo", "factura") == "presupuesto"
    rotulo = "PRESUPUESTO" if es_presupuesto else "FACTURA"

    filas_meta = [("Nº", datos.get("numero", "")), ("Fecha", datos.get("fecha", ""))]
    if es_presupuesto and datos.get("validez"):
        filas_meta.append(("Validez", datos["validez"]))
    elif datos.get("vencimiento"):
        filas_meta.append(("Vence", datos["vencimiento"]))

    meta = Table(
        [
            [Paragraph(etiqueta, est["meta"]), Paragraph(_texto(valor), est["meta_dato"])]
            for etiqueta, valor in filas_meta
        ],
        colWidths=[18 * mm, 32 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )

    return Table(
        [[Paragraph(rotulo, est["titulo"]), meta]],
        colWidths=[None, 50 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "TOP"),
                ("VALIGN", (1, 0), (1, 0), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def _banda(datos, est):
    """Línea de contexto bajo el filete: serie a la izquierda, plazo a la derecha."""
    es_presupuesto = datos.get("tipo", "factura") == "presupuesto"
    if es_presupuesto:
        izquierda = "PRESUPUESTO SIN VALOR CONTABLE"
        derecha = f"VÁLIDO HASTA {_texto(datos.get('validez', '')).upper()}" if datos.get("validez") else ""
    else:
        izquierda = f"FACTURA {_texto(datos.get('numero', '')).upper()}"
        derecha = f"VENCIMIENTO {_texto(datos.get('vencimiento', '')).upper()}" if datos.get("vencimiento") else ""

    return Table(
        [[Paragraph(izquierda, est["banda"]), Paragraph(derecha, est["banda_der"])]],
        colWidths=[None, 70 * mm],
        style=TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def _bloque_parte(etiqueta, parte, est):
    lineas = [Paragraph(etiqueta.upper(), est["etiqueta"])]
    lineas.append(Paragraph(_texto(parte.get("nombre", "")), est["parte_nombre"]))
    detalles = []
    if parte.get("nif"):
        detalles.append(_texto(parte["nif"]))
    for clave in ("direccion", "poblacion"):
        if parte.get(clave):
            detalles.append(_texto(parte[clave]))
    contacto = " · ".join(
        _texto(parte[c]) for c in ("telefono", "email") if parte.get(c)
    )
    if contacto:
        detalles.append(contacto)
    if detalles:
        lineas.append(Paragraph("<br/>".join(detalles), est["parte"]))
    return lineas


def _partes(datos, est):
    """Emisor a la izquierda y cliente a la derecha, en la misma fila."""
    izquierda = _bloque_parte("Emisor", datos.get("emisor", {}), est)
    derecha = _bloque_parte("Cliente", datos.get("cliente", {}), est)
    return Table(
        [[izquierda, derecha]],
        colWidths=["50%", "50%"],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.9, TINTA),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 10),
            ]
        ),
    )


def _tabla_conceptos(lineas, est, ancho):
    """
    Tabla de conceptos que se parte sola entre páginas.

    `repeatRows=1` hace que la cabecera se repita arriba de cada página, que
    es lo que impedía leer la segunda hoja de una factura larga.
    """
    cabecera = [
        Paragraph("CONCEPTO", est["th"]),
        Paragraph("CANT.", est["th_der"]),
        Paragraph("PRECIO", est["th_der"]),
        Paragraph("IMPORTE", est["th_der"]),
    ]

    filas = [cabecera]
    for linea in lineas:
        cantidad = linea.cantidad
        cantidad_txt = f"{cantidad.normalize():f}" if cantidad == cantidad.to_integral() else formatear(cantidad)
        filas.append(
            [
                Paragraph(linea.descripcion or "", est["concepto"]),
                Paragraph(f"{cantidad_txt} {linea.unidad}".strip(), est["celda_der"]),
                Paragraph(formatear(linea.precio_ud), est["celda_der"]),
                Paragraph(formatear(linea.importe), est["celda_der"]),
            ]
        )

    anchos = [ancho - (62 * mm), 18 * mm, 21 * mm, 23 * mm]
    return Table(
        filas,
        colWidths=anchos,
        repeatRows=1,
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, TINTA),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, FILETE),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ]
        ),
    )


def _tabla_totales(totales, est):
    filas = [
        [Paragraph("Base imponible", est["total_etq"]),
         Paragraph(f"{formatear(totales.base)} €", est["total_val"])],
    ]
    for tramo in totales.desglose:
        etiqueta = f"IVA {formatear(tramo.tipo).rstrip('0').rstrip(',')} %"
        if len(totales.desglose) > 1:
            etiqueta += f" (sobre {formatear(tramo.base)} €)"
        filas.append(
            [Paragraph(etiqueta, est["total_etq"]),
             Paragraph(f"{formatear(tramo.cuota)} €", est["total_val"])]
        )
    filas.append(
        [Paragraph("TOTAL", est["total_final_etq"]),
         Paragraph(f"{formatear(totales.total)} €", est["total_final_val"])]
    )

    ultima = len(filas) - 1
    return Table(
        filas,
        colWidths=[46 * mm, 32 * mm],
        hAlign="RIGHT",
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("VALIGN", (0, ultima), (-1, ultima), "BOTTOM"),
                ("LINEABOVE", (0, ultima), (-1, ultima), 0.9, TINTA),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, ultima), (-1, ultima), 6),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
            ]
        ),
    )


def generar_documento_pdf(datos, ruta, totales=None):
    """
    Escribe el PDF y devuelve un resumen de lo generado.

    `totales` permite pasar los importes ya calculados —los mismos que se
    enseñaron en pantalla— para que papel y aplicación no puedan discrepar.
    Si no se pasa, se calculan con `core.taxes.calcular`, que es la misma
    función que usa la interfaz.

    Devuelve `{"paginas": int, "totales": Totales, "ruta": str}`.
    """
    lineas = list(datos.get("lineas", []))
    if totales is None:
        totales = calcular(lineas)

    est = _estilos()
    referencia = f"{'Presupuesto' if datos.get('tipo') == 'presupuesto' else 'Factura'} {_texto(datos.get('numero', ''))}".strip()

    doc = SimpleDocTemplate(
        str(ruta),
        pagesize=A4,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN + 6 * mm,  # hueco para el pie con la numeración
        title=referencia,
        author=_texto(datos.get("emisor", {}).get("nombre", "")),
    )
    ancho = doc.width

    historia = [
        _cabecera(datos, est),
        Spacer(1, 5 * mm),
        _banda(datos, est),
        Spacer(1, 4 * mm),
        _partes(datos, est),
        Spacer(1, 7 * mm),
        _tabla_conceptos(lineas, est, ancho),
        Spacer(1, 6 * mm),
    ]

    # El cuadro de totales no se separa de la nota: o caben juntos al final
    # de la página o pasan los dos a la siguiente.
    cierre = [_tabla_totales(totales, est)]
    if datos.get("nota"):
        cierre += [Spacer(1, 7 * mm), Paragraph(_texto(datos["nota"]), est["nota"])]
    historia.append(KeepTogether(cierre))

    def lienzo(*args, **kwargs):
        return _LienzoNumerado(*args, referencia=referencia, **kwargs)

    doc.build(historia, canvasmaker=lienzo)

    return {"paginas": doc.page, "totales": totales, "ruta": str(ruta)}
