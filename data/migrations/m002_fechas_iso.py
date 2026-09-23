"""
002 · Las fechas pasan a ISO-8601.

La columna estaba declarada `DATE`, pero SQLite no tiene tipo fecha: guardaba
el texto tal cual lo escribía el usuario, «15/01/2025». Ordenar por fecha
ordenaba alfabéticamente —«03/02» antes que «15/01»— y sacar el resumen de un
trimestre era imposible (defecto 08).

A partir de aquí se guarda «2025-01-15», que ordena solo y se puede filtrar
con un BETWEEN. La pantalla sigue enseñando el formato español.
"""

from core.fechas import a_iso

VERSION = 2
DESCRIPCION = "Fechas en formato ISO-8601"


def aplicar(conn):
    filas = conn.execute("SELECT Num_factura, fecha FROM Factura").fetchall()
    for num, fecha in filas:
        nueva = a_iso(fecha)
        if nueva != fecha:
            conn.execute(
                "UPDATE Factura SET fecha = ? WHERE Num_factura = ?", (nueva, num)
            )
