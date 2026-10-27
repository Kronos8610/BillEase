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
      "vencimiento": "16/03/2025",     # se acepta pero no se imprime
      "validez":     "19/09/2025",     # opcional (presupuestos)
      "emisor":   {"nombre", "nif", "direccion", "poblacion", "telefono", "email",
                   "logotipo",    # ruta de una imagen, opcional
                   "entidad", "iban"},   # dónde se cobra; solo en facturas
      "obra":     "Calle Alcalá 120, 3.º B",   # opcional: dónde es el trabajo
      "cliente":  {"nombre", "nif", "direccion", "poblacion", "telefono", "email"},
      "lineas":   [core.taxes.Linea, ...],
      "nota":     "…",                 # las observaciones; solo si las hay
    }

El vencimiento se guarda y se usa en la aplicación —de ahí salen las
facturas vencidas— pero no se imprime: el papel dice qué se debe y a qué
cuenta, y el plazo se habla aparte.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.taxes import calcular, formatear

# Dos tintas: la oscura hace la estructura y el acento resalta lo que se
# busca —el total, la obra, el número de cuenta—. El color va en filetes,
# rótulos y una sola pastilla, nunca en fondos grandes: así gasta poco tóner
# y la factura se sigue leyendo entera si se imprime en blanco y negro.
TINTA = colors.HexColor("#1C1917")
ACENTO = colors.HexColor("#9A3412")          # teja
GRIS = colors.HexColor("#44403C")
GRIS_CLARO = colors.HexColor("#57534E")
FILETE = colors.HexColor("#E7E2DC")
FILETE_FUERTE = colors.HexColor("#DDD8D2")
# El acento al 6 % sobre blanco: las filas alternas de la tabla.
ZEBRA = colors.HexColor("#FAF3F0")
PAPEL = colors.white

# Lo que el cliente lee como «texto sobre fondo» en el papel. El PDF pasa por
# la misma vara de medir que la pantalla: `tools/check_contraste.py --papel`
# recorre estos pares y ninguno puede bajar de 4,5:1. Importa sobre todo el
# primero, que es el único texto en blanco del documento.
PARES_PAPEL = (
    (PAPEL, ACENTO, "el total, en blanco sobre la pastilla"),
    (TINTA, PAPEL, "el texto corriente sobre el papel"),
    (TINTA, ZEBRA, "un concepto sobre una fila tintada"),
    (GRIS, PAPEL, "los datos del emisor y del cliente"),
    (GRIS, ZEBRA, "los importes sobre una fila tintada"),
    (GRIS_CLARO, PAPEL, "los rótulos pequeños y el pie"),
    (ACENTO, PAPEL, "el rótulo CLIENTE"),
)

# Helvetica es una de las catorce fuentes que todo lector de PDF trae de
# serie, así que el documento se ve igual en cualquier ordenador sin
# empaquetar nada. La tipografía matricial del diseño llegará cuando se
# incruste el fichero de la fuente.
FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"

MARGEN = 18 * mm

# Lo que se mete el texto dentro de las tablas con fondo (la zebra de los
# conceptos y la pastilla del total): la banda llega hasta el margen de la
# página y las letras no se pegan a su borde.
SANGRIA = 3 * mm

# El logotipo encabeza el documento sin competir con él: cabe en una caja de
# este tamaño y se escala conservando su proporción.
ANCHO_LOGO = 42 * mm
ALTO_LOGO = 16 * mm


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


def _logotipo(datos):
    """
    El logotipo del emisor, escalado para que quepa en su caja.

    Devuelve None si no hay logotipo, si el fichero ya no existe o si la
    imagen no se puede leer: un documento sin logotipo es exactamente lo que
    se emitía hasta ahora, y es preferible a no poder emitirlo.
    """
    ruta = _texto(datos.get("emisor", {}).get("logotipo", ""))
    if not ruta or not Path(ruta).is_file():
        return None

    try:
        ancho_real, alto_real = ImageReader(ruta).getSize()
        if not ancho_real or not alto_real:
            return None
        escala = min(ANCHO_LOGO / ancho_real, ALTO_LOGO / alto_real)
        return Image(ruta, width=ancho_real * escala, height=alto_real * escala,
                     hAlign="LEFT")
    except Exception:          # noqa: BLE001 — un fichero que no es una imagen
        return None


