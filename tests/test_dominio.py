"""
Pruebas de los modelos y de la numeración de la serie.
"""

from decimal import Decimal

import pytest

from core.models import Autonomo, Cliente, Documento, Linea
from core.money import formatear, redondear
from core.numbering import Numero, huecos, siguiente, siguiente_para


# ─────────────────────────── modelos ───────────────────────────


def test_la_linea_calcula_su_importe_redondeado():
    linea = Linea("Pintura", cantidad=15, precio_ud="12,5")
    assert linea.importe == Decimal("187.50")


def test_la_linea_acepta_la_coma_decimal_espanola():
    assert Linea("x", cantidad="1,5", precio_ud="10,20").importe == Decimal("15.30")


def test_la_referencia_de_un_documento():
    doc = Documento(id=4, ejercicio=2025, numero=4)
    assert doc.referencia == "2025-004"


def test_la_referencia_con_serie():
    assert Documento(id=1, serie="R", ejercicio=2025, numero=7).referencia == "R-2025-007"


def test_un_documento_sin_numerar_cae_en_su_identificador():
    assert Documento(id=12).referencia == "12"


def test_la_etiqueta_fiscal_depende_del_tipo_de_cliente():
    assert Cliente(es_persona_fisica=True).etiqueta_fiscal == "NIF"
    assert Cliente(es_persona_fisica=False).etiqueta_fiscal == "CIF"


def test_el_nombre_completo_del_autonomo():
    assert Autonomo(nombre="Carlos", apellido="García López").nombre_completo == "Carlos García López"
    assert Autonomo(nombre="Ana").nombre_completo == "Ana"


def test_los_modelos_son_inmutables():
    """Nadie puede cambiar una factura ya emitida por accidente."""
    with pytest.raises(Exception):
        Documento(id=1).base = 100


# ─────────────────────────── numeración ───────────────────────────


def test_la_primera_factura_de_un_ejercicio_es_la_uno():
    assert siguiente([], 2026) == Numero("", 2026, 1)


def test_el_siguiente_numero_va_detras_del_mayor():
    usados = [("", 2025, 1), ("", 2025, 2), ("", 2025, 3)]
    assert str(siguiente(usados, 2025)) == "2025-004"


def test_cada_ejercicio_empieza_por_el_uno():
    usados = [("", 2025, n) for n in range(1, 8)]
    assert str(siguiente(usados, 2026)) == "2026-001"


def test_un_numero_gastado_no_se_reutiliza():
    """
    Si se anula la última factura, su número queda gastado. Reutilizarlo daría
    dos facturas distintas con el mismo número.
    """
    usados = [("", 2025, 1), ("", 2025, 2), ("", 2025, 7)]
    assert str(siguiente(usados, 2025)) == "2025-008"


def test_las_series_se_numeran_por_separado():
    usados = [("", 2025, 5), ("R", 2025, 1)]
    assert str(siguiente(usados, 2025, serie="")) == "2025-006"
    assert str(siguiente(usados, 2025, serie="R")) == "R-2025-002"


def test_el_ejercicio_sale_de_la_fecha():
    assert str(siguiente_para("2026-03-15", [])) == "2026-001"


def test_se_detectan_los_huecos_de_la_serie():
    """Una serie con huecos es un problema si llega una inspección."""
    assert huecos([("", 2025, 1), ("", 2025, 3), ("", 2025, 4)], 2025) == [2]
    assert huecos([("", 2025, n) for n in range(1, 8)], 2025) == []
    assert huecos([], 2025) == []


# ─────────────────────────── dinero ───────────────────────────


def test_el_redondeo_es_comercial_no_bancario():
    assert redondear("112.875") == Decimal("112.88")
    assert redondear("0.005") == Decimal("0.01")


def test_el_formato_espanol_agrupa_los_miles():
    assert formatear("1736.35") == "1.736,35"
    assert formatear("1234567.5") == "1.234.567,50"
    assert formatear("-50") == "-50,00"
