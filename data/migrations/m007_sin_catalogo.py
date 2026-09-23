"""
007 · Se retira el catálogo de servicios.

Los conceptos se escriben. Obligar a dar de alta un servicio antes de poder
facturarlo no encaja con cómo se trabaja: cada obra lleva su descripción —«un
armario de dos módulos con puerta corredera en blanco lacado de 2,00 × 2,40 m»—
y no se repite nunca igual.

La migración 005 ya copió en cada línea la descripción del servicio al que
apuntaba, así que aquí no se pierde nada: solo desaparecen la referencia y la
tabla del catálogo.
"""

from data.migrations._esquema import reconstruir_tabla

VERSION = 7
DESCRIPCION = "Se retira el catálogo de servicios"


DETALLE = """
    CREATE TABLE {tabla} (
        Num_Factura        INTEGER NOT NULL,
        Num_Linea          INTEGER NOT NULL,
        descripcion        TEXT NOT NULL DEFAULT '',
        NumServicios       REAL NOT NULL,
        unidad             TEXT NOT NULL DEFAULT 'ud',
        precioPorServicio  REAL NOT NULL,
        PRIMARY KEY (Num_Factura, Num_Linea),
        FOREIGN KEY (Num_Factura) REFERENCES Factura (Num_factura) ON DELETE CASCADE
    )
"""


def aplicar(conn):
    reconstruir_tabla(
        conn,
        "Detalle_linea",
        DETALLE,
        ["Num_Factura", "Num_Linea", "descripcion", "NumServicios",
         "unidad", "precioPorServicio"],
        "SELECT Num_Factura, Num_Linea, descripcion, NumServicios,"
        " unidad, precioPorServicio FROM Detalle_linea",
    )
    conn.execute("DROP TABLE IF EXISTS Servicio")