def _estilos():
    base = ParagraphStyle(
        "base", fontName=FUENTE, fontSize=9, leading=12.5, textColor=TINTA
    )
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base, fontName=FUENTE_NEGRITA, fontSize=23, leading=25
        ),
        "sello": ParagraphStyle(
            "sello", parent=base, fontSize=6.5, leading=10, textColor=GRIS_CLARO
        ),
        "meta": ParagraphStyle(
            "meta", parent=base, fontSize=7.5, leading=12, textColor=GRIS_CLARO
        ),
        "meta_dato": ParagraphStyle(
            "meta_dato", parent=base, fontName=FUENTE_NEGRITA, fontSize=8.5, alignment=TA_RIGHT
        ),
        "etiqueta": ParagraphStyle(
            "etiqueta", parent=base, fontSize=7, leading=10, textColor=GRIS_CLARO
        ),
        "etiqueta_acento": ParagraphStyle(
            "etiqueta_acento", parent=base, fontSize=7, leading=10, textColor=ACENTO
        ),
        "obra": ParagraphStyle(
            "obra", parent=base, fontName=FUENTE_NEGRITA, fontSize=9.5, leading=13
        ),
        "parte": ParagraphStyle("parte", parent=base, fontSize=8.5, leading=11.5, textColor=GRIS),
        "parte_nombre": ParagraphStyle(
            "parte_nombre", parent=base, fontName=FUENTE_NEGRITA, fontSize=9.5, leading=13
        ),
        "th": ParagraphStyle(
            "th", parent=base, fontSize=7, leading=9, textColor=TINTA
        ),
        "th_der": ParagraphStyle(
            "th_der", parent=base, fontSize=7, leading=9,
            textColor=TINTA, alignment=TA_RIGHT,
        ),
        "concepto": ParagraphStyle("concepto", parent=base, fontSize=9, leading=12.5),
        "celda_der": ParagraphStyle("celda_der", parent=base, fontSize=9, alignment=TA_RIGHT),
        "celda_fuerte": ParagraphStyle(
            "celda_fuerte", parent=base, fontName=FUENTE_NEGRITA, fontSize=9,
            alignment=TA_RIGHT,
        ),
        "total_etq": ParagraphStyle("total_etq", parent=base, fontSize=8, textColor=GRIS),
        "total_val": ParagraphStyle("total_val", parent=base, fontSize=8, alignment=TA_RIGHT, textColor=GRIS),
        "total_final_etq": ParagraphStyle(
            "tfe", parent=base, fontSize=7.5, textColor=PAPEL, leading=14
        ),
        "total_final_val": ParagraphStyle(
            "tfv", parent=base, fontName=FUENTE_NEGRITA, fontSize=16,
            leading=19, alignment=TA_RIGHT, textColor=PAPEL,
        ),
        "nota": ParagraphStyle("nota", parent=base, fontSize=7.5, leading=11, textColor=GRIS),
        "iban": ParagraphStyle(
            "iban", parent=base, fontName=FUENTE_NEGRITA, fontSize=11, leading=15
        ),
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


