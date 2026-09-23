"""El emisor: sus datos y su acceso."""

import sqlite3

from core.models import Autonomo
from core.security import hashear, verificar
from core.validators import normalizar_cp, normalizar_telefono
from data.connection import conexion


def obtener():
    fila = conexion().execute("SELECT * FROM Autonomo LIMIT 1").fetchone()
    return Autonomo.desde_fila(fila)


def registrar(autonomo, contrasena):
    """Da de alta al autónomo. La contraseña se guarda cifrada, nunca en claro."""
    conn = conexion()
    try:
        conn.execute(
            "INSERT INTO Autonomo (DNI, nombre, apellido, direccion, codigo_postal,"
            " telefono, email, contrasena) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                autonomo.nif.upper(),
                autonomo.nombre,
                autonomo.apellido,
                autonomo.direccion,
                normalizar_cp(autonomo.codigo_postal),
                normalizar_telefono(autonomo.telefono),
                autonomo.email,
                hashear(contrasena),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def verificar_acceso(email, contrasena):
    """
    Comprueba las credenciales.

    Acepta las bases que todavía guardan la contraseña en claro y, en ese caso,
    la cifra al vuelo: nadie tiene que volver a registrarse.
    """
    conn = conexion()
    fila = conn.execute(
        "SELECT DNI, contrasena FROM Autonomo WHERE email = ?", (email,)
    ).fetchone()
    if not fila:
        return False

    correcta, recifrar = verificar(contrasena, fila["contrasena"])
    if correcta and recifrar:
        conn.execute(
            "UPDATE Autonomo SET contrasena = ? WHERE DNI = ?",
            (hashear(contrasena), fila["DNI"]),
        )
        conn.commit()
    return correcta
