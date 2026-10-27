"""
Pruebas del generador de PDF (defecto 02 de la auditoría).

La prueba clave es la de los 40 conceptos: con el generador anterior, que
dibujaba con coordenadas absolutas, 21 textos acababan con coordenada Y
negativa —fuera del papel— y el cuadro de totales no llegaba a verse.
Aquí se comprueba leyendo el PDF resultante, no confiando en el código.
"""

from decimal import Decimal

import pytest
from pypdf import PdfReader

from core.taxes import IVA_REDUCIDO, Linea, calcular
from documents.invoice_pdf import generar_documento_pdf

EMISOR = {
    "nombre": "Carlos García López",
    "nif": "12345678A",
    "direccion": "Calle Mayor 12, 2ºA",
    "poblacion": "28001 Madrid",
    "telefono": "612345678",
    "email": "carlos.garcia@billease.es",
}

CLIENTE = {
    "nombre": "Construcciones Pérez S.L.",
    "nif": "B12345678",
    "direccion": "Av. Industria 45",
    "poblacion": "08020 Barcelona",
}


def documento(lineas, **extra):
    datos = {
        "tipo": "factura",
        "numero": "2025-004",
        "fecha": "14/02/2025",
        "vencimiento": "16/03/2025",
        "emisor": EMISOR,
        "cliente": CLIENTE,
        "lineas": lineas,
    }
    datos.update(extra)
    return datos


@pytest.fixture
def logotipo(tmp_path):
    """Un PNG de 600 × 200 generado al vuelo, para no versionar imágenes."""
    from PIL import Image, ImageDraw

    imagen = Image.new("RGB", (600, 200), "white")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle([8, 8, 592, 192], outline="black", width=6)
    dibujo.text((40, 95), "CARPINTERIA GARCIA", fill="black")

    ruta = tmp_path / "logotipo.png"
    imagen.save(ruta)
    return ruta


def texto_de(ruta):
    """Todo el texto del PDF, página a página."""
    return [pagina.extract_text() or "" for pagina in PdfReader(str(ruta)).pages]


def _posicion(cm, tm):
    """
    Posición real de un fragmento de texto en la página.

    Es el producto de la matriz de texto por la del espacio de usuario; `tm`
    por sí sola es relativa al bloque y sale (0, 0).
    """
    x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
    y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
    return round(x, 1), round(y, 1)


def fragmentos(ruta):
    """Cada trozo de texto del PDF con su página y sus coordenadas."""
    encontrados = []
    for numero, pagina in enumerate(PdfReader(str(ruta)).pages, 1):
        alto = float(pagina.mediabox.height)
        ancho = float(pagina.mediabox.width)

        def visitar(texto, cm, tm, font_dict, font_size, _n=numero, _a=alto, _w=ancho):
            limpio = texto.strip()
            if limpio:
                x, y = _posicion(cm, tm)
                encontrados.append((_n, limpio, x, y, _w, _a))

        pagina.extract_text(visitor_text=visitar)
    return encontrados


def posiciones(ruta, palabras):
    """Coordenadas (x, y) donde aparece cada palabra en la primera página."""
    return {
        texto: (x, y)
        for pagina, texto, x, y, _, _ in fragmentos(ruta)
        if pagina == 1 and texto in palabras
    }


@pytest.fixture
def factura_4():
    return [
        Linea("Instalación de fontanería en baño principal", cantidad=2, precio_ud=85.0, unidad="h"),
        Linea("Pintura interior de dormitorio y pasillo", cantidad=15, precio_ud=12.5, unidad="m²"),
        Linea("Mano de obra general de apoyo", cantidad=4, precio_ud=45.0, unidad="h"),
    ]


# ─────────────────────── el defecto 02 ───────────────────────


def test_una_factura_de_40_conceptos_ocupa_varias_paginas(tmp_path):
    lineas = [
        Linea(f"Concepto número {i} de la obra", cantidad=1, precio_ud=100)
        for i in range(1, 41)
    ]
    ruta = tmp_path / "larga.pdf"
    resultado = generar_documento_pdf(documento(lineas), ruta)

    assert resultado["paginas"] >= 2
    assert len(PdfReader(str(ruta)).pages) == resultado["paginas"]


