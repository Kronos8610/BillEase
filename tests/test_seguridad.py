"""
Pruebas del cifrado y del acceso.

Lo que se comprueba aquí es lo que un autónomo tiene derecho a dar por hecho
cuando le dicen que sus datos están cifrados:

- que el fichero **no deja leer** ni un NIF sin la contraseña,
- que una contraseña equivocada **no abre nada**,
- que si alguien toca un byte del fichero **se nota**,
- que el código de recuperación **salva** una contraseña olvidada,
- y que cambiar la contraseña **no pierde** ni una factura.

Las pruebas no confían en el código: abren el fichero en crudo y buscan dentro.
"""

import sqlite3
from decimal import Decimal

import pytest

from core.cifrado import (
    CajaCorrupta,
    ClaveIncorrecta,
    FormatoDesconocido,
    desempaquetar,
    empaquetar,
    normalizar_codigo,
    nueva_cabecera,
    nuevo_codigo,
)
from core.models import Cliente, Linea
from data import backup, caja, connection
from data.repositories import autonomo as repo_autonomo
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo
from data.schema import crear_esquema_y_migrar

CONTRASENA = "Pass1234"
SECRETOS = (b"B12345674", "Construcciones Pérez".encode(),
            b"Armario a medida", b"SQLite format 3")


# ─────────────────────────── el cifrado ───────────────────────────


def test_lo_cifrado_no_se_parece_a_lo_de_dentro():
    cabecera, clave, _ = nueva_cabecera(CONTRASENA)
    datos = b"SQLite format 3\x00" + b"NIF B12345674 de Construcciones" * 50

    paquete = empaquetar(datos, clave, cabecera)

    assert b"B12345674" not in paquete
    assert b"SQLite format 3" not in paquete
    assert desempaquetar(paquete, contrasena=CONTRASENA)[0] == datos


def test_dos_cajas_con_la_misma_contrasena_no_se_parecen():
    """Cada caja tiene su sal y su clave: una no dice nada de la otra."""
    datos = b"los mismos datos"
    uno = empaquetar(datos, *_caja_nueva())
    otro = empaquetar(datos, *_caja_nueva())
    assert uno != otro


def _caja_nueva():
    cabecera, clave, _ = nueva_cabecera(CONTRASENA)
    return clave, cabecera


def test_una_contrasena_equivocada_no_abre():
    cabecera, clave, _ = nueva_cabecera(CONTRASENA)
    paquete = empaquetar(b"datos", clave, cabecera)

    for intento in ("pass1234", "Pass1235", "", "Pass1234 "):
        with pytest.raises(ClaveIncorrecta):
            desempaquetar(paquete, contrasena=intento)


@pytest.mark.parametrize("donde", [20, 60, -40, -1])
def test_si_tocan_un_byte_se_nota(donde):
    """
    AES-GCM autentica: un fichero manipulado no se abre «a medias».

    Da igual que el byte esté en la cabecera o en los datos.
    """
    cabecera, clave, _ = nueva_cabecera(CONTRASENA)
    paquete = bytearray(empaquetar(b"x" * 500, clave, cabecera))
    paquete[donde] ^= 0x01

    with pytest.raises((CajaCorrupta, ClaveIncorrecta, FormatoDesconocido)):
        desempaquetar(bytes(paquete), contrasena=CONTRASENA)


def test_un_fichero_cualquiera_no_es_una_caja():
    with pytest.raises(FormatoDesconocido):
        desempaquetar(b"SQLite format 3\x00 esto es una base normal",
                      contrasena=CONTRASENA)


def test_el_codigo_de_recuperacion_se_escribe_como_se_quiera():
    codigo = nuevo_codigo()
    assert len(codigo.replace("-", "")) == 32
    assert codigo.count("-") == 7

    cabecera, clave, codigo = nueva_cabecera(CONTRASENA)
    paquete = empaquetar(b"datos", clave, cabecera)

    for version in (codigo, codigo.lower(), codigo.replace("-", ""),
                    codigo.replace("-", " "), f"  {codigo}  "):
        assert desempaquetar(paquete, codigo=version)[0] == b"datos"


def test_el_codigo_perdona_los_ceros_y_los_unos():
    """Nadie distingue una O de un cero al copiar a mano. El alfabeto no los usa."""
    assert normalizar_codigo("0IL1") == "OILI"
    assert "0" not in normalizar_codigo(nuevo_codigo())


