"""
Pruebas de los resúmenes fiscales y de los estados de cobro (fase 6).

Lo que se comprueba es lo que exige la puerta 6: que el resumen de IVA
**cuadre con la suma a mano**. Por eso los números de estas pruebas están
escritos a mano, calculados aparte, y no sacados de la propia función: una
prueba que llama a lo mismo que prueba no comprueba nada.
"""

from decimal import Decimal

import pytest

from core.cobros import (
    PENDIENTE,
    VENCIDA,
    dias_de_retraso,
    esta_vencida,
    puede_pasar_a,
    reparto,
    situacion,
)
from core.models import COBRADA, EMITIDA, FACTURA, PRESUPUESTO, Documento
from core.reports import (
    ejercicios,
    limites,
    por_cliente,
    resumen_por_ejercicio,
    resumen_trimestral,
    trimestre_de,
)


def factura(fecha, base, estado=EMITIDA, vencimiento="", cliente="Pérez S.L.",
            cliente_id=1, tipo=FACTURA, iva=21):
    """Una factura ya guardada, como la devuelve el repositorio."""
    bruto = Decimal(str(base))
    total = (bruto * (100 + Decimal(str(iva))) / 100).quantize(Decimal("0.01"))
    return Documento(
        id=abs(hash((fecha, str(base), estado))) % 10_000,
        tipo=tipo,
        estado=estado,
        fecha=fecha,
        vencimiento=vencimiento,
        cliente_id=cliente_id,
        cliente_nombre=cliente,
        base=bruto,
        tipo_iva=Decimal(str(iva)),
        importe_total=total,
        ejercicio=int(fecha[:4]),
        numero=1,
    )


# Un ejercicio de ejemplo. Las bases están elegidas para que las sumas se
# puedan hacer de cabeza.
EJERCICIO = [
    factura("2026-01-15", 1000),                     # 1T
    factura("2026-03-31", 500),                      # 1T  (último día)
    factura("2026-04-01", 2000),                     # 2T  (primer día)
    factura("2026-09-30", 300),                      # 3T
    factura("2026-10-01", 1200),                     # 4T
    factura("2026-12-31", 800),                      # 4T
    factura("2025-12-31", 9999),                     # otro ejercicio
    factura("2026-02-10", 5000, tipo=PRESUPUESTO),   # un presupuesto no cuenta
]


# ─────────────────────── el trimestre ───────────────────────


@pytest.mark.parametrize("fecha,esperado", [
    ("2026-01-01", 1), ("2026-03-31", 1),
    ("2026-04-01", 2), ("2026-06-30", 2),
    ("2026-07-01", 3), ("2026-09-30", 3),
    ("2026-10-01", 4), ("2026-12-31", 4),
])
def test_cada_fecha_cae_en_su_trimestre(fecha, esperado):
    assert trimestre_de(fecha) == esperado


@pytest.mark.parametrize("entrada", ["", None, "no es una fecha", "2026"])
def test_una_fecha_que_no_se_entiende_no_cae_en_ningun_trimestre(entrada):
    assert trimestre_de(entrada) == 0


def test_los_limites_del_trimestre_cierran_el_ano_entero():
    assert limites(2026, 1) == ("2026-01-01", "2026-03-31")
    assert limites(2026, 2) == ("2026-04-01", "2026-06-30")
    assert limites(2026, 3) == ("2026-07-01", "2026-09-30")
    assert limites(2026, 4) == ("2026-10-01", "2026-12-31")


# ─────────────────────── el resumen ───────────────────────


def test_el_resumen_cuadra_con_la_suma_a_mano():
    """
    1T = 1.000 + 500 = 1.500 de base · 21 % = 315 de IVA · 1.815 de total.

    Los números están calculados aparte, no pedidos a la función.
    """
    resumen = resumen_trimestral(EJERCICIO, 2026)
    primero = resumen.trimestre(1)

    assert primero.documentos == 2
    assert primero.base == Decimal("1500.00")
    assert primero.cuota_iva == Decimal("315.00")
    assert primero.total == Decimal("1815.00")


def test_cada_trimestre_lleva_lo_suyo_y_solo_lo_suyo():
    resumen = resumen_trimestral(EJERCICIO, 2026)
    bases = [resumen.trimestre(t).base for t in (1, 2, 3, 4)]
    assert bases == [Decimal("1500"), Decimal("2000"), Decimal("300"), Decimal("2000")]
    assert [resumen.trimestre(t).documentos for t in (1, 2, 3, 4)] == [2, 1, 1, 2]


def test_el_ano_es_la_suma_de_los_cuatro_trimestres():
    resumen = resumen_trimestral(EJERCICIO, 2026)
    suma = sum(t.base for t in resumen.trimestres)
    assert resumen.anual.base == suma == Decimal("5800.00")
    assert resumen.anual.cuota_iva == Decimal("1218.00")     # 5.800 × 21 %
    assert resumen.anual.total == Decimal("7018.00")
    assert resumen.anual.documentos == 6


