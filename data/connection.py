"""
La conexión con SQLite.

Antes cada una de las veintidós funciones de `database/db.py` abría y cerraba
su propia conexión: pintar el listado con siete facturas abría ocho, y con
quinientas abriría quinientas una (defecto 09).

Y, sobre todo, ninguna activaba `PRAGMA foreign_keys`. SQLite arranca con las
claves ajenas **desactivadas**, así que el `ON DELETE CASCADE` declarado en el
esquema nunca llegaba a ejecutarse y se podían insertar líneas que apuntaban a
facturas inexistentes (defecto en el modelo de datos).

Aquí hay una sola conexión por proceso, con los PRAGMA correctos y
`row_factory` para poder leer las columnas por nombre en lugar de por índice.

Desde que la base se puede cifrar (`data/caja.py`), esa conexión puede ser de
dos clases: la de siempre, contra un fichero SQLite, o una **en memoria** que
se guarda cifrada en cada `commit()`. El resto del programa no distingue: pide
`conexion()` y escribe SQL igual en los dos casos.
"""

import sqlite3
import threading
from pathlib import Path

from config import asegurar_directorio, ruta_base_datos
from data import caja

_local = threading.local()


def _configurar(conn):
    """PRAGMA que hay que poner en CADA conexión nueva: no se heredan."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not isinstance(conn, caja.ConexionDeCaja):
        # WAL permite leer mientras se escribe y sobrevive mejor a un cierre
        # brusco de la aplicación. En memoria no tiene sentido: ahí el que
        # protege del cierre brusco es el guardado en cada `commit()`.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def uri_solo_lectura(ruta):
    """
    La URI con la que SQLite abre un fichero sin poder escribirlo.

    Hay que montarla con `as_uri()` y no pegando `file:` delante de la ruta:
    en Windows una ruta lleva barras invertidas, letra de unidad y, muy a
    menudo, espacios o acentos (C:/Users/José Luis/OneDrive - Empresa/…),
    y nada de eso es una URI válida tal cual (en el original van barras
    invertidas). `as_uri()` lo traduce a
    `file:///C:/Users/Jos%C3%A9%20Luis/…`, que es lo que SQLite espera.
    """
    return f"{Path(ruta).resolve().as_uri()}?mode=ro"


def abrir(ruta=None):
    """
    Abre una conexión nueva y configurada. El que la abre, la cierra.

    Se usa en migraciones y herramientas, donde interesa una conexión propia
    sobre un fichero concreto.
    """
    ruta = asegurar_directorio(ruta or ruta_base_datos())
    return _configurar(sqlite3.connect(str(ruta)))


def abrir_caja(ruta=None, contrasena=None, codigo=None):
    """
    Abre la base cifrada y la deja como conexión de este hilo.

    Es lo que hace la pantalla de acceso cuando el usuario acierta la
    contraseña. Lanza `ClaveIncorrecta` si no acierta, y `CajaCorrupta` si el
    fichero está dañado.
    """
    ruta = asegurar_directorio(ruta or ruta_base_datos())
    cerrar()
    conn = caja.abrir(ruta, contrasena=contrasena, codigo=codigo)
    _configurar(conn)
    _local.conn = conn
    return conn


def adoptar(conn):
    """
    Toma una conexión ya abierta como la de este hilo.

    La usa el alta inicial, que crea la caja y sigue trabajando con ella sin
    volver a pedir la contraseña que el usuario acaba de escribir.
    """
    cerrar()
    _configurar(conn)
    _local.conn = conn
    return conn


def esta_cifrada(ruta=None):
    """¿La base de esta ruta es una caja cifrada?"""
    ruta = ruta or ruta_base_datos()
    return caja.es_caja(ruta)


def conexion():
    """
    La conexión de este hilo, creándola la primera vez.

    SQLite no deja compartir una conexión entre hilos, así que se guarda una
    por hilo. En la aplicación, que es de un solo hilo, es una y solo una.

    Si la base está cifrada y nadie la ha abierto todavía, esto no puede
    adivinar la contraseña: avisa en lugar de crear una base vacía encima.
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        if esta_cifrada():
            raise caja.ClaveIncorrecta(
                "la base está cifrada: hay que abrirla con `abrir_caja(contrasena=…)`"
            )
        conn = abrir()
        _local.conn = conn
    return conn


def guardar():
    """
    Fuerza el guardado de la caja, si la conexión es cifrada.

    En condiciones normales no hace falta llamarla: cada `commit()` guarda. Se
    usa al cerrar el programa, por si quedara algo suelto.
    """
    conn = getattr(_local, "conn", None)
    if isinstance(conn, caja.ConexionDeCaja):
        return conn.persistir()
    return False


def cambiar_contrasena(nueva):
    """
    Cambia la contraseña de la caja abierta, sin cerrarla.

    Devuelve False si la base no está cifrada, que no es un error: solo
    significa que no hay caja que recifrar.
    """
    return caja.recifrar(getattr(_local, "conn", None), nueva)


def cerrar():
    """Cierra la conexión de este hilo, guardando antes si está cifrada."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        if isinstance(conn, caja.ConexionDeCaja):
            conn.persistir()
        conn.close()
        _local.conn = None