def test_ningun_texto_se_dibuja_fuera_del_papel(tmp_path):
    """
    La prueba decisiva del defecto 02.

    El generador anterior restaba 20 puntos por línea sin mirar el margen: a
    partir de unos 25 conceptos la coordenada Y se volvía negativa y el texto
    se dibujaba fuera de la hoja. Ojo, porque **extraer el texto no basta**
    para detectarlo: un lector de PDF devuelve igualmente lo que está fuera
    del papel, así que hay que mirar las coordenadas.
    """
    lineas = [Linea(f"Concepto {i}", cantidad=1, precio_ud=100) for i in range(1, 41)]
    ruta = tmp_path / "larga.pdf"
    generar_documento_pdf(documento(lineas), ruta)

    fuera = [
        (pagina, texto, x, y)
        for pagina, texto, x, y, ancho, alto in fragmentos(ruta)
        if not (0 <= y <= alto and 0 <= x <= ancho)
    ]
    assert fuera == [], f"{len(fuera)} textos fuera de la página: {fuera[:5]}"


def test_no_se_pierde_ningun_concepto_por_largo_que_sea_el_documento(tmp_path):
    lineas = [
        Linea(f"Concepto número {i} de la obra", cantidad=1, precio_ud=100)
        for i in range(1, 41)
    ]
    ruta = tmp_path / "larga.pdf"
    generar_documento_pdf(documento(lineas), ruta)

    todo = "\n".join(texto_de(ruta))
    faltan = [i for i in range(1, 41) if f"Concepto número {i} de la obra" not in todo]
    assert faltan == [], f"conceptos que no llegaron al papel: {faltan}"


def test_el_cuadro_de_totales_aparece_aunque_haya_40_conceptos(tmp_path):
    lineas = [Linea(f"Concepto {i}", cantidad=1, precio_ud=100) for i in range(1, 41)]
    ruta = tmp_path / "larga.pdf"
    generar_documento_pdf(documento(lineas), ruta)

    ultima = texto_de(ruta)[-1]
    assert "TOTAL" in ultima
    assert "4.840,00" in ultima  # 4.000 de base + 840 de IVA


def test_la_cabecera_de_la_tabla_se_repite_en_cada_pagina(tmp_path):
    lineas = [Linea(f"Concepto {i}", cantidad=1, precio_ud=100) for i in range(1, 41)]
    ruta = tmp_path / "larga.pdf"
    generar_documento_pdf(documento(lineas), ruta)

    paginas = texto_de(ruta)
    assert len(paginas) >= 2
    for numero, pagina in enumerate(paginas, 1):
        assert "CONCEPTO" in pagina, f"la página {numero} no repite la cabecera"


def test_cada_pagina_lleva_su_numeracion(tmp_path):
    lineas = [Linea(f"Concepto {i}", cantidad=1, precio_ud=100) for i in range(1, 41)]
    ruta = tmp_path / "larga.pdf"
    resultado = generar_documento_pdf(documento(lineas), ruta)

    total = resultado["paginas"]
    for numero, pagina in enumerate(texto_de(ruta), 1):
        assert f"Página {numero} de {total}" in pagina


def test_un_concepto_de_400_caracteres_no_se_recorta(tmp_path):
    largo = (
        "Suministro y montaje de armario empotrado de dos módulos con puerta "
        "corredera, acabado en blanco lacado, medidas 2,00 × 2,40 m, incluyendo "
        "herrajes, guía inferior de aluminio anodizado, dos baldas interiores "
        "regulables en altura, barra de colgar cromada, remates de sellado "
        "perimetral y zócalo inferior, con retirada del embalaje, recogida de "
        "restos de obra y limpieza final completa de toda la zona de trabajo."
    )
    assert len(largo) > 400
    ruta = tmp_path / "concepto_largo.pdf"
    generar_documento_pdf(documento([Linea(largo, cantidad=1, precio_ud=1240)]), ruta)

    todo = " ".join(" ".join(texto_de(ruta)).split())
    assert "limpieza final completa de toda la zona de trabajo." in todo
    assert "armario empotrado de dos módulos" in todo


# ─────────────────────── el defecto 01 ───────────────────────


