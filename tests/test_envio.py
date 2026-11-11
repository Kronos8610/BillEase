"""
Pruebas de «Enviármelo»: el PDF al Gmail o al WhatsApp del propio autónomo.

No se manda ningún correo de verdad: el servidor es de mentira y apunta lo
que le llega. Lo que se comprueba es que el mensaje va de la cuenta a sí
misma con el PDF dentro, que la contraseña no acaba en la base de datos, y
que los fallos se explican en cristiano.
"""

import os
import smtplib
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from core import correo, llavero, whatsapp  # noqa: E402
from core.models import Autonomo, Cliente, Linea  # noqa: E402
from data.connection import cerrar  # noqa: E402
from data.repositories import autonomo as repo_autonomo  # noqa: E402
from data.repositories import clientes as repo_clientes  # noqa: E402
from data.repositories import documentos as repo  # noqa: E402
from data.schema import crear_esquema_y_migrar  # noqa: E402

CUENTA = "carlos.garcia@gmail.com"
CLAVE = "abcdefghijklmnop"
PDF = b"%PDF-1.4 un pdf de mentira"


class ServidorDeMentira:
    """Hace de `smtplib.SMTP_SSL`: apunta lo que le mandan y no manda nada."""

    def __init__(self, fallo=None):
        self.fallo = fallo
        self.entradas = []
        self.mensajes = []

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, cuenta, clave):
        if self.fallo:
            raise self.fallo
        self.entradas.append((cuenta, clave))

    def send_message(self, mensaje):
        self.mensajes.append(mensaje)


# ─────────────────────── el correo ───────────────────────


def test_el_correo_va_de_la_cuenta_a_si_misma_con_el_pdf_dentro():
    servidor = ServidorDeMentira()
    correo.enviar(CUENTA, CLAVE, PDF, "2026-001.pdf", "Factura 2026-001", "Hola",
                  conectar=servidor)

    assert servidor.entradas == [(CUENTA, CLAVE)]
    mensaje = servidor.mensajes[0]
    assert mensaje["From"] == CUENTA and mensaje["To"] == CUENTA
    assert mensaje["Subject"] == "Factura 2026-001"

    adjuntos = list(mensaje.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "2026-001.pdf"
    assert adjuntos[0].get_content_type() == "application/pdf"
    assert adjuntos[0].get_payload(decode=True) == PDF


def test_la_contrasena_se_acepta_como_la_ensena_google():
    """Google la da en cuatro grupos con espacios, y así se pega."""
    servidor = ServidorDeMentira()
    correo.enviar(CUENTA, "abcd efgh ijkl mnop", PDF, "f.pdf", "a", "b", conectar=servidor)
    assert servidor.entradas == [(CUENTA, "abcdefghijklmnop")]


def test_una_contrasena_rechazada_se_explica_sin_jerga():
    servidor = ServidorDeMentira(smtplib.SMTPAuthenticationError(535, b"BadCredentials"))
    with pytest.raises(correo.ErrorDeCorreo) as error:
        correo.enviar(CUENTA, CLAVE, PDF, "f.pdf", "a", "b", conectar=servidor)
    assert "contraseña de aplicación" in str(error.value)
    assert "535" not in str(error.value)


def test_sin_red_se_dice_que_no_hay_red():
    servidor = ServidorDeMentira(OSError("Network is unreachable"))
    with pytest.raises(correo.ErrorDeCorreo) as error:
        correo.enviar(CUENTA, CLAVE, PDF, "f.pdf", "a", "b", conectar=servidor)
    assert "internet" in str(error.value)


def test_sin_cuenta_o_sin_clave_no_se_intenta_nada():
    servidor = ServidorDeMentira()
    for cuenta, clave in (("", CLAVE), (CUENTA, ""), (CUENTA, "   ")):
        with pytest.raises(correo.ErrorDeCorreo):
            correo.enviar(cuenta, clave, PDF, "f.pdf", "a", "b", conectar=servidor)
    assert servidor.entradas == []


# ─────────────────────── WhatsApp ───────────────────────


@pytest.mark.parametrize("telefono, esperado", [
    ("612345678", "34612345678"),
    ("612 34 56 78", "34612345678"),
    ("+34 612 345 678", "34612345678"),
    ("0034612345678", "34612345678"),
    ("+44 7700 900123", "447700900123"),
    ("", ""),
    (None, ""),
])
def test_el_telefono_sale_como_lo_quiere_whatsapp(telefono, esperado):
    assert whatsapp.numero_internacional(telefono) == esperado


def test_el_enlace_abre_el_chat_con_el_texto_escrito():
    enlace = whatsapp.enlace("612345678", "Factura 2026-001 · 650,38 €")
    assert enlace.startswith("https://wa.me/34612345678?text=Factura%202026-001")
    assert " " not in enlace
    assert whatsapp.enlace("") == ""


# ─────────────────────── la interfaz ───────────────────────


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def llavero_de_mentira(monkeypatch):
    """Un llavero en memoria: las pruebas no tocan el del sistema."""
    guardado = {}
    monkeypatch.setattr(llavero, "guardar", lambda c, k: guardado.__setitem__(c, k))
    monkeypatch.setattr(llavero, "leer", lambda c: guardado.get(c, ""))
    monkeypatch.setattr(llavero, "borrar", lambda c: guardado.pop(c, None))
    return guardado


@pytest.fixture
def base(tmp_path, monkeypatch, app, llavero_de_mentira):
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "envio.db"))
    cerrar()
    crear_esquema_y_migrar()
    emisor = Autonomo(nif="12345678Z", nombre="Carlos", apellido="García",
                      direccion="Calle Mayor 12", codigo_postal="28001",
                      telefono="612345678", email="carlos@correo.es")
    repo_autonomo.registrar(emisor, "Pass1234")
    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, codigo_postal="08020"))
    repo.crear("14/02/2026", cliente_id, [Linea("Armario", cantidad=1, precio_ud=1000)])
    yield tmp_path
    cerrar()


