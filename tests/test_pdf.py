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


def test_el_documento_no_lleva_marca_de_agua_ni_logotipo(tmp_path, factura_4):
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
