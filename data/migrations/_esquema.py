"""
Utilidad compartida por las migraciones que cambian el esquema.

Vive aparte del paquete para que las migraciones puedan importarla sin
provocar una importación circular: `__init__` las importa a ellas.
"""


def reconstruir_tabla(conn, nombre, definicion, columnas_destino, seleccion):
    """
    Cambia el esquema de una tabla, que en SQLite obliga a rehacerla entera.

    SQLite no sabe cambiar el tipo de una columna: hay que crear la tabla
    nueva, copiar los datos, borrar la vieja y renombrar. Es el procedimiento
    que documenta el propio SQLite; quien llama se encarga de apagar las
    claves ajenas y de comprobarlas antes de confirmar.

    `seleccion` es el SELECT que rellena la tabla nueva desde la vieja.
    """
    temporal = f"{nombre}__nueva"
    conn.execute(f"DROP TABLE IF EXISTS {temporal}")
    conn.execute(definicion.format(tabla=temporal))
    conn.execute(f"INSERT INTO {temporal} ({', '.join(columnas_destino)}) {seleccion}")
    conn.execute(f"DROP TABLE {nombre}")
    conn.execute(f"ALTER TABLE {temporal} RENAME TO {nombre}")
