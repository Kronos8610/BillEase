"""
Facturas y sus líneas.

Aquí se arregla el N+1 del listado: antes se pedía la lista de facturas y
después, **una consulta por fila**, el nombre del cliente. Con siete facturas
eran ocho viajes a la base; con quinientas, quinientos uno (defecto 09).

Ahora un `JOIN` trae factura y cliente de una vez.
"""

import sqlite3

from core.fechas import a_iso, ejercicio_de
from core.models import Documento, Linea
from core.numbering import siguiente
from core.taxes import IVA_GENERAL, calcular
from data.connection import conexion

# Factura más el nombre del cliente, que es lo único que necesita el listado.
SELECT_RESUMEN = """
    SELECT f.*, c.nombre_o_razon_social AS cliente_nombre
      FROM Factura f
      JOIN Cliente c ON c.Cod_cliente = f.Cod_cliente
"""


def listar():
    """Todas las facturas, de la más reciente a la más antigua, en una consulta."""
    filas = conexion().execute(
        SELECT_RESUMEN + " ORDER BY f.ejercicio DESC, f.numero DESC, f.Num_factura DESC"
    ).fetchall()
    return [Documento.desde_fila(f) for f in filas]


def obtener(num_factura, con_lineas=True):
    """Una factura concreta, con sus líneas si se piden."""
    fila = conexion().execute(
        SELECT_RESUMEN + " WHERE f.Num_factura = ?", (int(num_factura),)
    ).fetchone()
    if fila is None:
        return None
    return Documento.desde_fila(fila, lineas=lineas_de(num_factura) if con_lineas else ())


def lineas_de(num_factura):
    filas = conexion().execute(
        "SELECT * FROM Detalle_linea WHERE Num_Factura = ? ORDER BY Num_Linea",
        (int(num_factura),),
    ).fetchall()
    return [Linea.desde_fila(f) for f in filas]


def numeros_usados(serie=""):
    """Los números ya gastados de una serie, para calcular el siguiente."""
    filas = conexion().execute(
        "SELECT serie, ejercicio, numero FROM Factura WHERE serie = ?", (serie,)
    ).fetchall()
    return [(f["serie"] or "", f["ejercicio"] or 0, f["numero"] or 0) for f in filas]


def crear(fecha, cliente_id, lineas, observaciones="", tipo_iva=IVA_GENERAL, serie=""):
    """
    Emite una factura con sus líneas, todo o nada.

    `fecha` llega en formato español y se guarda en ISO. Los importes se
    calculan con `core.taxes`, la misma función que usan el listado y el PDF,
    así que no pueden discrepar. El número sale de la serie del ejercicio.
    """
    conn = conexion()
    iso = a_iso(fecha)
    ejercicio = ejercicio_de(iso)
    totales = calcular(lineas)
    numero = siguiente(numeros_usados(serie), ejercicio, serie)

    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            "INSERT INTO Factura (fecha, base, tipo_iva, importe_total, Cod_cliente,"
            " observaciones, serie, ejercicio, numero)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iso, float(totales.base), float(tipo_iva), float(totales.total),
             int(cliente_id), observaciones, serie, ejercicio, numero.numero),
        )
        num_factura = cur.lastrowid
        _escribir_lineas(conn, num_factura, lineas)
        conn.execute("COMMIT")
        return num_factura
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        return None


def actualizar(num_factura, fecha, cliente_id, lineas, observaciones="",
               tipo_iva=IVA_GENERAL):
    """Cambia una factura entera. Su número de serie no se toca nunca."""
    conn = conexion()
    totales = calcular(lineas)
    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            "UPDATE Factura SET fecha = ?, base = ?, tipo_iva = ?, importe_total = ?,"
            " Cod_cliente = ?, observaciones = ? WHERE Num_factura = ?",
            (a_iso(fecha), float(totales.base), float(tipo_iva), float(totales.total),
             int(cliente_id), observaciones, int(num_factura)),
        )
        if cur.rowcount == 0:
            conn.execute("ROLLBACK")
            return False
        conn.execute("DELETE FROM Detalle_linea WHERE Num_Factura = ?", (int(num_factura),))
        _escribir_lineas(conn, num_factura, lineas)
        conn.execute("COMMIT")
        return True
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        return False


def eliminar(num_factura):
    """
    Borra una factura y sus líneas.

    Ojo: borrar deja un hueco permanente en la serie, y la numeración tiene que
    ser correlativa. La fase 4 sustituye esto por anular, que conserva el
    número y el rastro.
    """
    conn = conexion()
    cur = conn.execute("DELETE FROM Factura WHERE Num_factura = ?", (int(num_factura),))
    conn.commit()
    return cur.rowcount > 0


def _escribir_lineas(conn, num_factura, lineas):
    for orden, linea in enumerate(lineas, 1):
        conn.execute(
            "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
            " NumServicios, unidad, precioPorServicio, cod_servicio)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(num_factura), orden, linea.descripcion, float(linea.cantidad),
             linea.unidad, float(linea.precio_ud),
             int(linea.cod_servicio) if linea.cod_servicio is not None else None),
        )
