"""
Acceso a la base de datos.

Reescrito en la fase 2. Lo que había antes abría y cerraba una conexión en
cada una de sus veintidós funciones, nunca activaba las claves ajenas y se
tragaba cualquier error con un `print`, de modo que la interfaz nunca sabía
*por qué* algo no se había guardado.

Ahora todo pasa por la conexión única de `data/connection.py`, con las claves
ajenas aplicadas, y las consultas devuelven filas que se leen **por nombre de
columna** en lugar de por índice: añadir una columna deja de romper pantallas
a distancia.

Las fechas entran y salen en formato español y se guardan en ISO; los
importes se calculan siempre con `core.taxes`.

La fase 3 sustituye este módulo por repositorios que devuelvan objetos del
dominio. Hasta entonces sigue siendo el único sitio del programa con SQL.
"""

import sqlite3

from core.fechas import a_espanol, a_iso, ejercicio_de
from core.security import hashear, verificar
from core.taxes import IVA_GENERAL, Linea, calcular
from data.connection import conexion


# ──────────────────────────── esquema ────────────────────────────

ESQUEMA_INICIAL = (
    """
    CREATE TABLE IF NOT EXISTS Autonomo (
        DNI            TEXT NOT NULL UNIQUE,
        nombre         TEXT NOT NULL,
        apellido       TEXT NOT NULL,
        direccion      TEXT,
        codigo_postal  REAL,
        telefono       REAL,
        email          TEXT UNIQUE,
        contrasena     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Cliente (
        Cod_cliente           INTEGER PRIMARY KEY AUTOINCREMENT,
        TIPO_CLIENTE          BOOLEAN,
        nombre_o_razon_social TEXT NOT NULL,
        direccion             TEXT,
        telefono              REAL,
        cod_postal            TEXT,
        CIFNIF                TEXT NOT NULL UNIQUE,
        observaciones         TEXT,
        email                 TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Factura (
        Num_factura    INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha          DATE NOT NULL,
        total          REAL NOT NULL,
        Cod_cliente    REAL NOT NULL,
        observaciones  TEXT,
        FOREIGN KEY (Cod_cliente) REFERENCES Cliente (Cod_cliente) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Servicio (
        Cod_servicio   INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion    TEXT NOT NULL,
        precio         REAL NOT NULL,
        observaciones  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Detalle_linea (
        Num_Factura         REAL,
        Num_Linea           REAL,
        NumServicios        REAL NOT NULL,
        precioPorServicio   REAL NOT NULL,
        cod_servicio        REAL NOT NULL,
        PRIMARY KEY (Num_Factura, Num_Linea),
        FOREIGN KEY (Num_Factura) REFERENCES Factura (Num_factura),
        FOREIGN KEY (cod_servicio) REFERENCES Servicio (Cod_servicio)
    )
    """,
)


def crear_base_de_datos(conn=None):
    """
    Crea el esquema de partida y lo pone al día con las migraciones.

    El esquema que se crea aquí es el original, con sus defectos incluidos, y
    las migraciones de `data/migrations/` lo llevan hasta la versión actual.
    Así hay un único camino —el mismo que recorre la base de un usuario que
    viene de una versión antigua— en lugar de dos definiciones que se separan
    con el tiempo.
    """
    from data.migrations import migrar

    conn = conn or conexion()
    for sentencia in ESQUEMA_INICIAL:
        conn.execute(sentencia)
    conn.commit()
    migrar(conn, registrar=lambda *_: None)
    return conn


# ──────────────────────────── autónomo ────────────────────────────