def test_un_codigo_inventado_no_abre_nada():
    cabecera, clave, _ = nueva_cabecera(CONTRASENA)
    paquete = empaquetar(b"datos", clave, cabecera)
    with pytest.raises(ClaveIncorrecta):
        desempaquetar(paquete, codigo=nuevo_codigo())


# ─────────────────────────── la caja ───────────────────────────


@pytest.fixture
def cifrada(tmp_path, monkeypatch):
    """Una base cifrada, con esquema, un cliente y una factura."""
    ruta = tmp_path / "billease.db"
    monkeypatch.setenv("BILLEASE_DB", str(ruta))
    connection.cerrar()

    conn, codigo = caja.crear(ruta, CONTRASENA)
    connection.adoptar(conn)
    crear_esquema_y_migrar(conn)
    repo_autonomo.registrar(
        _autonomo(), CONTRASENA
    )
    cliente = repo_clientes.crear(Cliente(
        nombre="Construcciones Pérez S.L.", nif="B12345674",
        es_persona_fisica=False, codigo_postal="08020",
    ))
    repo.crear("26/10/2026", cliente, [
        Linea("Armario a medida", cantidad=1, precio_ud=1240)
    ])
    yield {"ruta": ruta, "codigo": codigo}
    connection.cerrar()


def _autonomo():
    from core.models import Autonomo

    return Autonomo(nif="12345678Z", nombre="Carlos", apellido="García López",
                    direccion="Calle Mayor 12", codigo_postal="28001",
                    telefono="612345678", email="carlos@billease.es")


def test_en_el_disco_no_hay_nada_legible(cifrada):
    connection.cerrar()
    crudo = cifrada["ruta"].read_bytes()

    assert caja.es_caja(cifrada["ruta"])
    for secreto in SECRETOS:
        assert secreto not in crudo, f"se ve {secreto!r} en el fichero"


def test_un_visor_de_sqlite_no_puede_abrir_la_caja(cifrada):
    connection.cerrar()
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(cifrada["ruta"]).execute("SELECT * FROM Cliente").fetchall()


def test_con_la_contrasena_vuelve_todo(cifrada):
    connection.cerrar()
    connection.abrir_caja(cifrada["ruta"], contrasena=CONTRASENA)

    assert [c.nombre for c in repo_clientes.listar()] == ["Construcciones Pérez S.L."]
    documento = repo.obtener(repo.listar()[0].id)
    assert documento.lineas[0].descripcion == "Armario a medida"
    assert documento.importe_total == Decimal("1500.40")


def test_sin_la_contrasena_no_hay_manera(cifrada):
    connection.cerrar()
    with pytest.raises(ClaveIncorrecta):
        connection.abrir_caja(cifrada["ruta"], contrasena="otra cosa")
    # Y nadie abre la base por detrás creando una vacía encima.
    with pytest.raises(ClaveIncorrecta):
        connection.conexion()


def test_el_codigo_abre_la_base_entera(cifrada):
    connection.cerrar()
    connection.abrir_caja(cifrada["ruta"], codigo=cifrada["codigo"])
    assert len(repo.listar()) == 1


def test_cada_commit_queda_guardado(cifrada):
    """
    Un corte de luz no puede costar una factura.

    Se escribe, se tira la conexión sin cerrarla bien —como haría un apagón— y
    se vuelve a abrir el fichero.
    """
    cliente = repo_clientes.listar()[0]
    repo.crear("27/10/2026", cliente.id, [Linea("Otra", cantidad=1, precio_ud=100)])

    connection.conexion().close()        # ni `cerrar()` ni guardado explícito
    connection._local.conn = None

    connection.abrir_caja(cifrada["ruta"], contrasena=CONTRASENA)
    assert len(repo.listar()) == 2


def test_cambiar_la_contrasena_no_pierde_nada(cifrada):
    assert connection.cambiar_contrasena("Cambiada9")

    connection.cerrar()
    with pytest.raises(ClaveIncorrecta):
        caja.abrir(cifrada["ruta"], contrasena=CONTRASENA)

    connection.abrir_caja(cifrada["ruta"], contrasena="Cambiada9")
    assert len(repo.listar()) == 1
    assert repo_clientes.listar()[0].nif == "B12345674"


