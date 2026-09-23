"""
Pruebas del editor de documentos (fase 4).

Se ejecutan sin pantalla, con `QT_QPA_PLATFORM=offscreen`.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core.models import ACEPTADO, ENVIADO, FACTURA, PRESUPUESTO, Cliente, Linea  # noqa: E402
from core.taxes import calcular  # noqa: E402
from data.connection import cerrar  # noqa: E402
from data.repositories import clientes as repo_clientes  # noqa: E402
from data.repositories import documentos as repo  # noqa: E402
from data.schema import crear_esquema_y_migrar  # noqa: E402

CONCEPTO_LARGO = (
    "Suministro y montaje de armario empotrado de dos módulos con puerta "
    "corredera, acabado en blanco lacado, medidas 2,00 × 2,40 m, incluyendo "
    "herrajes, guía inferior de aluminio anodizado, dos baldas interiores "
    "regulables en altura, barra de colgar cromada, remates de sellado "
    "perimetral y zócalo inferior, con retirada del embalaje, recogida de "
    "restos de obra y limpieza final completa de toda la zona de trabajo."
)


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def base(tmp_path, monkeypatch, app):
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "editor.db"))
    cerrar()
    crear_esquema_y_migrar()
    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, codigo_postal="08020")
    )
    yield cliente_id
    cerrar()


@pytest.fixture
def sin_dialogos(monkeypatch):
    """Los avisos no deben bloquear una prueba sin nadie delante."""
    mensajes = []
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, nombre,
            staticmethod(lambda p, t, m, *a, _n=nombre, **k: mensajes.append((_n, t, m))),
        )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    return mensajes


def editor(tipo=FACTURA, documento_id=None):
    from ui.views.documento_editor import DocumentoEditor

    return DocumentoEditor(tipo=tipo, documento_id=documento_id)


def elegir_cliente(dialogo, cliente_id):
    for i in range(dialogo.cliente_combo.count()):
        cliente = dialogo.cliente_combo.itemData(i)
        if cliente and cliente.id == cliente_id:
            dialogo.cliente_combo.setCurrentIndex(i)
            return
    raise AssertionError("el cliente no está en el desplegable")


def escribir(fila, descripcion, cantidad, precio, unidad="ud"):
    fila.descripcion.setPlainText(descripcion)
    fila.cantidad.setText(str(cantidad))
    fila.precio.setText(str(precio))
    fila.unidad.setCurrentText(unidad)


# ─────────────────────── se escribe, no se elige ───────────────────────


def test_el_concepto_se_escribe_entero(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    escribir(d.filas[0], CONCEPTO_LARGO, 1, "1240")
    d.guardar()

    guardado = repo.obtener(d.documento_id)
    assert guardado.lineas[0].descripcion == CONCEPTO_LARGO
    assert len(guardado.lineas[0].descripcion) > 400


def test_cada_concepto_lleva_su_unidad(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    escribir(d.filas[0], "Instalación de fontanería", 2, "85", unidad="h")
    escribir(d._anadir_fila(), "Pintura interior", 15, "12,50", unidad="m²")
    d.guardar()

    lineas = repo.obtener(d.documento_id).lineas
    assert [l.unidad for l in lineas] == ["h", "m²"]


def test_el_total_en_pantalla_es_el_que_se_guarda(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    escribir(d.filas[0], "Armario a medida", 1, "1240")
    escribir(d._anadir_fila(), "Desmontaje", 1, "195")

    esperado = calcular([
        Linea("Armario a medida", cantidad=1, precio_ud="1240"),
        Linea("Desmontaje", cantidad=1, precio_ud="195"),
    ])
    assert "1.736,35" in d.linea_total.text()   # 1.435,00 + 21 %

    d.guardar()
    guardado = repo.obtener(d.documento_id)
    assert guardado.importe_total == esperado.total


def test_el_importe_de_la_fila_se_recalcula_al_escribir(base, sin_dialogos):
    d = editor()
    fila = d.filas[0]
    escribir(fila, "Pintura", 15, "12,50")
    assert fila.importe.text() == "187,50"
    fila.cantidad.setText("20")
    assert fila.importe.text() == "250,00"


def test_una_fila_a_medias_no_se_guarda(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    escribir(d.filas[0], "Trabajo bueno", 1, "100")
    escribir(d._anadir_fila(), "", 1, "50")          # sin descripción
    escribir(d._anadir_fila(), "Sin precio", 1, "0")  # sin precio
    d.guardar()

    assert len(repo.obtener(d.documento_id).lineas) == 1


def test_no_se_guarda_un_documento_sin_conceptos(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    d.guardar()
    assert d.documento_id is None
    assert any("Falta el trabajo" in t for _, t, _ in sin_dialogos)


def test_no_se_guarda_un_documento_sin_cliente(base, sin_dialogos):
    d = editor()
    escribir(d.filas[0], "Trabajo", 1, "100")
    d.guardar()
    assert d.documento_id is None
    assert any("Falta el cliente" in t for _, t, _ in sin_dialogos)


def test_las_sugerencias_salen_de_lo_ya_escrito(base, sin_dialogos):
    d = editor()
    elegir_cliente(d, base)
    escribir(d.filas[0], "Instalación de fontanería", 1, "85")
    d.guardar()

    assert "Instalación de fontanería" in repo.descripciones_usadas()
    otro = editor()
    assert "Instalación de fontanería" in otro._sugerencias


# ─────────────────────── el defecto 06 ───────────────────────


def test_los_datos_fiscales_del_cliente_no_son_editables(base, sin_dialogos):
    """
    Antes eran seis campos editables cuyo contenido se descartaba al guardar.
    Ahora se enseñan como texto: no parecen editables porque no lo son.
    """
    from PyQt6.QtWidgets import QLineEdit

    d = editor()
    elegir_cliente(d, base)
    assert "B12345674" in d.datos_cliente.text()
    assert not isinstance(d.datos_cliente, QLineEdit)


# ─────────────────────── edición ───────────────────────


def test_se_edita_un_documento_ya_guardado(base, sin_dialogos):
    doc_id = repo.crear("23/09/2026", base, [
        Linea("Trabajo original", cantidad=1, precio_ud=100)
    ])

    d = editor(documento_id=doc_id)
    assert d.filas[0].descripcion.texto() == "Trabajo original"
    escribir(d.filas[0], "Trabajo corregido", 2, "150")
    d.guardar()

    guardado = repo.obtener(doc_id)
    assert guardado.lineas[0].descripcion == "Trabajo corregido"
    assert guardado.base == 300


def test_editar_no_cambia_el_numero_de_serie(base, sin_dialogos):
    doc_id = repo.crear("23/09/2026", base, [Linea("x", cantidad=1, precio_ud=100)])
    antes = repo.obtener(doc_id, con_lineas=False).referencia

    d = editor(documento_id=doc_id)
    escribir(d.filas[0], "otro trabajo", 1, "200")
    d.guardar()

    assert repo.obtener(doc_id, con_lineas=False).referencia == antes


# ─────────────────────── presupuestos ───────────────────────


def test_el_editor_de_presupuesto_pide_validez_y_el_de_factura_vencimiento(base, sin_dialogos):
    presupuesto = editor(tipo=PRESUPUESTO)
    elegir_cliente(presupuesto, base)
    escribir(presupuesto.filas[0], "Obra presupuestada", 1, "1000")
    presupuesto.guardar()

    guardado = repo.obtener(presupuesto.documento_id)
    assert guardado.es_presupuesto
    assert guardado.validez and not guardado.vencimiento

    factura = editor(tipo=FACTURA)
    elegir_cliente(factura, base)
    escribir(factura.filas[0], "Obra facturada", 1, "1000")
    factura.guardar()

    emitida = repo.obtener(factura.documento_id)
    assert emitida.vencimiento and not emitida.validez
