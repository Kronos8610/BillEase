"""
Presupuestos y su conversión en factura (fase 4).

Un presupuesto no tiene valor contable: es una oferta con fecha de caducidad.
Cuando el cliente la acepta se convierte en factura, y solo entonces entra en
la serie de facturación.
"""

import pytest

from core.models import ACEPTADO, BORRADOR, ENVIADO, FACTURA, PRESUPUESTO, RECHAZADO, Linea
from core.quotes import (
    a_factura,
    esta_caducado,
    puede_convertirse,
    puede_pasar_a,
    validez_por_defecto,
    vencimiento_por_defecto,
)
from data.connection import abrir, cerrar
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo
from data.schema import crear_esquema_y_migrar


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Una base vacía y migrada, con un cliente dado de alta."""
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "presupuestos.db"))
    cerrar()
    crear_esquema_y_migrar()
    from core.models import Cliente

    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, codigo_postal="08020")
    )
    yield cliente_id
    cerrar()


def lineas_de_obra():
    return [
        Linea("Suministro y montaje de armario de dos módulos", cantidad=1,
              precio_ud=1240, unidad="ud"),
        Linea("Desmontaje del armario existente", cantidad=1, precio_ud=195, unidad="ud"),
    ]


# ─────────────────────── el ciclo de vida ───────────────────────


def test_un_presupuesto_nace_en_borrador(base):
    doc_id = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    documento = repo.obtener(doc_id)
    assert documento.tipo == PRESUPUESTO
    assert documento.estado == BORRADOR
    assert documento.referencia == "P-2026-001"


def test_las_dos_series_corren_en_paralelo(base):
    """Facturas y presupuestos se numeran por separado y no se pisan."""
    factura = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=FACTURA)
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)

    assert repo.obtener(factura).referencia == "2026-001"
    assert repo.obtener(presupuesto).referencia == "P-2026-001"


def test_el_presupuesto_recorre_sus_estados(base):
    doc_id = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)

    assert repo.cambiar_estado(doc_id, ENVIADO)
    assert repo.obtener(doc_id).estado == ENVIADO
    assert repo.cambiar_estado(doc_id, ACEPTADO)
    assert repo.obtener(doc_id).estado == ACEPTADO


def test_no_se_puede_aceptar_lo_que_no_se_ha_enviado(base):
    doc_id = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    assert not repo.cambiar_estado(doc_id, ACEPTADO)
    assert repo.obtener(doc_id).estado == BORRADOR


def test_un_rechazado_se_puede_volver_a_enviar(base):
    """El cliente cambia de idea más veces de las que uno querría."""
    doc_id = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    repo.cambiar_estado(doc_id, ENVIADO)
    repo.cambiar_estado(doc_id, RECHAZADO)
    assert repo.cambiar_estado(doc_id, ENVIADO)


def test_una_factura_no_tiene_ciclo_de_vida(base):
    factura = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=FACTURA)
    assert not repo.cambiar_estado(factura, ENVIADO)


# ─────────────────────── la conversión ───────────────────────


def test_un_presupuesto_aceptado_se_convierte_en_factura(base):
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO,
                             observaciones="Reforma del dormitorio")
    repo.cambiar_estado(presupuesto, ENVIADO)
    repo.cambiar_estado(presupuesto, ACEPTADO)

    factura_id = repo.facturar_presupuesto(presupuesto, "30/09/2026")
    assert factura_id

    original = repo.obtener(presupuesto)
    factura = repo.obtener(factura_id)

    assert factura.tipo == FACTURA
    assert factura.referencia == "2026-001"          # entra en la serie de facturación
    assert factura.origen_id == presupuesto
    assert factura.cliente_id == original.cliente_id
    assert factura.observaciones == original.observaciones
    assert factura.importe_total == original.importe_total
    assert [(l.descripcion, l.cantidad, l.precio_ud) for l in factura.lineas] == \
           [(l.descripcion, l.cantidad, l.precio_ud) for l in original.lineas]


def test_el_presupuesto_sigue_ahi_despues_de_facturarlo(base):
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    repo.cambiar_estado(presupuesto, ENVIADO)
    repo.cambiar_estado(presupuesto, ACEPTADO)
    repo.facturar_presupuesto(presupuesto)

    assert repo.obtener(presupuesto) is not None
    assert len(repo.listar(PRESUPUESTO)) == 1
    assert len(repo.listar(FACTURA)) == 1


def test_no_se_factura_dos_veces_el_mismo_presupuesto(base):
    """Facturar dos veces el mismo trabajo es cobrarlo dos veces."""
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    repo.cambiar_estado(presupuesto, ENVIADO)
    repo.cambiar_estado(presupuesto, ACEPTADO)

    assert repo.facturar_presupuesto(presupuesto)
    assert repo.facturar_presupuesto(presupuesto) is None
    assert len(repo.listar(FACTURA)) == 1


def test_solo_se_factura_un_presupuesto_aceptado(base):
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    assert repo.facturar_presupuesto(presupuesto) is None
    repo.cambiar_estado(presupuesto, ENVIADO)
    assert repo.facturar_presupuesto(presupuesto) is None


def test_se_puede_saber_qué_factura_salio_de_un_presupuesto(base):
    presupuesto = repo.crear("23/09/2026", base, lineas_de_obra(), tipo=PRESUPUESTO)
    repo.cambiar_estado(presupuesto, ENVIADO)
    repo.cambiar_estado(presupuesto, ACEPTADO)
    assert repo.factura_de(presupuesto) is None

    factura_id = repo.facturar_presupuesto(presupuesto)
    assert repo.factura_de(presupuesto).id == factura_id


# ─────────────────────── plazos ───────────────────────


def test_los_plazos_por_defecto_son_de_treinta_dias():
    assert validez_por_defecto("2026-09-23") == "2026-10-23"
    assert vencimiento_por_defecto("2026-09-23") == "2026-10-23"


def test_un_presupuesto_caduca_si_pasa_su_validez():
    from core.models import Documento

    enviado = Documento(tipo=PRESUPUESTO, estado=ENVIADO, validez="2020-01-01")
    assert esta_caducado(enviado)
    # Uno ya aceptado no caduca: el trabajo está cerrado.
    assert not esta_caducado(Documento(tipo=PRESUPUESTO, estado=ACEPTADO, validez="2020-01-01"))
    # Y una factura no caduca nunca.
    assert not esta_caducado(Documento(tipo=FACTURA, validez="2020-01-01"))


def test_la_conversion_a_factura_exige_estar_aceptado():
    from core.models import Documento

    with pytest.raises(ValueError):
        a_factura(Documento(tipo=PRESUPUESTO, estado=ENVIADO))