@pytest.fixture
def avisos(monkeypatch):
    dichos = []
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, nombre,
            staticmethod(lambda p, t, m, *a, _n=nombre, **k: dichos.append((_n, t, m))),
        )
    return dichos


def listado_con_la_factura():
    from ui.views.listado import FACTURAS, Listado

    listado = Listado(FACTURAS)
    listado.vista.selectRow(0)
    return listado


def test_sin_configurar_el_correo_se_dice_donde_hacerlo(base, avisos, monkeypatch):
    enviados = []
    monkeypatch.setattr(correo, "enviar", lambda *a, **k: enviados.append(a))

    listado_con_la_factura()._enviar_por_correo()

    assert enviados == []
    assert any("Ajustes" in mensaje for _, _, mensaje in avisos)


def test_la_factura_sale_por_correo_con_su_numero_de_nombre(
    base, avisos, monkeypatch, llavero_de_mentira
):
    repo_autonomo.guardar_correo_envio(CUENTA)
    llavero_de_mentira[CUENTA] = CLAVE
    enviados = []
    monkeypatch.setattr(correo, "enviar", lambda *a, **k: enviados.append(a))

    listado = listado_con_la_factura()
    listado._enviar_por_correo()

    cuenta, clave, pdf, nombre, asunto, _cuerpo = enviados[0]
    assert (cuenta, clave) == (CUENTA, CLAVE)
    assert pdf.startswith(b"%PDF")
    assert nombre == f"{listado.seleccionado().referencia}.pdf"
    assert "Construcciones Pérez S.L." in asunto and "1.210,00 €" in asunto
    assert avisos[-1][1] == "Enviado"


def test_si_gmail_rechaza_la_clave_se_avisa_y_no_se_dice_enviado(
    base, avisos, monkeypatch, llavero_de_mentira
):
    repo_autonomo.guardar_correo_envio(CUENTA)
    llavero_de_mentira[CUENTA] = CLAVE

    def revienta(*_a, **_k):
        raise correo.ErrorDeCorreo("Gmail no ha aceptado la contraseña.")

    monkeypatch.setattr(correo, "enviar", revienta)
    listado_con_la_factura()._enviar_por_correo()

    assert [titulo for _, titulo, _ in avisos] == ["No se ha enviado"]
    # Y el cursor de espera no se queda puesto para siempre.
    assert QApplication.overrideCursor() is None


