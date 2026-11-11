"""
012 · La cuenta de Gmail desde la que el programa se manda los PDF.

Solo la dirección. La contraseña de aplicación NO va aquí: va en el llavero
del sistema (`core/llavero.py`), porque en una base sin cifrar la leería
cualquiera con un visor de SQLite.
"""

VERSION = 12
DESCRIPCION = "Cuenta de Gmail para mandarse los PDF"


def aplicar(conn):
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Autonomo)")}
    if "correo_envio" not in columnas:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN correo_envio TEXT")
