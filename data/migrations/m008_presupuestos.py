"""
008 · Presupuestos.

Un autónomo presupuesta antes de facturar, y hasta ahora el programa solo sabía
facturar. Presupuesto y factura son el mismo documento con otra cabecera, así
que comparten tabla y se distinguen por su `tipo`.

Cada uno lleva su serie: las facturas van 2025-001, 2025-002… y los
presupuestos P-2025-001, P-2025-002… El índice único de la migración 004 ya
separa las series, de modo que las dos numeraciones corren en paralelo sin
pisarse.

`origen_id` guarda de qué presupuesto salió una factura, para poder seguir el
rastro de una a otro.
"""

VERSION = 8
DESCRIPCION = "Presupuestos: tipo, estado, vencimiento y validez"

# Estados de un presupuesto. Una factura emitida está siempre «emitida».
BORRADOR = "borrador"
ENVIADO = "enviado"
ACEPTADO = "aceptado"
RECHAZADO = "rechazado"
EMITIDA = "emitida"


def aplicar(conn):
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Factura)")}

    if "tipo" not in columnas:
        conn.execute(
            "ALTER TABLE Factura ADD COLUMN tipo TEXT NOT NULL DEFAULT 'factura'"
        )
    if "estado" not in columnas:
        conn.execute(
            "ALTER TABLE Factura ADD COLUMN estado TEXT NOT NULL DEFAULT 'emitida'"
        )
    if "vencimiento" not in columnas:
        conn.execute("ALTER TABLE Factura ADD COLUMN vencimiento TEXT")
    if "validez" not in columnas:
        conn.execute("ALTER TABLE Factura ADD COLUMN validez TEXT")
    if "origen_id" not in columnas:
        # De qué presupuesto salió esta factura, si salió de alguno.
        conn.execute("ALTER TABLE Factura ADD COLUMN origen_id INTEGER")

    # Todo lo que ya había son facturas emitidas.
    conn.execute(
        "UPDATE Factura SET tipo = 'factura', estado = 'emitida'"
        " WHERE tipo IS NULL OR tipo = ''"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_factura_tipo ON Factura (tipo, fecha)")
