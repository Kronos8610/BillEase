"""
El esquema de partida.

Es el `CREATE TABLE` original, con sus defectos incluidos: columnas REAL para
códigos postales, fechas en texto libre y una columna «total» que guardaba la
base imponible. No se corrige aquí.

Las migraciones de `data/migrations/` lo llevan hasta la versión actual, de
modo que una base nueva recorre exactamente el mismo camino que la de un
usuario que viniera de una versión antigua. Con dos definiciones separadas
—una «nueva» y otra «migrada»— acabarían divergiendo.
"""

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


def crear_esquema_y_migrar(conn=None):
    """
    Crea el esquema de partida y lo pone al día.

    Es el camino que recorre cualquier base: la de un usuario nuevo y la de
    quien viene de una versión antigua pasan por las mismas migraciones.
    """
    from data.connection import conexion
    from data.migrations import migrar

    conn = conn or conexion()
    for sentencia in ESQUEMA_INICIAL:
        conn.execute(sentencia)
    conn.commit()
    migrar(conn, registrar=lambda *_: None)
    return conn
