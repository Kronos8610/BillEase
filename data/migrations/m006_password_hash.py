"""
006 · La contraseña deja de guardarse en claro.

`BillEase.db` guardaba «Pass1234» tal cual, legible con cualquier visor de
SQLite, y `login()` comparaba cadenas (defecto 03).

Esta migración cifra con Argon2 lo que hubiera guardado. Es irreversible por
definición: del hash no se vuelve a la contraseña, que es justo el objetivo.
La contraseña sigue siendo la misma para el usuario.
"""

from core.security import es_hash, hashear

VERSION = 6
DESCRIPCION = "Contraseña cifrada con Argon2"


def aplicar(conn):
    filas = conn.execute("SELECT DNI, contrasena FROM Autonomo").fetchall()
    for dni, contrasena in filas:
        if contrasena and not es_hash(contrasena):
            conn.execute(
                "UPDATE Autonomo SET contrasena = ? WHERE DNI = ?",
                (hashear(contrasena), dni),
            )