def test_el_codigo_sigue_valiendo_despues_de_cambiar_la_contrasena(cifrada):
    """Por eso abre también las copias de seguridad antiguas."""
    connection.cambiar_contrasena("Cambiada9")
    connection.cerrar()

    connection.abrir_caja(cifrada["ruta"], codigo=cifrada["codigo"])
    assert len(repo.listar()) == 1


def test_una_copia_antigua_se_abre_con_el_codigo(cifrada):
    copia = backup.copiar(cifrada["ruta"])
    connection.cambiar_contrasena("Cambiada9")
    connection.cerrar()

    # La copia se hizo con la contraseña de antes: esa la abre, la nueva no.
    assert caja.abrir(copia, contrasena=CONTRASENA)
    with pytest.raises(ClaveIncorrecta):
        caja.abrir(copia, contrasena="Cambiada9")
    assert caja.abrir(copia, codigo=cifrada["codigo"])


def test_las_copias_de_una_base_cifrada_tambien_van_cifradas(cifrada):
    copia = backup.copiar(cifrada["ruta"])
    assert caja.es_caja(copia)
    crudo = copia.read_bytes()
    for secreto in SECRETOS:
        assert secreto not in crudo


def test_se_restaura_una_copia_cifrada(cifrada):
    copia = backup.copiar(cifrada["ruta"])
    for documento in repo.listar():
        repo.eliminar(documento.id)
    assert repo.listar() == []
    connection.cerrar()

    backup.restaurar(copia, cifrada["ruta"])
    connection.abrir_caja(cifrada["ruta"], contrasena=CONTRASENA)
    assert len(repo.listar()) == 1


def test_el_usuario_puede_sacar_sus_datos(cifrada, tmp_path):
    """Un programa que te encierra los datos dentro no protege: secuestra."""
    connection.cerrar()
    fuera = caja.descifrar(cifrada["ruta"], CONTRASENA, tmp_path / "mios.db")

    suelta = sqlite3.connect(fuera)
    assert suelta.execute(
        "SELECT nombre_o_razon_social FROM Cliente"
    ).fetchone()[0] == "Construcciones Pérez S.L."
    suelta.close()


def test_sin_contrasena_no_se_puede_sacar_nada(cifrada, tmp_path):
    connection.cerrar()
    with pytest.raises(ClaveIncorrecta):
        caja.descifrar(cifrada["ruta"], "la que sea", tmp_path / "no.db")


# ─────────────────── pasar de claro a cifrado ───────────────────


@pytest.fixture
def en_claro(tmp_path, monkeypatch):
    """Una base sin cifrar, como la de quien viene de una versión anterior."""
    ruta = tmp_path / "billease.db"
    monkeypatch.setenv("BILLEASE_DB", str(ruta))
    connection.cerrar()
    crear_esquema_y_migrar()
    repo_autonomo.registrar(_autonomo(), CONTRASENA)
    cliente = repo_clientes.crear(Cliente(
        nombre="Construcciones Pérez S.L.", nif="B12345674", es_persona_fisica=False
    ))
    repo.crear("26/10/2026", cliente, [Linea("Armario a medida", cantidad=1, precio_ud=1240)])
    yield ruta
    connection.cerrar()


def test_una_base_en_claro_se_lee_sin_nada(en_claro):
    """El punto de partida: así están hoy los datos de cualquier instalación."""
    connection.cerrar()
    suelta = sqlite3.connect(en_claro)
    assert suelta.execute("SELECT CIFNIF FROM Cliente").fetchone()[0] == "B12345674"
    suelta.close()
    assert not caja.es_caja(en_claro)


def test_cifrar_una_base_que_ya_tenia_datos(en_claro):
    antes = len(repo.listar())
    connection.cerrar()

    _, codigo = caja.cifrar(en_claro, CONTRASENA)

    assert caja.es_caja(en_claro)
    assert b"B12345674" not in en_claro.read_bytes()

    connection.abrir_caja(en_claro, contrasena=CONTRASENA)
    assert len(repo.listar()) == antes
    assert repo_clientes.listar()[0].nif == "B12345674"
    assert codigo


def test_cifrar_dos_veces_no_tiene_sentido_y_se_avisa(en_claro):
    connection.cerrar()
    caja.cifrar(en_claro, CONTRASENA)
    with pytest.raises(caja.ErrorDeCifrado):
        caja.cifrar(en_claro, CONTRASENA)