def test_el_total_del_pdf_es_el_que_calcula_core_taxes(tmp_path, factura_4):
    ruta = tmp_path / "factura.pdf"
    resultado = generar_documento_pdf(documento(factura_4), ruta)

    esperado = calcular(factura_4)
    assert resultado["totales"].total == esperado.total == Decimal("650.38")

    texto = "\n".join(texto_de(ruta))
    assert "537,50" in texto   # base imponible
    assert "112,88" in texto   # cuota de IVA
    assert "650,38" in texto   # total


def test_se_pueden_pasar_los_totales_ya_calculados(tmp_path, factura_4):
    """Los mismos importes que enseñó la pantalla, sin recalcular nada."""
    totales = calcular(factura_4)
    ruta = tmp_path / "factura.pdf"
    resultado = generar_documento_pdf(documento(factura_4), ruta, totales=totales)
    assert resultado["totales"] is totales


def test_el_desglose_aparece_cuando_se_mezclan_tipos_de_iva(tmp_path):
    lineas = [
        Linea("Material de obra", cantidad=1, precio_ud=1000),
        Linea("Reforma de vivienda", cantidad=1, precio_ud=500, tipo_iva=IVA_REDUCIDO),
    ]
    ruta = tmp_path / "mixta.pdf"
    generar_documento_pdf(documento(lineas), ruta)

    texto = "\n".join(texto_de(ruta))
    assert "IVA 21 %" in texto
    assert "IVA 10 %" in texto
    assert "1.760,00" in texto


# ─────────────────────── el defecto 04 ───────────────────────


def test_el_codigo_postal_no_sale_con_decimales(tmp_path, factura_4):
    """
    Con el esquema actual, SQLite devuelve 28001.0 y 612345678.0 porque las
    columnas están declaradas REAL. En el papel eso no puede aparecer.
    """
    emisor = dict(EMISOR, poblacion=28001.0, telefono=612345678.0)
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4, emisor=emisor), ruta)

    texto = "\n".join(texto_de(ruta))
    assert "28001.0" not in texto
    assert "612345678.0" not in texto
    assert "28001" in texto


# ─────────────────────── presupuestos ───────────────────────


def test_el_presupuesto_lleva_su_rotulo_y_su_validez(tmp_path, factura_4):
    ruta = tmp_path / "presupuesto.pdf"
    datos = documento(
        factura_4, tipo="presupuesto", numero="P-2025-011", validez="19/09/2025"
    )
    datos.pop("vencimiento")
    generar_documento_pdf(datos, ruta)

    texto = "\n".join(texto_de(ruta))
    assert "PRESUPUESTO" in texto
    assert "19/09/2025" in texto
    assert "SIN VALOR CONTABLE" in texto


def test_emisor_y_cliente_van_en_la_misma_fila(tmp_path, factura_4):
    """
    Los dos bloques comparten fila, no van uno encima del otro. Se comprueba
    sobre las coordenadas del PDF: misma altura, el cliente más a la derecha.
    """
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)

    pos = posiciones(ruta, {"EMISOR", "CLIENTE"})
    assert set(pos) == {"EMISOR", "CLIENTE"}, f"rótulos encontrados: {sorted(pos)}"

    (x_emisor, y_emisor), (x_cliente, y_cliente) = pos["EMISOR"], pos["CLIENTE"]
    assert y_emisor == y_cliente, "los rótulos no están a la misma altura"
    assert x_cliente > x_emisor, "el cliente debería ir a la derecha del emisor"


def test_el_documento_no_lleva_la_marca_del_programa(tmp_path, factura_4):
    """
    En el papel solo van los datos del autónomo y del cliente. El nombre del
    programa únicamente puede aparecer dentro del correo del emisor, porque
    forma parte de su dirección.
    """
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)

    for renglon in "\n".join(texto_de(ruta)).splitlines():
        if "billease" in renglon.lower():
            assert "@" in renglon, f"marca del programa fuera del correo: {renglon!r}"


def test_un_documento_sin_logotipo_no_lleva_ninguna_imagen(tmp_path, factura_4):
    """El papel sigue siendo el mismo si el emisor no ha puesto logotipo."""
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)
    assert list(PdfReader(str(ruta)).pages[0].images) == []


