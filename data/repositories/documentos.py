"""
Facturas y presupuestos.

Los dos comparten tabla y se distinguen por su `tipo`: son el mismo documento
con otra cabecera, otra serie y distinto ciclo de vida.

Aquí vive también el arreglo del N+1 del listado: antes se pedía la lista y
después, una consulta por fila, el nombre del cliente. Con siete documentos
eran ocho viajes a la base; con quinientos, quinientos uno (defecto 09). Ahora
un `JOIN` trae todo de una vez.
"""

import sqlite3

from core.fechas import a_iso, ejercicio_de
from core.models import (
    EMITIDA,
    FACTURA,
    PRESUPUESTO,
    SERIE_PRESUPUESTO,
    Documento,
    Linea,
)
from core.numbering import siguiente
from core.quotes import a_factura, puede_pasar_a
from core.taxes import IVA_GENERAL, calcular
from data.connection import conexion

SELECT_RESUMEN = """
    SELECT f.*, c.nombre_o_razon_social AS cliente_nombre
      FROM Factura f
      JOIN Cliente c ON c.Cod_cliente = f.Cod_cliente
"""

ORDEN = " ORDER BY f.ejercicio DESC, f.numero DESC, f.Num_factura DESC"


def serie_de(tipo):
    """Cada tipo lleva su serie, para que las numeraciones no se mezclen."""
    return SERIE_PRESUPUESTO if tipo == PRESUPUESTO else ""


def listar(tipo=FACTURA):
    """Todos los documentos de un tipo, del más reciente al más antiguo."""
    filas = conexion().execute(
        SELECT_RESUMEN + " WHERE f.tipo = ?" + ORDEN, (tipo,)
    ).fetchall()
    return [Documento.desde_fila(f) for f in filas]


def obtener(documento_id, con_lineas=True):
    fila = conexion().execute(
        SELECT_RESUMEN + " WHERE f.Num_factura = ?", (int(documento_id),)
    ).fetchone()
    if fila is None:
        return None
    return Documento.desde_fila(
        fila, lineas=lineas_de(documento_id) if con_lineas else ()
    )


def lineas_de(documento_id):
    filas = conexion().execute(
        "SELECT * FROM Detalle_linea WHERE Num_Factura = ? ORDER BY Num_Linea",
        (int(documento_id),),
    ).fetchall()
    return [Linea.desde_fila(f) for f in filas]


def numeros_usados(serie=""):
    filas = conexion().execute(
        "SELECT serie, ejercicio, numero FROM Factura WHERE serie = ?", (serie,)
    ).fetchall()
    return [(f["serie"] or "", f["ejercicio"] or 0, f["numero"] or 0) for f in filas]


def descripciones_usadas(limite=400):
    """
    Los conceptos que ya se han escrito alguna vez.

    Alimentan la sugerencia del editor: al teclear «arma…» aparece el armario
    que se facturó el mes pasado. Sugiere, no obliga.
    """
    filas = conexion().execute(
        "SELECT descripcion, COUNT(*) AS veces FROM Detalle_linea"
        " WHERE descripcion != ''"
        " GROUP BY descripcion ORDER BY veces DESC, descripcion LIMIT ?",
        (int(limite),),
    ).fetchall()
    return [f["descripcion"] for f in filas]


def crear(fecha, cliente_id, lineas, observaciones="", tipo=FACTURA,
          estado=None, vencimiento="", validez="", origen_id=None,
          tipo_iva=IVA_GENERAL):
    """
    Emite un documento con sus líneas, todo o nada.

    `fecha` llega en formato español y se guarda en ISO. Los importes se
    calculan con `core.taxes`, la misma función que usan el listado y el PDF.
    El número sale de la serie que le toque a su tipo.
    """
    conn = conexion()
    iso = a_iso(fecha)
    ejercicio = ejercicio_de(iso)
    serie = serie_de(tipo)
    totales = calcular(lineas)
    numero = siguiente(numeros_usados(serie), ejercicio, serie)
    if estado is None:
        estado = EMITIDA if tipo == FACTURA else "borrador"

    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            "INSERT INTO Factura (fecha, base, tipo_iva, importe_total, Cod_cliente,"
            " observaciones, serie, ejercicio, numero, tipo, estado, vencimiento,"
            " validez, origen_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iso, float(totales.base), float(tipo_iva), float(totales.total),
             int(cliente_id), observaciones, serie, ejercicio, numero.numero,
             tipo, estado, a_iso(vencimiento) or None, a_iso(validez) or None,
             origen_id),
        )
        documento_id = cur.lastrowid
        _escribir_lineas(conn, documento_id, lineas)
        conn.execute("COMMIT")
        return documento_id
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        return None