# ─────────────────────────── el acceso ───────────────────────────


def test_la_contrasena_del_autonomo_se_comprueba(en_claro):
    assert repo_autonomo.verificar_contrasena(CONTRASENA)
    assert not repo_autonomo.verificar_contrasena("otra")
    assert repo_autonomo.hay_autonomo()


def test_la_contrasena_guardada_nunca_esta_en_claro(cifrada):
    guardada = connection.conexion().execute(
        "SELECT contrasena FROM Autonomo"
    ).fetchone()[0]
    assert guardada != CONTRASENA
    assert guardada.startswith("$argon2id$")


def test_cambiar_la_contrasena_cambia_las_dos_cosas(cifrada):
    """La de la caja y la que se guarda cifrada tienen que moverse juntas."""
    connection.cambiar_contrasena("Cambiada9")
    repo_autonomo.cambiar_contrasena("Cambiada9")

    assert repo_autonomo.verificar_contrasena("Cambiada9")
    assert not repo_autonomo.verificar_contrasena(CONTRASENA)

    connection.cerrar()
    assert caja.abrir(cifrada["ruta"], contrasena="Cambiada9")


# ─────────────────────── la pantalla de acceso ───────────────────────


@pytest.fixture(scope="session")
def app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication

    import theme

    aplicacion = QApplication.instance() or QApplication([])
    theme.aplicar_tema(aplicacion, "claro")
    return aplicacion


@pytest.fixture
def sin_dialogos(monkeypatch):
    """
    Un aviso modal en una prueba se queda esperando un clic que no llega.

    Se sustituyen por una lista, que además sirve para comprobar qué se le
    dijo al usuario.
    """
    from PyQt6.QtWidgets import QMessageBox

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


def test_la_pantalla_de_acceso_abre_la_caja(cifrada, app):
    from ui.views.acceso import VentanaAcceso

    connection.cerrar()
    entradas = []
    ventana = VentanaAcceso(cifrada["ruta"], al_entrar=lambda: entradas.append(1))

    ventana._comprobar("la que no es")
    assert entradas == []
    assert "incorrecta" in ventana.error.text()

    ventana._comprobar(CONTRASENA)
    assert entradas == [1]
    assert ventana.error.text() == ""
    assert len(repo.listar()) == 1


def test_tras_varios_intentos_hay_que_esperar(cifrada, app):
    """Argon2 ya hace lento probar contraseñas; esto lo hace además incómodo."""
    from ui.views.acceso import INTENTOS_LIBRES, VentanaAcceso

    connection.cerrar()
    ventana = VentanaAcceso(cifrada["ruta"], al_entrar=lambda: None)

    for _ in range(INTENTOS_LIBRES):
        ventana._comprobar("no es")

    assert not ventana.boton.isEnabled()
    assert "Espera" in ventana.error.text()


def test_con_la_base_en_claro_la_pantalla_lo_dice(en_claro, app):
    """No se puede dar a entender que protege lo que no protege."""
    from ui.views.acceso import VentanaAcceso

    connection.cerrar()
    ventana = VentanaAcceso(en_claro, al_entrar=lambda: None)

    assert not ventana.cifrada
    assert "NO están cifrados" in ventana.explicacion.text()

    entradas = []
    ventana.al_entrar = lambda: entradas.append(1)
    ventana._comprobar("otra cosa")
    assert entradas == []
    ventana._comprobar(CONTRASENA)
    assert entradas == [1]


def test_el_dialogo_de_recuperacion_devuelve_el_acceso(cifrada, app, sin_dialogos):
    from ui.views.acceso import DialogoRecuperacion

    connection.cerrar()
    dialogo = DialogoRecuperacion(cifrada["ruta"])
    dialogo.codigo.setText(cifrada["codigo"].lower())
    dialogo.nueva.setText("Recuperada7")
    dialogo.repetida.setText("Recuperada7")
    dialogo.recuperar()

    assert dialogo.error.text() == ""
    assert len(repo.listar()) == 1
    assert repo_autonomo.verificar_contrasena("Recuperada7")