def test_por_whatsapp_se_guarda_el_pdf_se_copia_y_se_abre_el_chat(
    base, avisos, monkeypatch
):
    from PyQt6.QtGui import QDesktopServices, QGuiApplication

    destino = base / "para-whatsapp.pdf"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(destino), ""))
    )
    abiertos = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", staticmethod(lambda url: abiertos.append(url.toString()))
    )

    listado_con_la_factura()._enviar_por_whatsapp()

    assert destino.read_bytes().startswith(b"%PDF")
    assert abiertos and abiertos[0].startswith("https://wa.me/34612345678?text=")
    # Se comparan como rutas y no como texto: Qt las da con «/» y Windows
    # con «\\», y son el mismo fichero.
    from pathlib import Path

    copiados = [Path(u.toLocalFile()) for u in QGuiApplication.clipboard().mimeData().urls()]
    assert copiados == [destino]
    assert "Ctrl+V" in avisos[-1][2]


def test_sin_telefono_whatsapp_dice_donde_ponerlo(base, avisos, monkeypatch):
    from PyQt6.QtGui import QDesktopServices

    emisor = repo_autonomo.obtener()
    repo_autonomo.actualizar(Autonomo(
        nif=emisor.nif, nombre=emisor.nombre, apellido=emisor.apellido,
        direccion=emisor.direccion, codigo_postal=emisor.codigo_postal,
        telefono="", email=emisor.email))
    abiertos = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", staticmethod(lambda url: abiertos.append(url))
    )

    listado_con_la_factura()._enviar_por_whatsapp()

    assert abiertos == []
    assert any("teléfono" in titulo for _, titulo, _ in avisos)


# ─────────────────────── Ajustes y la contraseña ───────────────────────


def test_la_contrasena_va_al_llavero_y_no_a_la_base(base, llavero_de_mentira):
    """
    Si la base no está cifrada, cualquiera la abre con un visor de SQLite.
    La contraseña que deja mandar correo no puede estar ahí.
    """
    from ui.views.ajustes import Ajustes

    pantalla = Ajustes()
    pantalla.cuenta_envio.setText(CUENTA)
    pantalla.clave_envio.setText("abcd efgh ijkl mnop")
    assert pantalla._guardar_envio()

    assert llavero_de_mentira == {CUENTA: CLAVE}
    assert repo_autonomo.obtener().correo_envio == CUENTA
    assert pantalla.clave_envio.text() == "", "la contraseña no se vuelve a enseñar"

    cerrar()
    crudo = (base / "envio.db").read_bytes()
    assert CLAVE.encode() not in crudo
    volcado = "\n".join(sqlite3.connect(base / "envio.db").iterdump())
    assert CLAVE not in volcado


def test_quitar_olvida_la_cuenta_y_la_contrasena(base, llavero_de_mentira):
    from ui.views.ajustes import Ajustes

    repo_autonomo.guardar_correo_envio(CUENTA)
    llavero_de_mentira[CUENTA] = CLAVE

    pantalla = Ajustes()
    assert pantalla.boton_prueba.isEnabled()
    pantalla._quitar_envio()

    assert llavero_de_mentira == {}
    assert repo_autonomo.obtener().correo_envio == ""
    assert not pantalla.boton_prueba.isEnabled()


def test_una_direccion_que_no_es_un_correo_no_se_guarda(base, llavero_de_mentira):
    from ui.views.ajustes import Ajustes

    pantalla = Ajustes()
    pantalla.cuenta_envio.setText("esto no es un correo")
    pantalla.clave_envio.setText(CLAVE)
    assert not pantalla._guardar_envio()
    assert llavero_de_mentira == {}


def test_sin_llavero_no_se_guarda_en_otro_sitio(base, monkeypatch, avisos):
    """Mejor decir que no se puede que guardarla donde no debe."""
    from ui.views.ajustes import Ajustes

    def no_hay(*_):
        raise llavero.LlaveroNoDisponible("Este sistema no tiene llavero.")

    monkeypatch.setattr(llavero, "guardar", no_hay)
    pantalla = Ajustes()
    pantalla.cuenta_envio.setText(CUENTA)
    pantalla.clave_envio.setText(CLAVE)

    assert not pantalla._guardar_envio()
    assert repo_autonomo.obtener().correo_envio == ""
    assert avisos[-1][0] == "critical"
