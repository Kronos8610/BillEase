"""
Pruebas de la vista previa.

Lo que se comprueba no es que la ventana se abra, sino que lo que enseña es
el documento de verdad: el PDF se maqueta, tiene las páginas que debe, lo que
se guarda desde ahí es byte por byte lo que se estaba mirando, y en ningún
momento aparece una factura suelta en la carpeta temporal.
"""

import io
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("PyQt6.QtPdfWidgets")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from core.models import Autonomo, Cliente, Linea, PRESUPUESTO  # noqa: E402
from core.taxes import calcular  # noqa: E402
from data.connection import cerrar  # noqa: E402
from data.repositories import autonomo as repo_autonomo  # noqa: E402
from data.repositories import clientes as repo_clientes  # noqa: E402
from data.repositories import documentos as repo  # noqa: E402
from data.schema import crear_esquema_y_migrar  # noqa: E402
from documents.armado import datos_de  # noqa: E402
from ui.views.vista_previa import VistaPrevia  # noqa: E402

EMISOR = Autonomo(
    nif="12345678Z", nombre="Carlos", apellido="García López",
    direccion="Calle Mayor 12, 2ºA", codigo_postal="28001",
    telefono="612345678", email="carlos.garcia@correo.es",
    entidad="Banco Santander", iban="ES9121000418450200051332",
)


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def base(tmp_path, monkeypatch, app):
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "previa.db"))
    cerrar()
    crear_esquema_y_migrar()
    if repo_autonomo.obtener() is None:
        repo_autonomo.registrar(EMISOR, "Pass1234")
    repo_autonomo.actualizar(EMISOR)
    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, direccion="Av. Industria 45",
                codigo_postal="08020")
    )
    yield cliente_id
    cerrar()


def previa_de(cliente_id, lineas=None, **extra):
    """La ventana de vista previa de un documento recién creado."""
    lineas = lineas or [
        Linea("Instalación de fontanería en baño principal", cantidad=2, precio_ud=85),
        Linea("Pintura interior de dormitorio y pasillo", cantidad=15, precio_ud=12.5),
    ]
    documento_id = repo.crear("14/02/2026", cliente_id, lineas, **extra)
    documento = repo.obtener(documento_id)
    cliente = repo_clientes.obtener(documento.cliente_id)
    datos = datos_de(documento, cliente, repo_autonomo.obtener())
    return VistaPrevia(datos, totales=calcular(documento.lineas))


# ─────────────────────── lo que se enseña ───────────────────────


def test_la_previa_enseña_el_pdf_de_verdad(base, app):
    """
    No es un dibujo parecido: es el fichero, maquetado por el mismo generador
    que escribe el que se guarda. Si fueran dos, acabarían discrepando.
    """
    from pypdf import PdfReader

    previa = previa_de(base)
    try:
        assert previa.pdf.startswith(b"%PDF")
        texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(previa.pdf)).pages)
        assert "FACTURA" in texto
        assert "Construcciones Pérez S.L." in texto
        assert "Instalación de fontanería en baño principal" in texto
        assert "ES91 2100 0418 4502 0005 1332" in texto
    finally:
        previa.close()


def test_un_presupuesto_se_previsualiza_con_su_rotulo(base, app):
    previa = previa_de(base, tipo=PRESUPUESTO)
    try:
        assert previa.rotulo == "Presupuesto"
        assert previa.windowTitle().startswith("Vista previa · Presupuesto")
    finally:
        previa.close()


def test_la_previa_cuenta_las_paginas_de_un_documento_largo(base, app):
    lineas = [
        Linea(f"Concepto {i} de una obra larga que ocupa dos renglones en el papel",
              cantidad=2, precio_ud=47.3)
        for i in range(1, 46)
    ]
    previa = previa_de(base, lineas=lineas)
    try:
        assert previa._paginas > 1
        assert previa.documento.pageCount() == previa._paginas
        assert previa.etiqueta_pagina.text() == f"Página 1 de {previa._paginas}"
    finally:
        previa.close()


# ─────────────────────── páginas y zoom ───────────────────────


