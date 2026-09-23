"""
003 · La factura guarda base, tipo de IVA y total.

La columna se llamaba `total` pero guardaba la **base imponible**: la suma de
las líneas sin IVA. El PDF le sumaba un 21 % por su cuenta, así que la misma
factura valía dos cifras distintas según dónde se mirara (defecto 01).

La fase 1 ya hizo que ambas pasaran por `core.taxes`. Esta migración lo
arregla en el origen: tres columnas explícitas, con el valor anterior
convertido en la base que siempre fue.
"""

from data.migrations._esquema import reconstruir_tabla

VERSION = 3
DESCRIPCION = "Factura con base, tipo de IVA e importe total"


FACTURA = """
    CREATE TABLE {tabla} (
        Num_factura    INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha          TEXT NOT NULL,
        base           REAL NOT NULL DEFAULT 0,
        tipo_iva       REAL NOT NULL DEFAULT 21,
        importe_total  REAL NOT NULL DEFAULT 0,
        Cod_cliente    INTEGER NOT NULL,
        observaciones  TEXT,
        FOREIGN KEY (Cod_cliente) REFERENCES Cliente (Cod_cliente)
    )
"""


def aplicar(conn):
    reconstruir_tabla(
        conn,
        "Factura",
        FACTURA,
        ["Num_factura", "fecha", "base", "tipo_iva", "importe_total",
         "Cod_cliente", "observaciones"],
        "SELECT Num_factura, fecha,"
        " ROUND(total, 2),"                                # el antiguo «total» era la base
        " 21,"                                             # único tipo que emitía la aplicación
        " ROUND(ROUND(total, 2) + ROUND(total * 0.21, 2), 2),"
        " CAST(Cod_cliente AS INTEGER),"                   # era REAL apuntando a un INTEGER
        " observaciones"
        " FROM Factura",
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_factura_cliente ON Factura (Cod_cliente)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_factura_fecha ON Factura (fecha)")
