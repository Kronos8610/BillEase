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
"""

import sqlite3
import threading

from config import asegurar_directorio, ruta_base_datos

_local = threading.local()


def _configurar(conn):
    """PRAGMA que hay que poner en CADA conexión nueva: no se heredan."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL permite leer mientras se escribe y sobrevive mejor a un cierre
    # brusco de la aplicación.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def abrir(ruta=None):
    """
    Abre una conexión nueva y configurada. El que la abre, la cierra.

    Se usa en migraciones y herramientas, donde interesa una conexión propia
    sobre un fichero concreto.
    """
    ruta = asegurar_directorio(ruta or ruta_base_datos())
    return _configurar(sqlite3.connect(str(ruta)))


def conexion():
    """
    La conexión de este hilo, creándola la primera vez.

    SQLite no deja compartir una conexión entre hilos, así que se guarda una
    por hilo. En la aplicación, que es de un solo hilo, es una y solo una.
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = abrir()
        _local.conn = conn
    return conn


def cerrar():
    """Cierra la conexión de este hilo, si la hay."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
