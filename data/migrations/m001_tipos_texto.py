"""
001 · Códigos postales y teléfonos dejan de ser números.

`codigo_postal` y `telefono` estaban declarados `REAL`, así que SQLite
convertía la cadena en número al guardarla: «08001» se quedaba en 8001.0 —
Barcelona perdía el cero inicial— y «+34612345678» en 34612345678.0, sin el
prefijo. Luego eso salía impreso en la factura como «CP: 28001.0»
(defecto 04 de la auditoría).

SQLite no sabe cambiar el tipo de una columna, así que se rehacen las dos
tablas y se recuperan los ceros a la izquierda al copiar.
"""

from data.migrations._esquema import reconstruir_tabla

VERSION = 1
DESCRIPCION = "Códigos postales y teléfonos a TEXT"


AUTONOMO = """
    CREATE TABLE {tabla} (
        DNI            TEXT NOT NULL,
        nombre         TEXT NOT NULL,
        apellido       TEXT NOT NULL,
        direccion      TEXT,
        codigo_postal  TEXT CHECK (codigo_postal IS NULL OR length(codigo_postal) = 5),
        telefono       TEXT,
        email          TEXT UNIQUE,
        contrasena     TEXT NOT NULL,
        PRIMARY KEY (DNI)
    )
"""

CLIENTE = """
    CREATE TABLE {tabla} (
        Cod_cliente           INTEGER PRIMARY KEY AUTOINCREMENT,
        TIPO_CLIENTE          INTEGER NOT NULL DEFAULT 1,
        nombre_o_razon_social TEXT NOT NULL,
        direccion             TEXT,
        telefono              TEXT,
        cod_postal            TEXT CHECK (cod_postal IS NULL OR length(cod_postal) = 5),
        CIFNIF                TEXT NOT NULL UNIQUE,
        observaciones         TEXT,
        email                 TEXT
    )
"""


def _cp(columna):
    """Devuelve el CP como texto de cinco cifras, recuperando el cero perdido."""
    return (
        f"CASE WHEN {columna} IS NULL OR trim(CAST({columna} AS TEXT)) = '' THEN NULL"
        f"     ELSE substr('00000' || CAST(CAST({columna} AS INTEGER) AS TEXT),"
        f"                 -5, 5) END"
    )


def _telefono(columna):
    """El teléfono como texto, sin el `.0` que arrastra el tipo REAL."""
    return (
        f"CASE WHEN {columna} IS NULL OR trim(CAST({columna} AS TEXT)) = '' THEN NULL"
        f"     WHEN CAST({columna} AS TEXT) LIKE '%.0' THEN CAST(CAST({columna} AS INTEGER) AS TEXT)"
        f"     ELSE CAST({columna} AS TEXT) END"
    )


def aplicar(conn):
    reconstruir_tabla(
        conn,
        "Autonomo",
        AUTONOMO,
        ["DNI", "nombre", "apellido", "direccion", "codigo_postal",
         "telefono", "email", "contrasena"],
        "SELECT DNI, nombre, apellido, direccion,"
        f" {_cp('codigo_postal')}, {_telefono('telefono')}, email, contrasena"
        " FROM Autonomo",
    )

    reconstruir_tabla(
        conn,
        "Cliente",
        CLIENTE,
        ["Cod_cliente", "TIPO_CLIENTE", "nombre_o_razon_social", "direccion",
         "telefono", "cod_postal", "CIFNIF", "observaciones", "email"],
        "SELECT Cod_cliente, COALESCE(TIPO_CLIENTE, 1), nombre_o_razon_social, direccion,"
        f" {_telefono('telefono')}, {_cp('cod_postal')}, CIFNIF, observaciones, email"
        " FROM Cliente",
    )