def test_el_logotipo_del_emisor_encabeza_el_documento(tmp_path, factura_4, logotipo):
    """El logotipo es del autónomo: es su documento, no el del programa."""
    ruta = tmp_path / "factura.pdf"
    emisor = dict(EMISOR, logotipo=str(logotipo))
    generar_documento_pdf(documento(factura_4, emisor=emisor), ruta)

    imagenes = list(PdfReader(str(ruta)).pages[0].images)
    assert len(imagenes) == 1
    # Y no desplaza el contenido fuera del papel.
    assert "FACTURA" in texto_de(ruta)[0]


def test_el_logotipo_se_escala_sin_deformarse(tmp_path, factura_4, logotipo):
    """
    Una imagen de 600 × 200 entra en la caja de 42 × 16 mm conservando su
    proporción: lo que no puede pasar es que salga achatada.
    """
    from documents.invoice_pdf import ALTO_LOGO, ANCHO_LOGO, _logotipo

    imagen = _logotipo({"emisor": {"logotipo": str(logotipo)}})
    assert imagen is not None
    assert imagen.drawWidth <= ANCHO_LOGO + 0.01
    assert imagen.drawHeight <= ALTO_LOGO + 0.01
    assert round(imagen.drawWidth / imagen.drawHeight, 2) == 3.0


@pytest.mark.parametrize("ruta_logo", ["", "/no/existe/logo.png", "no-es-una-imagen.txt"])
def test_un_logotipo_que_no_se_puede_leer_no_impide_emitir(
    tmp_path, factura_4, ruta_logo
):
    """
    Si el fichero se ha movido o no es una imagen, sale el documento de
    siempre. Quedarse sin poder facturar por un logotipo sería absurdo.
    """
    if ruta_logo.endswith(".txt"):
        falso = tmp_path / ruta_logo
        falso.write_text("esto no es una imagen")
        ruta_logo = str(falso)

    ruta = tmp_path / "factura.pdf"
    emisor = dict(EMISOR, logotipo=ruta_logo)
    resultado = generar_documento_pdf(documento(factura_4, emisor=emisor), ruta)

    assert resultado["paginas"] == 1
    assert list(PdfReader(str(ruta)).pages[0].images) == []
    assert "FACTURA" in texto_de(ruta)[0]


# ─────────────────── la obra y la cuenta ───────────────────

OBRA = "Calle Alcalá 120, 3.º B · 28009 Madrid"
CUENTA = {"entidad": "Banco Santander", "iban": "ES9121000418450200051332"}


def test_la_obra_va_entre_las_partes_y_los_conceptos(tmp_path, factura_4):
    """
    Es donde se busca: después de saber quién factura a quién, de qué obra se
    habla, y luego el detalle. En las observaciones del final no la ve nadie.
    """
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4, obra=OBRA), ruta)

    pos = posiciones(ruta, {"EMISOR", "CLIENTE", "DIRECCIÓN DE LA OBRA", "CONCEPTO"})
    assert "DIRECCIÓN DE LA OBRA" in pos, f"rótulos: {sorted(pos)}"

    # En un PDF la Y crece hacia arriba: más abajo es menor.
    assert pos["DIRECCIÓN DE LA OBRA"][1] < pos["EMISOR"][1]
    assert pos["DIRECCIÓN DE LA OBRA"][1] > pos["CONCEPTO"][1]
    assert OBRA in texto_de(ruta)[0]


def test_sin_obra_el_documento_no_la_menciona(tmp_path, factura_4):
    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)
    assert "DIRECCIÓN DE LA OBRA" not in texto_de(ruta)[0]


def test_el_presupuesto_tambien_lleva_la_obra(tmp_path, factura_4):
    """Se presupuesta una obra concreta, no una idea."""
    ruta = tmp_path / "presupuesto.pdf"
    generar_documento_pdf(
        documento(factura_4, tipo="presupuesto", numero="P-2026-001", obra=OBRA), ruta
    )
    assert OBRA in texto_de(ruta)[0]


def test_la_factura_dice_donde_se_transfiere(tmp_path, factura_4):
    """Debajo del total, que es donde se mira cuánto hay que pagar."""
    ruta = tmp_path / "factura.pdf"
    emisor = dict(EMISOR, **CUENTA)
    generar_documento_pdf(documento(factura_4, emisor=emisor), ruta)

    texto = texto_de(ruta)[0]
    assert "FORMA DE PAGO" in texto
    assert "Banco Santander" in texto
    # El IBAN se imprime en grupos de cuatro: así se copia sin equivocarse.
    assert "ES91 2100 0418 4502 0005 1332" in texto

    pos = posiciones(ruta, {"TOTAL", "FORMA DE PAGO"})
    assert pos["FORMA DE PAGO"][1] < pos["TOTAL"][1], "la cuenta va debajo del total"


