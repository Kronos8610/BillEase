"""El emisor: sus datos y su acceso."""

import sqlite3

from core.models import FACTURA, PRESUPUESTO, Autonomo
from core.security import hashear, verificar
from core.validators import normalizar_cp, normalizar_iban, normalizar_telefono
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
                normalizar_cp(autonomo.codigo_postal) or None,
                normalizar_telefono(autonomo.telefono) or None,
                autonomo.email,
                hashear(contrasena),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def actualizar(autonomo):
    """
    Guarda los datos del emisor. La contraseña y el logotipo no se tocan aquí.

    El NIF también se puede corregir: una errata en el documento fiscal hay
    que poder arreglarla, y hasta ahora solo se podía reinstalando. Lo que se
    cambie sale impreso en los documentos que se generen a partir de ahora.
    """
    conn = conexion()
    fila = conn.execute("SELECT DNI FROM Autonomo LIMIT 1").fetchone()
    if fila is None:
        return False
    try:
        conn.execute(
            "UPDATE Autonomo SET DNI = ?, nombre = ?, apellido = ?, direccion = ?,"
            " codigo_postal = ?, telefono = ?, email = ?, entidad = ?, iban = ?"
            " WHERE DNI = ?",
            (
                autonomo.nif.upper(),
                autonomo.nombre,
                autonomo.apellido,
                autonomo.direccion,
                normalizar_cp(autonomo.codigo_postal) or None,
                normalizar_telefono(autonomo.telefono) or None,
                autonomo.email,
                autonomo.entidad.strip() or None,
                normalizar_iban(autonomo.iban) or None,
                fila["DNI"],
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


# Qué columna guarda la carpeta de cada tipo de documento. El nombre del
# tipo viene de `core.models`, y así no hay un `if` repartido por la interfaz.
COLUMNA_CARPETA = {
    FACTURA: "carpeta_facturas",
    PRESUPUESTO: "carpeta_presupuestos",
}


def carpeta_de(tipo):
    """
    La carpeta donde van los PDF de ese tipo, o cadena vacía si no hay.

    No comprueba que exista: eso lo mira quien va a escribir, que es quien
    puede hacer algo al respecto si el disco externo no está puesto.
    """
    emisor = obtener()
    if emisor is None or tipo not in COLUMNA_CARPETA:
        return ""
    return getattr(emisor, COLUMNA_CARPETA[tipo], "") or ""


def guardar_carpeta(tipo, ruta):
    """
    Apunta en qué carpeta se guardan los PDF de ese tipo. Vacía, se quita.

    Se guarda tal cual la eligió el usuario. Si deja de existir, el programa
    vuelve a preguntar dónde guardar en lugar de fallar.
    """
    columna = COLUMNA_CARPETA.get(tipo)
    if columna is None:
        raise ValueError(f"no hay carpeta para «{tipo}»; hay {sorted(COLUMNA_CARPETA)}")

    conn = conexion()
    fila = conn.execute("SELECT DNI FROM Autonomo LIMIT 1").fetchone()
    if fila is None:
        return False
    conn.execute(
        f"UPDATE Autonomo SET {columna} = ? WHERE DNI = ?",
        (str(ruta or "").strip() or None, fila["DNI"]),
    )
    conn.commit()
    return True


def guardar_logotipo(ruta):
    """
    Apunta qué imagen encabeza los documentos. Con cadena vacía, se quita.

    Se guarda la ruta tal cual la eligió el usuario. Si el fichero se mueve o
    se borra, el documento sale sin logotipo —como salía antes— en lugar de
    fallar al imprimirse.
    """
    conn = conexion()
    fila = conn.execute("SELECT DNI FROM Autonomo LIMIT 1").fetchone()
    if fila is None:
        return False
    conn.execute(
        "UPDATE Autonomo SET logotipo = ? WHERE DNI = ?",
        (str(ruta or "") or None, fila["DNI"]),
    )
    conn.commit()
    return True


def verificar_contrasena(contrasena):
    """
    Comprueba la contraseña del único autónomo que hay.

    BillEase es de un solo usuario: no hace falta pedir también el correo para
    entrar. Si la contraseña venía en claro de una versión antigua, se cifra
    al vuelo, como en `verificar_acceso`.
    """
    conn = conexion()
    fila = conn.execute("SELECT DNI, contrasena FROM Autonomo LIMIT 1").fetchone()
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


def cambiar_contrasena(nueva):
    """
    Guarda la contraseña nueva, cifrada.

    Quien llama se encarga de comprobar antes la anterior y, si la base está
    cifrada, de cambiarla también en la caja: son dos cosas distintas que
    tienen que moverse juntas.
    """
    conn = conexion()
    fila = conn.execute("SELECT DNI FROM Autonomo LIMIT 1").fetchone()
    if fila is None:
        return False
    conn.execute(
        "UPDATE Autonomo SET contrasena = ? WHERE DNI = ?", (hashear(nueva), fila["DNI"])
    )
    conn.commit()
    return True


def hay_autonomo():
    """¿Hay alguien dado de alta? Si no, no se le puede pedir que se acredite."""
    return conexion().execute("SELECT COUNT(*) FROM Autonomo").fetchone()[0] > 0


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