def test_se_pasa_de_pagina_y_el_pie_lo_dice(base, app):
    lineas = [
        Linea(f"Concepto {i} de una obra larga que ocupa dos renglones en el papel",
              cantidad=2, precio_ud=47.3)
        for i in range(1, 46)
    ]
    previa = previa_de(base, lineas=lineas)
    try:
        previa.show()
        app.processEvents()

        assert previa.pagina() == 0
        assert not previa.boton_anterior.isEnabled()
        assert previa.boton_siguiente.isEnabled()

        previa.ir_a(1)
        app.processEvents()
        assert previa.pagina() == 1
        assert previa.etiqueta_pagina.text() == f"Página 2 de {previa._paginas}"
        assert previa.boton_anterior.isEnabled()

        # No se puede pasar de la última ni retroceder de la primera.
        previa.ir_a(previa._paginas + 5)
        assert previa.pagina() == previa._paginas - 1
        assert not previa.boton_siguiente.isEnabled()
        previa.ir_a(-3)
        assert previa.pagina() == 0
    finally:
        previa.close()


def test_el_zoom_no_miente_mientras_la_pagina_esta_ajustada(base, app):
    """
    Con el modo «ajustar», Qt deja `zoomFactor()` en 1,0 aunque la página se
    vea al 70 %. Enseñar «100 %» ahí sería mentir, así que pone «Ajustada».
    """
    previa = previa_de(base)
    try:
        previa.show()
        app.processEvents()
        assert previa.ajustada()
        assert previa.etiqueta_zoom.text() == "Ajustada"

        previa.acercar()            # el primer toque siempre lleva al 100 %
        assert not previa.ajustada()
        assert previa.etiqueta_zoom.text() == "100 %"

        previa.acercar()
        assert previa.etiqueta_zoom.text() == "125 %"
        previa.alejar()
        previa.alejar()
        assert previa.etiqueta_zoom.text() == "75 %"

        previa.ajustar()
        assert previa.etiqueta_zoom.text() == "Ajustada"
    finally:
        previa.close()


def test_el_zoom_tiene_tope_arriba_y_abajo(base, app):
    previa = previa_de(base)
    try:
        previa.show()
        app.processEvents()
        for _ in range(12):
            previa.acercar()
        assert previa.etiqueta_zoom.text() == "300 %"
        for _ in range(12):
            previa.alejar()
        assert previa.etiqueta_zoom.text() == "50 %"
    finally:
        previa.close()


# ─────────────────────── guardar y limpiar ───────────────────────


def test_lo_que_se_guarda_es_lo_que_se_estaba_mirando(base, app, tmp_path, monkeypatch):
    """
    Se copia el fichero, no se vuelve a generar: si se regenerara, lo guardado
    podría no ser lo que se acaba de revisar.
    """
    destino = tmp_path / "guardada.pdf"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(destino), "PDF (*.pdf)")),
    )
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )

    previa = previa_de(base)
    try:
        assert previa.guardar() == str(destino)
        assert destino.read_bytes() == previa.pdf
    finally:
        previa.close()


def test_si_no_se_elige_fichero_no_se_guarda_nada(base, app, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    previa = previa_de(base)
    try:
        assert previa.guardar() is None
    finally:
        previa.close()


def test_la_previa_no_escribe_nada_en_la_carpeta_temporal(base, app):
    """
    El PDF lleva dentro el NIF del cliente y lo que se le cobra, así que no
    puede pasar por %TEMP% ni un momento.

    La primera versión sí lo escribía y lo borraba al cerrar, y en Windows el
    borrado fallaba en silencio: el motor de PDF no suelta el fichero
    mientras el documento está abierto. Cada vistazo dejaba una factura allí.
    Por eso esto mira la carpeta entera antes y después, y no solo si un
    fichero concreto se ha borrado: lo que no se escribe no se puede quedar.
    """
    import tempfile

    temporales = Path(tempfile.gettempdir())
    antes = set(temporales.iterdir())

    previa = previa_de(base)
    durante = set(temporales.iterdir()) - antes
    assert previa.pdf.startswith(b"%PDF"), "no se ha maquetado nada"
    assert durante == set(), f"ha aparecido algo en la carpeta temporal: {durante}"

    previa.close()
    assert set(temporales.iterdir()) - antes == set()


def test_cerrar_dos_veces_no_revienta(base, app):
    previa = previa_de(base)
    previa.close()
    previa.close()