def test_el_presupuesto_no_lleva_la_cuenta(tmp_path, factura_4):
    """Un presupuesto todavía no se cobra: pedir ahí el dinero no toca."""
    ruta = tmp_path / "presupuesto.pdf"
    emisor = dict(EMISOR, **CUENTA)
    generar_documento_pdf(
        documento(factura_4, tipo="presupuesto", numero="P-2026-001", emisor=emisor), ruta
    )

    texto = texto_de(ruta)[0]
    assert "FORMA DE PAGO" not in texto
    assert "ES91" not in texto


def test_sin_iban_no_se_inventa_una_forma_de_pago(tmp_path, factura_4):
    ruta = tmp_path / "factura.pdf"
    emisor = dict(EMISOR, entidad="Banco Santander")      # entidad pero sin IBAN
    generar_documento_pdf(documento(factura_4, emisor=emisor), ruta)
    assert "FORMA DE PAGO" not in texto_de(ruta)[0]


def test_con_obra_y_cuenta_nada_se_sale_del_papel(tmp_path, factura_4):
    """Lo de siempre: que añadir bloques no empuje nada fuera de la página."""
    ruta = tmp_path / "factura.pdf"
    emisor = dict(EMISOR, **CUENTA)
    generar_documento_pdf(
        documento(factura_4 * 12, emisor=emisor, obra=OBRA), ruta
    )

    fuera = [
        (texto, x, y) for pagina, texto, x, y, ancho, alto in fragmentos(ruta)
        if x < 0 or y < 0 or x > ancho or y > alto
    ]
    assert fuera == [], f"texto fuera del papel: {fuera[:3]}"


def test_el_generador_no_necesita_qt():
    """
    El PDF tiene que poder generarse en un servidor sin pantalla. El generador
    anterior importaba los colores de `utils/globals.py`, que define QFont y
    por tanto arrastra PyQt6 entero (defecto 14).

    Se comprueba importando el módulo en un intérprete limpio y mirando qué ha
    entrado en `sys.modules`, no leyendo el código fuente.
    """
    import subprocess
    import sys
    from pathlib import Path

    guion = (
        "import sys; import documents.invoice_pdf; "
        "cargados = [m for m in sys.modules if m.split('.')[0] in ('PyQt6', 'sqlite3')]; "
        "print(','.join(sorted(cargados)))"
    )
    raiz = Path(__file__).resolve().parent.parent
    salida = subprocess.run(
        [sys.executable, "-c", guion],
        cwd=raiz, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert salida == "", f"el generador arrastra: {salida}"


# ─────────────────────── el color y el vencimiento ───────────────────────


def rectangulos(ruta, pagina=1):
    """
    Los rectángulos macizos de una página, con su color y su caja.

    ReportLab los dibuja como `x y ancho alto re f*` dentro de un bloque con
    su propia matriz `cm`, así que la posición real es la suma de las dos.
    Devuelve `(color, izquierda, derecha, ancho)` en puntos.
    """
    import re

    contenido = PdfReader(str(ruta)).pages[pagina - 1].get_contents().get_data()
    patron = re.compile(
        r"([\d.]+) ([\d.]+) cm\s*q\s*([\d.]+) ([\d.]+) ([\d.]+) rg\s*"
        r"n ([-\d.]+) ([-\d.]+) ([\d.]+) ([-\d.]+) re"
    )
    salida = []
    for m in patron.finditer(contenido.decode("latin-1")):
        dx, dy, r, g, b, x, _y, ancho, _alto = (float(v) for v in m.groups())
        color = "#%02X%02X%02X" % tuple(round(c * 255) for c in (r, g, b))
        salida.append((color, round(dx + x, 1), round(dx + x + ancho, 1), round(ancho, 1)))
    return salida


def test_el_vencimiento_no_se_imprime(tmp_path, factura_4):
    """
    La fecha de vencimiento se guarda y mueve el estado de la factura, pero
    en el papel no sale: se quitó a petición del usuario. Lo que se le dice
    al cliente es cuánto debe y a qué cuenta.
    """
    ruta = tmp_path / "factura.pdf"
    datos = documento(factura_4)          # lleva vencimiento="16/03/2025"
    generar_documento_pdf(datos, ruta)

    texto = "\n".join(texto_de(ruta))
    assert "16/03/2025" not in texto
    assert "Vence" not in texto and "VENCIMIENTO" not in texto
    assert "14/02/2025" in texto, "la fecha de emisión sí tiene que salir"


def test_el_total_va_sobre_el_acento(tmp_path, factura_4):
    """
    El total es la cifra que se busca al coger el papel: va en una pastilla
    de color con las letras en blanco. Se comprueba sobre el PDF, que es
    donde se ve, y no sobre la constante del módulo.
    """
    from documents.invoice_pdf import ACENTO

    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)

    acento = ACENTO.hexval().replace("0x", "#").upper()[:7]
    pastillas = [r for r in rectangulos(ruta) if r[0] == acento and r[3] > 50]
    assert pastillas, f"no hay ninguna banda del acento; hay {rectangulos(ruta)}"