def _barra(ancho, alto, color):
    """Un rectángulo macizo. Es como se dibuja un filete grueso con platypus."""
    return Table(
        [[""]],
        colWidths=[ancho],
        rowHeights=[alto],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def _con_barra(contenido, color=None):
    """
    Un bloque con una barra de color pegada a la izquierda.

    Es lo que distingue de un vistazo la obra y la forma de pago del resto del
    papel, sin encerrarlas en una caja.
    """
    return Table(
        [[" ", contenido]],
        colWidths=[1.4 * mm, None],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, 0), color or ACENTO),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def _cabecera(datos, est, ancho):
    """
    Rótulo subrayado con el acento a la izquierda, y los datos en una caja.

    El vencimiento no sale: se quitó a petición del usuario. En un
    presupuesto sí va la validez, que es lo que le da sentido a una oferta.
    """
    es_presupuesto = datos.get("tipo", "factura") == "presupuesto"
    rotulo = "PRESUPUESTO" if es_presupuesto else "FACTURA"

    # El filete se mide sobre la palabra, no a ojo: así queda igual de
    # proporcionado debajo de FACTURA que debajo de PRESUPUESTO, que es la
    # mitad de larga otra vez.
    estilo = est["titulo"]
    izquierda = [
        Paragraph(rotulo, estilo),
        Spacer(1, 2 * mm),
        _barra(
            0.8 * stringWidth(rotulo, estilo.fontName, estilo.fontSize),
            1.6 * mm,
            ACENTO,
        ),
    ]
    if es_presupuesto:
        izquierda += [Spacer(1, 2 * mm), Paragraph("SIN VALOR CONTABLE", est["sello"])]

    filas_meta = [("Nº", datos.get("numero", "")), ("Fecha", datos.get("fecha", ""))]
    if es_presupuesto and datos.get("validez"):
        filas_meta.append(("Válido hasta", datos["validez"]))

    meta = Table(
        [
            [Paragraph(etiqueta, est["meta"]), Paragraph(_texto(valor), est["meta_dato"])]
            for etiqueta, valor in filas_meta
        ],
        colWidths=[24 * mm, 28 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.6, FILETE_FUERTE),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (0, -1), 4 * mm),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ]
        ),
    )

    return Table(
        [[izquierda, meta]],
        colWidths=[ancho - 52 * mm, 52 * mm],
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


def _obra(datos, est):
    """
    La dirección de la obra, entre las partes y los conceptos.

    No es la dirección del cliente: se le factura a la oficina un trabajo
    hecho en otra calle, y quien recibe el papel necesita saber de qué obra se
    está hablando. Por eso va justo encima de los conceptos, que es donde se
    busca, y no escondida en las observaciones.
    """
    direccion = _texto(datos.get("obra", ""))
    if not direccion:
        return None

    return _con_barra([
        Paragraph("DIRECCIÓN DE LA OBRA", est["etiqueta"]),
        Spacer(1, 0.8 * mm),
        Paragraph(direccion, est["obra"]),
    ])


def _cuenta(datos, est):
    """
    Dónde se hace la transferencia. Solo en las facturas.

    Un presupuesto no se cobra todavía, así que poner ahí el número de cuenta
    sería pedir un dinero que nadie debe aún.
    """
    if datos.get("tipo", "factura") == "presupuesto":
        return None

    emisor = datos.get("emisor", {})
    iban = _texto(emisor.get("iban", ""))
    if not iban:
        return None

    from core.validators.banco import formatear_iban

    entidad = _texto(emisor.get("entidad", ""))
    dentro = [Paragraph("FORMA DE PAGO", est["etiqueta"]), Spacer(1, 0.8 * mm)]
    dentro.append(Paragraph(
        f"Transferencia a {entidad}" if entidad else "Transferencia bancaria",
        est["parte"],
    ))
    dentro.append(Paragraph(formatear_iban(iban), est["iban"]))
    return [_con_barra(dentro, color=TINTA)]


def _bloque_parte(etiqueta, parte, est, estilo="etiqueta"):
    lineas = [Paragraph(etiqueta.upper(), est[estilo])]
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
    """
    Emisor a la izquierda y cliente a la derecha, en la misma fila.

    Cada bloque cuelga de su propio filete: el del emisor en tinta y el del
    cliente en el acento. Es lo que hace que se vean como dos columnas y no
    como un párrafo partido. La columna del medio está vacía y solo abre el
    hueco: así los dos filetes no se tocan y no parecen uno solo de dos
    colores.
    """
    izquierda = _bloque_parte("Emisor", datos.get("emisor", {}), est)
    derecha = _bloque_parte("Cliente", datos.get("cliente", {}), est, "etiqueta_acento")
    return Table(
        [[izquierda, "", derecha]],
        colWidths=["46%", "8%", "46%"],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEABOVE", (0, 0), (0, 0), 1.2, TINTA),
                ("LINEABOVE", (2, 0), (2, 0), 1.2, ACENTO),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
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
                Paragraph(formatear(linea.importe), est["celda_fuerte"]),
            ]
        )

    # Filas alternas tintadas en lugar de una raya entre cada dos: el ojo
    # sigue el renglón hasta el importe sin perderse, y un concepto de tres
    # líneas se ve como un solo bloque. Se escriben una a una, y no con
    # ROWBACKGROUNDS, para que al partirse la tabla entre páginas cada fila
    # conserve el fondo que le toca.
    zebra = [
        ("BACKGROUND", (0, fila), (-1, fila), ZEBRA)
        for fila in range(1, len(filas))
        if fila % 2 == 1
    ]

    anchos = [ancho - (62 * mm), 18 * mm, 21 * mm, 23 * mm]
    return Table(
        filas,
        colWidths=anchos,
        repeatRows=1,
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                *zebra,
                ("LINEBELOW", (0, 0), (-1, 0), 1.4, TINTA),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, FILETE_FUERTE),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (0, -1), SANGRIA),
                ("RIGHTPADDING", (-1, 0), (-1, -1), SANGRIA),
            ]
        ),
    )


