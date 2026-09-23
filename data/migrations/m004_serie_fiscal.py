"""
004 · Numeración de factura como serie fiscal.

El número de factura era el `AUTOINCREMENT` de SQLite. Borrar una factura
dejaba un hueco permanente en la serie, y el reglamento de facturación exige
numeración correlativa; tampoco había prefijo ni ejercicio, así que la
factura 1 de 2025 y la 1 de 2026 no se distinguían (defecto 05).

A partir de aquí cada documento tiene serie, ejercicio y número, con un
índice único que impide repetir. Las siete facturas existentes se renumeran
como 2025-001 … 2025-007 respetando su orden actual.
"""

VERSION = 4
DESCRIPCION = "Serie fiscal: serie, ejercicio y número correlativo"


def numero_completo(serie, ejercicio, numero):
    """«2025-004» a partir de sus tres piezas."""
    prefijo = f"{serie}-" if serie else ""
    return f"{prefijo}{ejercicio}-{int(numero):03d}"


def aplicar(conn):
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Factura)")}
    if "numero" not in columnas:
        conn.execute("ALTER TABLE Factura ADD COLUMN serie TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE Factura ADD COLUMN ejercicio INTEGER")
        conn.execute("ALTER TABLE Factura ADD COLUMN numero INTEGER")

    # Se renumera por ejercicio siguiendo el orden de emisión que ya había.
    contadores = {}
    filas = conn.execute(
        "SELECT Num_factura, fecha FROM Factura ORDER BY fecha, Num_factura"
    ).fetchall()
    for num_factura, fecha in filas:
        ejercicio = int(str(fecha)[:4]) if str(fecha)[:4].isdigit() else 0
        contadores[ejercicio] = contadores.get(ejercicio, 0) + 1
        conn.execute(
            "UPDATE Factura SET ejercicio = ?, numero = ? WHERE Num_factura = ?",
            (ejercicio, contadores[ejercicio], num_factura),
        )

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_factura_serie"
        " ON Factura (serie, ejercicio, numero)"
    )
