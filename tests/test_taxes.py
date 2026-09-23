"""
Pruebas del cálculo de importes (defecto 01 de la auditoría).

Sin Qt y sin base de datos: se ejecutan en cualquier sitio.
"""

from decimal import Decimal

import pytest

from core.taxes import (
    IVA_EXENTO,
    IVA_GENERAL,
    IVA_REDUCIDO,
    IVA_SUPERREDUCIDO,
    Linea,
    calcular,
    desde_detalles,
    formatear,
    redondear,
)


def d(valor):
    return Decimal(str(valor))


# ─────────────────────────── redondeo ───────────────────────────


def test_redondeo_comercial_sube_el_medio_centimo():
    # 537,50 × 21 % = 112,875 → la regla comercial sube a 112,88.
    # Con el redondeo bancario de Python (`round`) saldría 112,87 y la
    # factura no cuadraría con la que emite cualquier otro programa.
    assert redondear(Decimal("112.875")) == d("112.88")
    assert redondear(Decimal("0.005")) == d("0.01")


def test_no_arrastra_el_ruido_de_la_coma_flotante():
    # 0,1 + 0,2 en float es 0,30000000000000004
    lineas = [
        Linea("a", cantidad=1, precio_ud=0.1),
        Linea("b", cantidad=1, precio_ud=0.2),
    ]
    assert calcular(lineas).base == d("0.30")


def test_formato_espanol():
    assert formatear(Decimal("1736.35")) == "1.736,35"
    assert formatear(Decimal("650.38")) == "650,38"
    assert formatear(Decimal("0")) == "0,00"
    assert formatear(Decimal("1234567.5")) == "1.234.567,50"


# ─────────────────────────── cálculo ───────────────────────────


def test_base_iva_y_total_de_una_factura_de_690():
    # El caso de la maqueta del rediseño.
    lineas = [
        Linea("Armario a medida", cantidad=1, precio_ud=340),
        Linea("Desmontaje", cantidad=1, precio_ud=350),
    ]
    t = calcular(lineas)
    assert t.base == d("690.00")
    assert t.cuota_iva == d("144.90")
    assert t.total == d("834.90")


def test_la_factura_4_de_la_base_de_demostracion():
    # 2 × 85,00 + 15 × 12,50 + 4 × 45,00 = 537,50 de base.
    # El PDF de hoy imprime 650,38 y la lista muestra 537,50 como «total»:
    # son las dos cifras del defecto 01.
    lineas = [
        Linea("Instalación de fontanería", cantidad=2, precio_ud=85.0),
        Linea("Pintura interior m²", cantidad=15, precio_ud=12.5),
        Linea("Mano de obra general", cantidad=4, precio_ud=45.0),
    ]
    t = calcular(lineas)
    assert t.base == d("537.50")
    assert t.cuota_iva == d("112.88")
    assert t.total == d("650.38")


@pytest.mark.parametrize(
    "tipo,cuota_esperada,total_esperado",
    [
        (IVA_GENERAL, "210.00", "1210.00"),
        (IVA_REDUCIDO, "100.00", "1100.00"),
        (IVA_SUPERREDUCIDO, "40.00", "1040.00"),
        (IVA_EXENTO, "0.00", "1000.00"),
    ],
)
def test_los_cuatro_tipos_de_iva(tipo, cuota_esperada, total_esperado):
    t = calcular([Linea("Servicio", cantidad=1, precio_ud=1000, tipo_iva=tipo)])
    assert t.base == d("1000.00")
    assert t.cuota_iva == d(cuota_esperada)
    assert t.total == d(total_esperado)


def test_desglose_cuando_se_mezclan_dos_tipos():
    # Materiales al 21 % y reforma de vivienda al 10 %.
    lineas = [
        Linea("Material", cantidad=1, precio_ud=1000, tipo_iva=IVA_GENERAL),
        Linea("Reforma", cantidad=1, precio_ud=500, tipo_iva=IVA_REDUCIDO),
    ]
    t = calcular(lineas)
    assert t.base == d("1500.00")
    assert t.cuota_iva == d("260.00")  # 210 + 50
    assert t.total == d("1760.00")
    assert [(x.tipo, x.base, x.cuota) for x in t.desglose] == [
        (d("21"), d("1000.00"), d("210.00")),
        (d("10"), d("500.00"), d("50.00")),
    ]
    assert t.tipo_unico is None


def test_tipo_unico_cuando_todo_va_al_mismo_iva():
    t = calcular([Linea("Servicio", cantidad=1, precio_ud=100)])
    assert t.tipo_unico == IVA_GENERAL


def test_la_base_es_la_suma_exacta_de_los_importes_de_linea():
    # Invariante que el cliente puede comprobar sumando la columna a mano.
    lineas = [
        Linea("a", cantidad=3, precio_ud=33.333),
        Linea("b", cantidad=7, precio_ud=1.115),
        Linea("c", cantidad=1, precio_ud=0.005),
    ]
    t = calcular(lineas)
    assert t.base == sum(linea.importe for linea in lineas)


def test_documento_sin_lineas():
    t = calcular([])
    assert (t.base, t.cuota_iva, t.total) == (d("0.00"), d("0.00"), d("0.00"))
    assert t.desglose == ()


# ─────────────────────── puente con la base ───────────────────────


def test_desde_base_da_el_mismo_total_que_desde_las_lineas():
    """
    El listado calcula desde la base guardada y el PDF desde las líneas:
    tienen que coincidir al céntimo o vuelve el defecto 01.
    """
    from core.taxes import desde_base

    lineas = [
        Linea("Instalación de fontanería", cantidad=2, precio_ud=85.0),
        Linea("Pintura interior m²", cantidad=15, precio_ud=12.5),
        Linea("Mano de obra general", cantidad=4, precio_ud=45.0),
    ]
    desde_lineas = calcular(lineas)
    desde_columna = desde_base(desde_lineas.base)

    assert desde_columna.base == desde_lineas.base
    assert desde_columna.cuota_iva == desde_lineas.cuota_iva
    assert desde_columna.total == desde_lineas.total == d("650.38")


def test_desde_base_con_las_siete_facturas_de_la_demostracion():
    from core.taxes import desde_base

    bases_y_totales = {
        480.0: "580.80", 211.0: "255.31", 1420.0: "1718.20", 537.5: "650.38",
        110.0: "133.10", 830.0: "1004.30", 180.0: "217.80",
    }
    for base, total in bases_y_totales.items():
        assert desde_base(base).total == d(total)


def test_desde_detalles_construye_las_lineas():
    # Forma de las filas de `obtener_detalles_factura`:
    # (Num_Factura, Num_Linea, cantidad, precio, cod_servicio, descripcion)
    detalles = [
        (4.0, 1.0, 2.0, 85.0, 1.0, "Instalación de fontanería"),
        (4.0, 2.0, 15.0, 12.5, 3.0, "Pintura interior m²"),
        (4.0, 3.0, 4.0, 45.0, 5.0, "Mano de obra general"),
    ]
    lineas = desde_detalles(detalles)
    assert [linea.descripcion for linea in lineas] == [
        "Instalación de fontanería",
        "Pintura interior m²",
        "Mano de obra general",
    ]
    assert calcular(lineas).total == d("650.38")
