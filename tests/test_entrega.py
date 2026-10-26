"""
Pruebas de la entrega (fase 6): dónde viven los datos y qué se empaqueta.

La puerta 6 pide dos cosas que no son de cálculo sino de instalación: que la
base viva en la carpeta de datos del usuario y no junto al ejecutable, y que
al cerrar quede una copia de seguridad que de verdad se pueda restaurar.

Lo que **no** se puede comprobar aquí es el instalador en una máquina limpia
con Windows: eso se ejecuta a mano, siguiendo el README.
"""

import ast
import os
import sys
from pathlib import Path

import pytest

import config
from data import backup
from data.connection import cerrar
from data.schema import crear_esquema_y_migrar

RAIZ = Path(__file__).resolve().parent.parent


# ─────────────────────── dónde viven los datos ───────────────────────


def test_en_windows_la_base_va_a_localappdata(monkeypatch, tmp_path):
    """
    No junto al ejecutable: «Archivos de programa» es de solo lectura.

    Antes la ruta era la cadena «BillEase.db» relativa al directorio de
    trabajo, así que abrir el programa desde otra carpeta creaba una base
    nueva y vacía y los datos «desaparecían».
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("BILLEASE_DB", raising=False)

    ruta = config.ruta_base_datos()
    assert ruta.parent == tmp_path / "AppData" / "Local" / "BillEase"
    assert ruta.name == "billease.db"


def test_fuera_de_windows_la_base_va_a_la_carpeta_de_datos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "datos"))
    monkeypatch.delenv("BILLEASE_DB", raising=False)

    assert config.ruta_base_datos() == tmp_path / "datos" / "BillEase" / "billease.db"


def test_la_variable_de_entorno_manda_sobre_todo(monkeypatch, tmp_path):
    """Es lo que usan las pruebas y las herramientas para no tocar la base real."""
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "otra.db"))
    assert config.ruta_base_datos() == tmp_path / "otra.db"


def test_la_base_nunca_se_crea_junto_al_programa(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("BILLEASE_DB", raising=False)

    ruta = config.ruta_base_datos()
    assert RAIZ not in ruta.parents
    assert Path.cwd() not in ruta.parents


# ─────────────────────── la copia al cerrar ───────────────────────


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "billease.db"))
    cerrar()
    crear_esquema_y_migrar()
    yield tmp_path / "billease.db"
    cerrar()


def test_al_cerrar_la_ventana_queda_una_copia(base):
    """La copia automática de la puerta 6, comprobada cerrando la ventana."""
    pytest.importorskip("PyQt6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    import theme
    from ui.shell import VentanaPrincipal

    app = QApplication.instance() or QApplication([])
    theme.aplicar_tema(app, "claro")

    assert backup.copias(base) == []

    ventana = VentanaPrincipal()
    ventana.close()

    copias = backup.copias(base)
    assert len(copias) == 1
    assert copias[0].exists()


def test_una_copia_que_falla_no_impide_cerrar(base, monkeypatch):
    """Quedarse sin poder cerrar el programa sería peor que perder la copia."""
    pytest.importorskip("PyQt6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    import theme
    from ui.shell import VentanaPrincipal

    app = QApplication.instance() or QApplication([])
    theme.aplicar_tema(app, "claro")

    def revienta(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(backup, "copiar", revienta)

    ventana = VentanaPrincipal()
    ventana.close()                      # no debe lanzar
    assert not ventana.isVisible()


def test_las_rutas_con_espacios_y_acentos_funcionan(tmp_path):
    """
    En Windows la base vive en `C:/Users/<nombre>/…`, y los nombres llevan
    espacios y acentos: «José Luis», «OneDrive - Empresa».

    Pegarle `file:` delante a una ruta así no da una URI válida. Si esto se
    rompe, el programa falla solo en los ordenadores de quien tiene un nombre
    con tilde, que es la mitad de España.
    """
    from data import backup, caja
    from data.connection import uri_solo_lectura

    carpeta = tmp_path / "OneDrive - Carpintería José Luis" / "mis facturas"
    carpeta.mkdir(parents=True)
    ruta = carpeta / "billease.db"

    import sqlite3

    suelta = sqlite3.connect(ruta)
    suelta.execute("CREATE TABLE Cliente (nombre TEXT)")
    suelta.execute("INSERT INTO Cliente VALUES ('María Fernández')")
    suelta.commit()
    suelta.close()

    uri = uri_solo_lectura(ruta)
    assert uri.startswith("file:///") and "%20" in uri      # espacios escapados
    assert sqlite3.connect(uri, uri=True).execute(
        "SELECT nombre FROM Cliente"
    ).fetchone()[0] == "María Fernández"

    # Y las operaciones que la usan: copiar y cifrar.
    assert backup.copiar(ruta).exists()
    caja.cifrar(ruta, "Pass1234")
    conn = caja.abrir(ruta, contrasena="Pass1234")
    assert conn.execute("SELECT nombre FROM Cliente").fetchone()[0] == "María Fernández"
    conn.close()


# ─────────────────────── el empaquetado ───────────────────────


def test_la_receta_de_empaquetado_incluye_la_hoja_de_estilos():
    """
    Sin `app.qss` el programa empaquetado arranca sin estilos: todo gris.

    Se lee la receta como lo que es —un fichero de Python— en lugar de
    buscar texto a ojo.
    """
    receta = (RAIZ / "billease.spec").read_text(encoding="utf-8")
    arbol = ast.parse(receta)

    datos = None
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Assign)
                and getattr(nodo.targets[0], "id", "") == "datos"):
            datos = ast.literal_eval(nodo.value)
    assert datos is not None, "la receta no declara ficheros de datos"
    assert ("theme/app.qss", "theme") in datos


def test_el_tema_se_encuentra_tambien_dentro_del_ejecutable(monkeypatch, tmp_path):
    """
    PyInstaller descomprime los datos en `sys._MEIPASS`.

    Si `theme` no mirara ahí, la aplicación empaquetada arrancaría sin
    estilos aunque el fichero viajara dentro.
    """
    import theme

    falso = tmp_path / "theme"
    falso.mkdir()
    (falso / "app.qss").write_text("QWidget { color: $texto; }", encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert theme._hoja() == falso / "app.qss"

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert theme._hoja().name == "app.qss"
    assert theme._hoja().exists()


def test_la_receta_lleva_lo_que_hace_falta_para_descifrar():
    """
    Si `cryptography` no viaja dentro, el ejecutable no abre los datos de nadie.

    Es el fallo que no se ve hasta que alguien instala el programa en una
    máquina sin Python y se encuentra con que su base no se abre.
    """
    receta = (RAIZ / "billease.spec").read_text(encoding="utf-8")
    arbol = ast.parse(receta)

    ocultos = None
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Assign)
                and getattr(nodo.targets[0], "id", "") == "ocultos"):
            ocultos = [
                elemento.value for elemento in nodo.value.elts
                if isinstance(elemento, ast.Constant)
            ]
    assert ocultos is not None, "la receta no declara importaciones ocultas"
    assert "cryptography" in ocultos
    assert "argon2" in ocultos


def test_el_instalador_no_borra_los_datos_al_desinstalar():
    """
    Borrar las facturas de alguien porque desinstala el programa sería
    imperdonable. El `.iss` no puede tener una sección que las borre.
    """
    receta = (RAIZ / "installer" / "billease.iss").read_text(encoding="utf-8")
    sin_comentarios = "\n".join(
        linea for linea in receta.splitlines() if not linea.strip().startswith(";")
    )
    # Ninguna sección de borrado al desinstalar, y ninguna directiva que
    # apunte a la carpeta de datos: `{localappdata}` es la constante que usa
    # Inno Setup. El `%LOCALAPPDATA%` del mensaje final es solo texto que se
    # le enseña al usuario para decirle dónde están sus cosas.
    assert "[UninstallDelete]" not in sin_comentarios
    assert "{localappdata}" not in sin_comentarios.lower()
    assert "[Files]" in sin_comentarios
    assert "%LOCALAPPDATA%" in receta, "el instalador debería decir dónde quedan los datos"


def test_el_instalador_apunta_a_lo_que_genera_pyinstaller():
    receta = (RAIZ / "installer" / "billease.iss").read_text(encoding="utf-8")
    assert "..\\dist\\BillEase\\*" in receta
    assert "BillEase.exe" in receta