def test_la_recuperacion_exige_un_codigo_que_valga(cifrada, app):
    from ui.views.acceso import DialogoRecuperacion

    connection.cerrar()
    dialogo = DialogoRecuperacion(cifrada["ruta"])
    dialogo.codigo.setText(nuevo_codigo())
    dialogo.nueva.setText("Recuperada7")
    dialogo.repetida.setText("Recuperada7")
    dialogo.recuperar()

    assert "no abre esta base" in dialogo.error.text()
    assert caja.abrir(cifrada["ruta"], contrasena=CONTRASENA)


def test_la_recuperacion_exige_una_contrasena_decente(cifrada, app):
    from ui.views.acceso import DialogoRecuperacion

    connection.cerrar()
    dialogo = DialogoRecuperacion(cifrada["ruta"])
    dialogo.codigo.setText(cifrada["codigo"])
    dialogo.nueva.setText("corta")
    dialogo.repetida.setText("otra")
    dialogo.recuperar()
    assert "no coinciden" in dialogo.error.text()

    dialogo.repetida.setText("corta")
    dialogo.recuperar()
    assert "8 caracteres" in dialogo.error.text()


def test_el_dialogo_de_cambio_mueve_las_dos_contrasenas(cifrada, app, sin_dialogos):
    from ui.views.seguridad import DialogoCambioContrasena

    dialogo = DialogoCambioContrasena(cifrada["ruta"])
    dialogo.actual.setText("la que no es")
    dialogo.nueva.setText("Cambiada9")
    dialogo.repetida.setText("Cambiada9")
    dialogo.cambiar()
    assert "no es correcta" in dialogo.error.text()

    dialogo.actual.setText(CONTRASENA)
    dialogo.cambiar()
    assert dialogo.error.text() == ""
    assert repo_autonomo.verificar_contrasena("Cambiada9")

    connection.cerrar()
    assert caja.abrir(cifrada["ruta"], contrasena="Cambiada9")
    with pytest.raises(ClaveIncorrecta):
        caja.abrir(cifrada["ruta"], contrasena=CONTRASENA)


def test_el_alta_inicial_deja_la_base_cifrada(tmp_path, monkeypatch, app, sin_dialogos):
    """Una instalación nueva nace cifrada, sin tener que acordarse de nada."""
    from PyQt6.QtWidgets import QDialog

    from ui.views import registro as modulo_registro

    ruta = tmp_path / "billease.db"
    monkeypatch.setenv("BILLEASE_DB", str(ruta))
    connection.cerrar()

    codigos = []

    class CodigoDePrueba(QDialog):
        def __init__(self, codigo, parent=None):
            super().__init__(parent)
            codigos.append(codigo)

        def exec(self):
            return 1

    monkeypatch.setattr("ui.views.seguridad.DialogoCodigo", CodigoDePrueba)
    monkeypatch.setattr(
        modulo_registro.VentanaRegistro, "abrir_aplicacion", lambda self: None
    )

    ventana = modulo_registro.VentanaRegistro(configuracion_inicial=True)
    for clave, valor in {
        "nombre": "Carlos", "apellido": "García López", "nif": "12345678Z",
        "direccion": "Calle Mayor 12", "email": "carlos@billease.es",
        "contrasena": CONTRASENA, "telefono": "612345678", "codigo_postal": "28001",
    }.items():
        ventana.campos[clave].setText(valor)
    ventana.registrar()

    assert caja.es_caja(ruta)
    assert len(codigos) == 1 and len(codigos[0].replace("-", "")) == 32
    assert repo_autonomo.obtener().nombre_completo == "Carlos García López"
    connection.cerrar()
    assert b"12345678Z" not in ruta.read_bytes()


# ─────────────────── el defecto del código postal ───────────────────


def test_un_cliente_sin_codigo_postal_se_puede_crear(en_claro):
    """
    El esquema exige cinco cifras o NULL, y la pantalla guardaba "".

    El alta fallaba y el programa decía «ya hay un cliente con ese documento»,
    que no tenía nada que ver con lo que pasaba.
    """
    identificador = repo_clientes.crear(Cliente(
        nombre="Sin código postal S.L.", nif="C87654323", es_persona_fisica=False
    ))
    assert identificador is not None
    assert repo_clientes.obtener(identificador).codigo_postal == ""


def test_un_cliente_sin_telefono_tampoco_estorba(en_claro):
    identificador = repo_clientes.crear(Cliente(
        nombre="Antonio Martínez Soto", nif="22334455Y", telefono="", codigo_postal=""
    ))
    assert identificador is not None