def actualizar(documento_id, fecha, cliente_id, lineas, observaciones="",
               vencimiento="", validez="", tipo_iva=IVA_GENERAL):
    """Cambia un documento entero. Su número de serie no se toca nunca."""
    conn = conexion()
    totales = calcular(lineas)
    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            "UPDATE Factura SET fecha = ?, base = ?, tipo_iva = ?, importe_total = ?,"
            " Cod_cliente = ?, observaciones = ?, vencimiento = ?, validez = ?"
            " WHERE Num_factura = ?",
            (a_iso(fecha), float(totales.base), float(tipo_iva), float(totales.total),
             int(cliente_id), observaciones, a_iso(vencimiento) or None,
             a_iso(validez) or None, int(documento_id)),
        )
        if cur.rowcount == 0:
            conn.execute("ROLLBACK")
            return False
        conn.execute(
            "DELETE FROM Detalle_linea WHERE Num_Factura = ?", (int(documento_id),)
        )
        _escribir_lineas(conn, documento_id, lineas)
        conn.execute("COMMIT")
        return True
    except sqlite3.Error:
        conn.execute("ROLLBACK")
        return False


def cambiar_estado(documento_id, estado):
    """Mueve un presupuesto por su ciclo de vida, si la transición es legítima."""
    documento = obtener(documento_id, con_lineas=False)
    if documento is None or not puede_pasar_a(documento, estado):
        return False
    conn = conexion()
    conn.execute(
        "UPDATE Factura SET estado = ? WHERE Num_factura = ?",
        (estado, int(documento_id)),
    )
    conn.commit()
    return True


def facturar_presupuesto(presupuesto_id, fecha=None):
    """
    Convierte un presupuesto aceptado en factura.

    Devuelve el identificador de la factura nueva, o None si el presupuesto no
    se puede facturar: solo se factura uno aceptado, y solo una vez. Facturar
    dos veces el mismo presupuesto es cobrar dos veces el mismo trabajo.
    """
    presupuesto = obtener(presupuesto_id)
    if presupuesto is None:
        return None

    ya_facturado = conexion().execute(
        "SELECT COUNT(*) FROM Factura WHERE origen_id = ?", (int(presupuesto_id),)
    ).fetchone()[0]
    if ya_facturado:
        return None

    try:
        factura = a_factura(presupuesto, fecha)
    except ValueError:
        return None

    return crear(
        factura.fecha,
        factura.cliente_id,
        factura.lineas,
        observaciones=factura.observaciones,
        tipo=FACTURA,
        vencimiento=factura.vencimiento,
        origen_id=presupuesto.id,
        tipo_iva=factura.tipo_iva,
    )


def factura_de(presupuesto_id):
    """La factura que salió de este presupuesto, si ya se facturó."""
    fila = conexion().execute(
        SELECT_RESUMEN + " WHERE f.origen_id = ?", (int(presupuesto_id),)
    ).fetchone()
    return Documento.desde_fila(fila) if fila else None


def eliminar(documento_id):
    """
    Borra un documento y sus líneas.

    Un presupuesto se puede borrar sin más: no tiene valor contable. Una
    factura emitida no debería borrarse —deja un hueco en la serie—, pero la
    pantalla todavía lo permite y avisa.
    """
    conn = conexion()
    cur = conn.execute(
        "DELETE FROM Factura WHERE Num_factura = ?", (int(documento_id),)
    )
    conn.commit()
    return cur.rowcount > 0


def _escribir_lineas(conn, documento_id, lineas):
    for orden, linea in enumerate(lineas, 1):
        conn.execute(
            "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
            " NumServicios, unidad, precioPorServicio) VALUES (?, ?, ?, ?, ?, ?)",
            (int(documento_id), orden, linea.descripcion, float(linea.cantidad),
             linea.unidad, float(linea.precio_ud)),
        )