def register_autonomo(dni, nombre, apellido, direccion, codigo_postal, telefono,
                      email, contrasena):
    """Da de alta al autónomo. La contraseña se guarda cifrada, nunca en claro."""
    conn = conexion()
    try:
        conn.execute(
            "INSERT INTO Autonomo (DNI, nombre, apellido, direccion, codigo_postal,"
            " telefono, email, contrasena) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (dni, nombre, apellido, direccion, str(codigo_postal or ""),
             str(telefono or ""), email, hashear(contrasena)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def login(email, contrasena):
    """
    Comprueba las credenciales del autónomo.

    Acepta también las bases que aún guardan la contraseña en claro y, en ese
    caso, la cifra al vuelo: nadie tiene que volver a registrarse.
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


def obtener_datos_autonomo():
    """Datos del emisor: (DNI, nombre, apellido, dirección, CP, teléfono, email)."""
    fila = conexion().execute(
        "SELECT DNI, nombre, apellido, direccion, codigo_postal, telefono, email"
        " FROM Autonomo LIMIT 1"
    ).fetchone()
    return tuple(fila) if fila else None


# ──────────────────────────── clientes ────────────────────────────

def agregar_cliente(cifnif, nombre_o_razon_social, direccion, cod_postal, telefono,
                    observaciones, tipo_cliente=True, email=""):
    """Añade un cliente. Devuelve su identificador, o None si el NIF ya existe."""
    conn = conexion()
    try:
        cur = conn.execute(
            "INSERT INTO Cliente (TIPO_CLIENTE, nombre_o_razon_social, direccion,"
            " telefono, cod_postal, CIFNIF, observaciones, email)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (int(bool(tipo_cliente)), nombre_o_razon_social, direccion,
             str(telefono or ""), str(cod_postal or ""), cifnif, observaciones, email),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def obtener_clientes():
    return conexion().execute(
        "SELECT * FROM Cliente ORDER BY nombre_o_razon_social"
    ).fetchall()


def obtener_cliente_por_id(cod_cliente):
    return conexion().execute(
        "SELECT * FROM Cliente WHERE Cod_cliente = ?", (int(cod_cliente),)
    ).fetchone()


def eliminar_cliente(cod_cliente):
    """
    Borra un cliente.

    No se puede borrar uno que tenga facturas: la clave ajena lo impide, y así
    debe ser, porque una factura emitida no puede quedarse sin destinatario.
    """
    conn = conexion()
    try:
        cur = conn.execute("DELETE FROM Cliente WHERE Cod_cliente = ?", (int(cod_cliente),))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def obtener_facturas_cliente(cod_cliente):
    return conexion().execute(
        "SELECT * FROM Factura WHERE Cod_cliente = ? ORDER BY fecha DESC",
        (int(cod_cliente),),
    ).fetchall()


# ──────────────────────────── servicios ────────────────────────────
# El catálogo sigue existiendo porque las pantallas de crear y editar factura
# todavía lo usan. La fase 4 lo retira: los conceptos pasan a escribirse.

def insertar_servicio(descripcion, precio, observaciones=""):
    conn = conexion()
    cur = conn.execute(
        "INSERT INTO Servicio (descripcion, precio, observaciones) VALUES (?, ?, ?)",
        (descripcion, precio, observaciones),
    )
    conn.commit()
    return cur.lastrowid


def obtener_todos_servicios():
    return conexion().execute("SELECT * FROM Servicio ORDER BY descripcion").fetchall()


def eliminar_servicio(cod_servicio):
    conn = conexion()
    cur = conn.execute("DELETE FROM Servicio WHERE Cod_servicio = ?", (int(cod_servicio),))
    conn.commit()
    return cur.rowcount > 0


def verificar_servicio_en_uso(cod_servicio):
    fila = conexion().execute(
        "SELECT COUNT(*) FROM Detalle_linea WHERE cod_servicio = ?", (int(cod_servicio),)
    ).fetchone()
    return fila[0] > 0


# ──────────────────────────── facturas ────────────────────────────

def siguiente_numero(ejercicio, serie=""):
    """
    Siguiente número de la serie para ese ejercicio.

    Se calcula sobre el máximo existente, no sobre el AUTOINCREMENT de SQLite,
    para que la serie sea correlativa por año como exige la facturación.
    La fase 3 traslada esto a `core/numbering.py` junto con la anulación.
    """
    fila = conexion().execute(
        "SELECT COALESCE(MAX(numero), 0) FROM Factura WHERE serie = ? AND ejercicio = ?",
        (serie, ejercicio),
    ).fetchone()
    return fila[0] + 1


def numero_completo(fila):
    """«2025-004» a partir de una fila de Factura."""
    serie = fila["serie"] or ""
    prefijo = f"{serie}-" if serie else ""
    if fila["ejercicio"] and fila["numero"]:
        return f"{prefijo}{fila['ejercicio']}-{int(fila['numero']):03d}"
    return str(fila["Num_factura"])


def insertar_factura(fecha, base, cod_cliente, observaciones="", tipo_iva=IVA_GENERAL):
    """
    Crea una factura y le asigna su número de serie.

    `fecha` llega en formato español y se guarda en ISO. `base` es la suma de
    las líneas sin IVA; el total se calcula con `core.taxes`, que es la misma
    función que usan el listado y el PDF.
    """
    conn = conexion()
    iso = a_iso(fecha)
    ejercicio = ejercicio_de(iso)
    totales = calcular([Linea("", cantidad=1, precio_ud=base, tipo_iva=tipo_iva)])
    try:
        cur = conn.execute(
            "INSERT INTO Factura (fecha, base, tipo_iva, importe_total, Cod_cliente,"
            " observaciones, serie, ejercicio, numero)"
            " VALUES (?, ?, ?, ?, ?, ?, '', ?, ?)",
            (iso, float(totales.base), float(tipo_iva), float(totales.total),
             int(cod_cliente), observaciones, ejercicio,
             siguiente_numero(ejercicio)),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def obtener_todas_facturas():
    return conexion().execute(
        "SELECT * FROM Factura ORDER BY ejercicio DESC, numero DESC, Num_factura DESC"
    ).fetchall()


def obtener_factura_por_id(num_factura):
    return conexion().execute(
        "SELECT * FROM Factura WHERE Num_factura = ?", (int(num_factura),)
    ).fetchone()


def actualizar_factura(num_factura, fecha, base, cod_cliente, observaciones="",
                       tipo_iva=IVA_GENERAL):
    """Cambia la cabecera de una factura. El número de serie no se toca."""
    conn = conexion()
    totales = calcular([Linea("", cantidad=1, precio_ud=base, tipo_iva=tipo_iva)])
    cur = conn.execute(
        "UPDATE Factura SET fecha = ?, base = ?, tipo_iva = ?, importe_total = ?,"
        " Cod_cliente = ?, observaciones = ? WHERE Num_factura = ?",
        (a_iso(fecha), float(totales.base), float(tipo_iva), float(totales.total),
         int(cod_cliente), observaciones, int(num_factura)),
    )
    conn.commit()
    return cur.rowcount > 0


def eliminar_factura(num_factura):
    """Borra una factura. Sus líneas caen con ella por la clave ajena."""
    conn = conexion()
    cur = conn.execute("DELETE FROM Factura WHERE Num_factura = ?", (int(num_factura),))
    conn.commit()
    return cur.rowcount > 0


# ──────────────────────────── líneas ────────────────────────────

def insertar_detalle_linea(num_factura, num_linea, num_servicios, precio_por_servicio,
                           cod_servicio=None, descripcion="", unidad="ud"):
    """
    Añade una línea a una factura.

    La descripción se guarda **en la línea**: si no se pasa y sí hay servicio,
    se copia la del catálogo, para que cambiar el catálogo mañana no reescriba
    las facturas de ayer.
    """
    conn = conexion()
    if not descripcion and cod_servicio is not None:
        fila = conn.execute(
            "SELECT descripcion FROM Servicio WHERE Cod_servicio = ?", (int(cod_servicio),)
        ).fetchone()
        descripcion = fila["descripcion"] if fila else ""

    try:
        conn.execute(
            "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
            " NumServicios, unidad, precioPorServicio, cod_servicio)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(num_factura), int(num_linea), descripcion, float(num_servicios),
             unidad, float(precio_por_servicio),
             int(cod_servicio) if cod_servicio is not None else None),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def obtener_detalles_factura(num_factura):
    return conexion().execute(
        "SELECT * FROM Detalle_linea WHERE Num_Factura = ? ORDER BY Num_Linea",
        (int(num_factura),),
    ).fetchall()


def reemplazar_detalles_factura(num_factura, detalles):
    """
    Cambia de golpe todas las líneas de una factura.

    `detalles` es una lista de diccionarios con `cantidad`, `precio_ud` y,
    opcionalmente, `cod_servicio`, `descripcion` y `unidad`.
    """
    conn = conexion()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM Detalle_linea WHERE Num_Factura = ?", (int(num_factura),))
        for orden, det in enumerate(detalles, 1):
            descripcion = det.get("descripcion", "")
            cod_servicio = det.get("cod_servicio")
            if not descripcion and cod_servicio is not None:
                fila = conn.execute(
                    "SELECT descripcion FROM Servicio WHERE Cod_servicio = ?",
                    (int(cod_servicio),),
                ).fetchone()
                descripcion = fila["descripcion"] if fila else ""
            conn.execute(
                "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
                " NumServicios, unidad, precioPorServicio, cod_servicio)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(num_factura), orden, descripcion, float(det["cantidad"]),
                 det.get("unidad", "ud"), float(det["precio_ud"]),
                 int(cod_servicio) if cod_servicio is not None else None),
            )
        conn.execute("COMMIT")
        return True
    except Exception:
        conn.execute("ROLLBACK")
        return False


# Se reexporta para que la interfaz formatee fechas sin importar core.
fecha_para_pantalla = a_espanol
