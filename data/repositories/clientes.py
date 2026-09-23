"""Clientes."""

import sqlite3

from core.models import Cliente
from core.validators import normalizar_cp, normalizar_telefono
from data.connection import conexion


def listar():
    filas = conexion().execute(
        "SELECT * FROM Cliente ORDER BY nombre_o_razon_social"
    ).fetchall()
    return [Cliente.desde_fila(f) for f in filas]


def obtener(cliente_id):
    fila = conexion().execute(
        "SELECT * FROM Cliente WHERE Cod_cliente = ?", (int(cliente_id),)
    ).fetchone()
    return Cliente.desde_fila(fila)


def crear(cliente):
    """
    Da de alta un cliente y devuelve su identificador.

    Devuelve None si el documento fiscal ya está registrado: la base lo impide
    con un índice único, y es mejor que la pantalla lo diga a que se creen dos
    fichas del mismo cliente.
    """
    conn = conexion()
    try:
        cur = conn.execute(
            "INSERT INTO Cliente (TIPO_CLIENTE, nombre_o_razon_social, direccion,"
            " telefono, cod_postal, CIFNIF, observaciones, email)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(bool(cliente.es_persona_fisica)),
                cliente.nombre,
                cliente.direccion,
                normalizar_telefono(cliente.telefono),
                normalizar_cp(cliente.codigo_postal),
                cliente.nif.upper(),
                cliente.observaciones,
                cliente.email,
            ),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def eliminar(cliente_id):
    """
    Borra un cliente.

    Uno con facturas no se puede borrar: lo impide la clave ajena, y así debe
    ser, porque una factura emitida no puede quedarse sin destinatario.
    """
    conn = conexion()
    try:
        cur = conn.execute(
            "DELETE FROM Cliente WHERE Cod_cliente = ?", (int(cliente_id),)
        )
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def cuantas_facturas(cliente_id):
    return conexion().execute(
        "SELECT COUNT(*) FROM Factura WHERE Cod_cliente = ?", (int(cliente_id),)
    ).fetchone()[0]
