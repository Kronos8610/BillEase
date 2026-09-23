"""
Catálogo de servicios.

Sigue existiendo porque las pantallas de crear y editar factura lo usan. La
fase 4 lo retira: los conceptos pasan a escribirse a mano.
"""

from core.models import Servicio
from data.connection import conexion


def listar():
    filas = conexion().execute("SELECT * FROM Servicio ORDER BY descripcion").fetchall()
    return [Servicio.desde_fila(f) for f in filas]


def crear(descripcion, precio, observaciones=""):
    conn = conexion()
    cur = conn.execute(
        "INSERT INTO Servicio (descripcion, precio, observaciones) VALUES (?, ?, ?)",
        (descripcion, float(precio), observaciones),
    )
    conn.commit()
    return cur.lastrowid


def eliminar(servicio_id):
    conn = conexion()
    cur = conn.execute(
        "DELETE FROM Servicio WHERE Cod_servicio = ?", (int(servicio_id),)
    )
    conn.commit()
    return cur.rowcount > 0


def esta_en_uso(servicio_id):
    return conexion().execute(
        "SELECT COUNT(*) FROM Detalle_linea WHERE cod_servicio = ?", (int(servicio_id),)
    ).fetchone()[0] > 0