def test_un_presupuesto_no_entra_en_el_resumen():
    """Una oferta no es un ingreso: declararla sería declarar lo que no se cobró."""
    resumen = resumen_trimestral(EJERCICIO, 2026)
    # El presupuesto de 5.000 € es de febrero; el 1T sigue valiendo 1.500.
    assert resumen.trimestre(1).base == Decimal("1500.00")
    assert resumen.anual.documentos == 6


def test_el_resumen_separa_los_ejercicios():
    de_2025 = resumen_trimestral(EJERCICIO, 2025)
    assert de_2025.anual.documentos == 1
    assert de_2025.anual.base == Decimal("9999")
    assert de_2025.trimestre(4).documentos == 1
    assert de_2025.trimestre(1).documentos == 0


def test_un_trimestre_sin_facturas_sale_igualmente_con_ceros():
    """En el modelo 303 también hay que presentarlo, y verlo vacío es información."""
    resumen = resumen_trimestral([factura("2026-05-05", 100)], 2026)
    primero = resumen.trimestre(1)
    assert primero.vacio
    assert primero.documentos == 0
    assert primero.base == Decimal("0")
    assert len(resumen.trimestres) == 4


def test_los_ejercicios_salen_del_mas_reciente_al_mas_antiguo():
    assert ejercicios(EJERCICIO) == [2026, 2025]
    assert [t.ejercicio for t in resumen_por_ejercicio(EJERCICIO)] == [2026, 2025]


def test_el_resumen_por_cliente_ordena_por_lo_facturado():
    documentos = [
        factura("2026-01-10", 1000, cliente="Pérez S.L.", cliente_id=1),
        factura("2026-02-10", 500, cliente="Pérez S.L.", cliente_id=1),
        factura("2026-03-10", 3000, cliente="Reformas Norte", cliente_id=2),
    ]
    tramos = por_cliente(documentos, 2026)
    assert [t.etiqueta for t in tramos] == ["Reformas Norte", "Pérez S.L."]
    assert tramos[0].base == Decimal("3000")
    assert tramos[1].base == Decimal("1500")


def test_el_resumen_distingue_lo_cobrado_de_lo_pendiente():
    documentos = [
        factura("2026-01-10", 1000, estado=COBRADA),
        factura("2026-02-10", 1000, estado=EMITIDA),
    ]
    resumen = resumen_trimestral(documentos, 2026)
    assert resumen.anual.total == Decimal("2420.00")
    assert resumen.anual.cobrado == Decimal("1210.00")
    assert resumen.anual.pendiente == Decimal("1210.00")


# ─────────────────────── los cobros ───────────────────────


def test_una_factura_emitida_esta_pendiente():
    assert situacion(factura("2026-01-10", 100)) == PENDIENTE


def test_una_factura_cobrada_no_vence_aunque_pase_la_fecha():
    cobrada = factura("2026-01-10", 100, estado=COBRADA, vencimiento="2026-02-10")
    assert situacion(cobrada, hoy="2026-10-14") == COBRADA
    assert not esta_vencida(cobrada, hoy="2026-10-14")


def test_una_factura_sin_cobrar_vence_al_pasar_el_plazo():
    pendiente = factura("2026-01-10", 100, vencimiento="2026-02-10")
    assert situacion(pendiente, hoy="2026-02-09") == PENDIENTE
    assert situacion(pendiente, hoy="2026-02-10") == PENDIENTE   # el mismo día, no
    assert situacion(pendiente, hoy="2026-02-11") == VENCIDA
    assert dias_de_retraso(pendiente, hoy="2026-03-13") == 31


def test_una_factura_sin_vencimiento_nunca_vence():
    assert not esta_vencida(factura("2020-01-01", 100), hoy="2026-10-14")


def test_un_presupuesto_no_tiene_estado_de_cobro():
    oferta = factura("2026-01-10", 100, tipo=PRESUPUESTO, estado="enviado")
    assert situacion(oferta) == "enviado"
    assert not esta_vencida(oferta, hoy="2030-01-01")
    assert not puede_pasar_a(oferta, COBRADA)


def test_el_cobro_se_puede_deshacer():
    """Un recibo devuelto existe: la factura vuelve a estar pendiente."""
    emitida = factura("2026-01-10", 100)
    assert puede_pasar_a(emitida, COBRADA)
    assert not puede_pasar_a(emitida, EMITIDA)

    cobrada = factura("2026-01-10", 100, estado=COBRADA)
    assert puede_pasar_a(cobrada, EMITIDA)
    assert not puede_pasar_a(cobrada, COBRADA)


def test_el_reparto_dice_cuanto_hay_de_cada():
    documentos = [
        factura("2026-01-10", 1000, estado=COBRADA),
        factura("2026-02-10", 500, vencimiento="2026-03-12"),      # vencida
        factura("2026-09-10", 200, vencimiento="2030-01-01"),      # pendiente
        factura("2026-03-10", 7000, tipo=PRESUPUESTO),             # no cuenta
    ]
    cuentas = reparto(documentos, hoy="2026-10-14")
    assert cuentas["documentos"] == {COBRADA: 1, PENDIENTE: 1, VENCIDA: 1}
    assert cuentas["importes"][COBRADA] == Decimal("1210.00")
    assert cuentas["importes"][VENCIDA] == Decimal("605.00")
    assert cuentas["importes"][PENDIENTE] == Decimal("242.00")
