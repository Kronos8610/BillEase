"""
005 · Las líneas guardan su propio texto.

Cada línea apuntaba a un servicio del catálogo, así que no se podía escribir
un concepto cualquiera: había que darlo de alta antes. Y cambiar la
descripción de un servicio reescribía retroactivamente todas las facturas
antiguas que lo usaban.

Ahora cada línea guarda la descripción y la unidad que le corresponden, y se
copia el texto del servicio al que apuntaba: las dieciséis líneas existentes
conservan exactamente lo que decían.

`cod_servicio` se mantiene, de momento nulo permitido, porque las pantallas de
crear y editar factura todavía usan el catálogo. La fase 4 lo retira junto con
la tabla `Servicio`, cuando ninguna pantalla lo lea.
"""

from data.migrations._esquema import reconstruir_tabla

VERSION = 5
DESCRIPCION = "Las líneas guardan descripción y unidad propias"


DETALLE = """
    CREATE TABLE {tabla} (
        Num_Factura        INTEGER NOT NULL,
        Num_Linea          INTEGER NOT NULL,
        descripcion        TEXT NOT NULL DEFAULT '',
        NumServicios       REAL NOT NULL,
        unidad             TEXT NOT NULL DEFAULT 'ud',
        precioPorServicio  REAL NOT NULL,
        cod_servicio       INTEGER,
        PRIMARY KEY (Num_Factura, Num_Linea),
        FOREIGN KEY (Num_Factura) REFERENCES Factura (Num_factura) ON DELETE CASCADE
    )
"""


def aplicar(conn):
    reconstruir_tabla(
        conn,
        "Detalle_linea",
        DETALLE,
        ["Num_Factura", "Num_Linea", "descripcion", "NumServicios",
         "unidad", "precioPorServicio", "cod_servicio"],
        "SELECT CAST(d.Num_Factura AS INTEGER), CAST(d.Num_Linea AS INTEGER),"
        " COALESCE(s.descripcion, ''),"       # el texto del catálogo pasa a ser de la línea
        " d.NumServicios, 'ud', d.precioPorServicio,"
        " CAST(d.cod_servicio AS INTEGER)"
        " FROM Detalle_linea d"
        " LEFT JOIN Servicio s ON s.Cod_servicio = d.cod_servicio",
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_linea_servicio ON Detalle_linea (cod_servicio)"
    )