def test_los_conceptos_y_el_total_acaban_en_la_misma_vertical(tmp_path, factura_4):
    """
    La zebra de los conceptos y la pastilla del total tienen que morir en el
    mismo canto derecho. `hAlign="RIGHT"` de ReportLab deja seis puntos de
    aire contra el margen y descuadraba la pastilla, que es justo lo que se
    nota al mirar la hoja de lejos.
    """
    from documents.invoice_pdf import ACENTO, ZEBRA

    ruta = tmp_path / "factura.pdf"
    generar_documento_pdf(documento(factura_4), ruta)

    def canto(color):
        """El canto derecho de la banda más ancha de ese color.

        La más ancha y no la primera: en el acento hay dos, y la otra es el
        filete corto que va debajo del rótulo.
        """
        hexa = color.hexval().replace("0x", "#").upper()[:7]
        bandas = [r for r in rectangulos(ruta) if r[0] == hexa]
        assert bandas, f"no hay bandas de {hexa}"
        return max(bandas, key=lambda r: r[3])[2]

    assert abs(canto(ZEBRA) - canto(ACENTO)) < 0.5


def test_las_filas_alternas_van_tintadas_tambien_en_la_segunda_pagina(tmp_path):
    """
    La zebra se escribe fila a fila para que al partirse la tabla cada una
    conserve su fondo. Si se perdiera, la segunda página saldría toda blanca.
    """
    from documents.invoice_pdf import ZEBRA

    lineas = [
        Linea(f"Concepto {i} de una obra larga", cantidad=2, precio_ud=47.3, unidad="ud")
        for i in range(1, 46)
    ]
    ruta = tmp_path / "factura.pdf"
    paginas = generar_documento_pdf(documento(lineas), ruta)["paginas"]
    assert paginas > 1, "hacen falta varias páginas para probar esto"

    hexa = ZEBRA.hexval().replace("0x", "#").upper()[:7]
    con_conceptos = [
        numero for numero, texto in enumerate(texto_de(ruta), 1) if "CONCEPTO" in texto
    ]
    assert len(con_conceptos) > 1, "la tabla no llegó a partirse"
    for pagina in con_conceptos:
        bandas = [r for r in rectangulos(ruta, pagina) if r[0] == hexa]
        assert bandas, f"la página {pagina} no tiene ninguna fila tintada"


def test_todo_lo_que_se_lee_en_el_papel_llega_al_minimo():
    """
    Puerta 5, pero del PDF: una factura también hay que poder leerla. El
    par justo es el blanco sobre el acento, que es el único texto del
    documento que no va en tinta oscura.
    """
    from theme.tokens import MINIMO, contraste

    from documents.invoice_pdf import PARES_PAPEL

    flojos = [
        (descripcion, round(razon, 2))
        for frente, fondo, descripcion in PARES_PAPEL
        if (razon := contraste(frente.hexval()[2:], fondo.hexval()[2:])) < MINIMO
    ]
    assert flojos == [], f"pares por debajo de {MINIMO}:1: {flojos}"