def _tabla_totales(totales, est, ancho):
    """
    Los importes a la derecha, con el total en una pastilla del acento.

    La tabla ocupa toda la caja de texto y deja vacía la primera columna en
    vez de alinearse a la derecha: `hAlign="RIGHT"` deja seis puntos de aire
    contra el margen, y entonces la pastilla no acaba donde acaban los
    conceptos. Así los dos cantos derechos caen en la misma vertical.
    """
    filas = [
        ["", Paragraph("Base imponible", est["total_etq"]),
         Paragraph(f"{formatear(totales.base)} €", est["total_val"])],
    ]
    for tramo in totales.desglose:
        etiqueta = f"IVA {formatear(tramo.tipo).rstrip('0').rstrip(',')} %"
        if len(totales.desglose) > 1:
            etiqueta += f" (sobre {formatear(tramo.base)} €)"
        filas.append(
            ["", Paragraph(etiqueta, est["total_etq"]),
             Paragraph(f"{formatear(tramo.cuota)} €", est["total_val"])]
        )
    filas.append(
        ["", Paragraph("TOTAL", est["total_final_etq"]),
         Paragraph(f"{formatear(totales.total)} €", est["total_final_val"])]
    )

    # El total va en una pastilla del acento con las letras en blanco: es la
    # cifra que se busca al coger el papel, y así se encuentra sin leer nada.
    # Encima queda un hueco en blanco para que la pastilla no parezca otra
    # fila más del cuadro.
    ultima = len(filas) - 1
    return Table(
        filas,
        colWidths=[ancho - 78 * mm, 46 * mm, 32 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, ultima - 1), (-1, ultima - 1), 9),
                ("BACKGROUND", (1, ultima), (-1, ultima), ACENTO),
                ("TOPPADDING", (0, ultima), (-1, ultima), 5),
                ("BOTTOMPADDING", (0, ultima), (-1, ultima), 6),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (1, 0), (1, -1), SANGRIA),
                ("RIGHTPADDING", (-1, 0), (-1, -1), SANGRIA),
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

    historia = []
    logotipo = _logotipo(datos)
    if logotipo is not None:
        historia += [logotipo, Spacer(1, 6 * mm)]

    historia += [
        _cabecera(datos, est, ancho),
        Spacer(1, 7 * mm),
        _partes(datos, est),
    ]

    obra = _obra(datos, est)
    if obra is not None:
        historia += [Spacer(1, 6 * mm), obra]

    historia += [
        Spacer(1, 7 * mm),
        _tabla_conceptos(lineas, est, ancho),
        Spacer(1, 6 * mm),
    ]

    # El cuadro de totales no se separa de la cuenta ni de la nota: o caben
    # juntos al final de la página o pasan todos a la siguiente. Donde se cobra
    # debajo de cuánto se cobra, que es donde se mira.
    cierre = [_tabla_totales(totales, est, ancho)]
    cuenta = _cuenta(datos, est)
    if cuenta:
        cierre += [Spacer(1, 7 * mm), *cuenta]
    if datos.get("nota"):
        cierre += [Spacer(1, 7 * mm), Paragraph(_texto(datos["nota"]), est["nota"])]
    historia.append(KeepTogether(cierre))

    def lienzo(*args, **kwargs):
        return _LienzoNumerado(*args, referencia=referencia, **kwargs)

    doc.build(historia, canvasmaker=lienzo)

    return {"paginas": doc.page, "totales": totales, "ruta": str(ruta)}
