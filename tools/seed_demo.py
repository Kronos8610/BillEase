"""
Genera una base de datos de demostración con datos ficticios.

    python tools/seed_demo.py                                   crea BillEase.db
    python tools/seed_demo.py --salida tests/fixtures/baseline.db
    python tools/seed_demo.py --forzar                          sobrescribe

Sustituye al antiguo `test.py`, que no era una prueba sino un script que
insertaba un autónomo en la base real. Aquí los datos son claramente
inventados y la base se genera entera desde cero, así que ya no hace falta
versionar ningún fichero `.db`.

Credenciales de la demostración:
    carlos.garcia@billease.es  /  Pass1234

Se genera el esquema original y después se aplican las migraciones, igual que
le pasaría a la base de un usuario que viniera de una versión antigua. Con
`--sin-migrar` se queda en el esquema de partida, que es lo que necesitan las
pruebas de migración.

Los NIF y CIF son inventados pero **válidos**: pasan la comprobación del dígito
de control, para que editar un cliente de la demostración no dé error.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.connection import abrir
from data.schema import ESQUEMA_INICIAL

AUTONOMO = (
    "12345678Z", "Carlos", "García López", "Calle Mayor 12, 2ºA",
    "28001", "612345678", "carlos.garcia@billease.es", "Pass1234",
)

# (TIPO_CLIENTE, nombre, direccion, telefono, cod_postal, CIFNIF, observaciones, email)
# TIPO_CLIENTE: 0 = persona jurídica, 1 = persona física
CLIENTES = [
    (0, "Construcciones Pérez S.L.", "Av. Industria 45", "654321098", "08020",
     "B12345674", "Cliente habitual", "contacto@construccionesperez.es"),
    (1, "María Fernández Ruiz", "C/ Rosales 8, 3ºB", "666111222", "28030",
     "87654321X", "", "maria.fernandez@gmail.com"),
    (0, "Reformas Norte S.A.", "Pol. Industrial km 3", "911223344", "33001",
     "C87654323", "Pago a 30 días", "admin@reformasnorte.com"),
    (1, "Antonio Martínez Soto", "Pza. España 1", "699887766", "41001",
     "22334455Y", "", "antonio.martinez@hotmail.com"),
    (0, "Logística Sur S.L.", "Av. del Puerto 20", "955443322", "11006",
     "D11223344", "Pago transferencia", "info@logisticasur.es"),
]

# (descripcion, precio, observaciones)
SERVICIOS = [
    ("Instalación de fontanería", 85.0, "Por hora de trabajo"),
    ("Instalación eléctrica", 95.0, "Incluye material básico"),
    ("Pintura interior m²", 12.5, "Precio por metro cuadrado"),
    ("Transporte de materiales", 60.0, "Trayecto urbano"),
    ("Mano de obra general", 45.0, "Por hora"),
    ("Instalación de espejos", 75.5, "Incluye fijaciones"),
    ("Limpieza post-obra", 30.0, "Por hora"),
    ("Asesoría técnica", 110.0, "Por visita"),
]

# (fecha, total, cod_cliente, observaciones)
# El campo `total` guarda la base imponible, sin IVA: es el defecto 01 de la
# auditoría, que arregla la fase 1. Aquí se reproduce tal cual para que la
# línea base refleje la realidad de hoy.
FACTURAS = [
    ("15/01/2025", 480.0, 1, "Reforma cocina fase 1"),
    ("22/01/2025", 211.0, 2, ""),
    ("03/02/2025", 1420.0, 3, "Nave industrial sector B"),
    ("14/02/2025", 537.5, 1, "Reforma baño principal"),
    ("28/02/2025", 110.0, 4, ""),
    ("10/03/2025", 830.0, 5, "Ampliación almacén"),
    ("25/03/2025", 180.0, 2, "Segunda visita"),
]

# (num_factura, num_linea, cantidad, precio_ud, cod_servicio)
LINEAS = [
    (1, 1, 3, 85.0, 1), (1, 2, 5, 45.0, 5),
    (2, 1, 2, 75.5, 6), (2, 2, 2, 30.0, 7),
    (3, 1, 8, 95.0, 2), (3, 2, 12, 45.0, 5), (3, 3, 2, 60.0, 4),
    (4, 1, 2, 85.0, 1), (4, 2, 15, 12.5, 3), (4, 3, 4, 45.0, 5),
    (5, 1, 1, 110.0, 8),
    (6, 1, 4, 95.0, 2), (6, 2, 3, 60.0, 4), (6, 3, 6, 45.0, 5),
    (7, 1, 3, 30.0, 7), (7, 2, 2, 45.0, 5),
]


def crear_esquema(conn):
    """
    Crea el esquema **original**, con sus defectos incluidos.

    Se genera la versión de partida a propósito: así la base de demostración
    recorre después las mismas migraciones que la de un usuario que venía de
    una versión antigua, y las pruebas de migración tienen contra qué correr.
    """
    for sentencia in ESQUEMA_INICIAL:
        conn.execute(sentencia)
    conn.commit()


def rellenar(conn):
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Autonomo (DNI, nombre, apellido, direccion, codigo_postal,"
            " telefono, email, contrasena) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            AUTONOMO,
        )
        cur.executemany(
            "INSERT INTO Cliente (TIPO_CLIENTE, nombre_o_razon_social, direccion,"
            " telefono, cod_postal, CIFNIF, observaciones, email)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            CLIENTES,
        )
        cur.executemany(
            "INSERT INTO Servicio (descripcion, precio, observaciones) VALUES (?, ?, ?)",
            SERVICIOS,
        )
        cur.executemany(
            "INSERT INTO Factura (fecha, total, Cod_cliente, observaciones)"
            " VALUES (?, ?, ?, ?)",
            FACTURAS,
        )
        cur.executemany(
            "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, NumServicios,"
            " precioPorServicio, cod_servicio) VALUES (?, ?, ?, ?, ?)",
            LINEAS,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--salida", default=None, help="fichero a generar")
    parser.add_argument(
        "--forzar", action="store_true", help="sobrescribe el fichero si ya existe"
    )
    parser.add_argument(
        "--sin-migrar", action="store_true",
        help="deja la base en el esquema original, sin aplicar las migraciones",
    )
    args = parser.parse_args()

    if args.salida:
        destino = Path(args.salida)
    else:
        from config import ruta_base_datos
        destino = ruta_base_datos()
    if destino.exists() and not args.forzar:
        print(f"\n{destino} ya existe. Añade --forzar para sobrescribirla.\n")
        return 1
    if destino.exists():
        destino.unlink()

    conn = abrir(destino)
    try:
        crear_esquema(conn)
        rellenar(conn)
        if not args.sin_migrar:
            from data.migrations import migrar
            migrar(conn, registrar=lambda *_: None)
    finally:
        conn.close()

    print(f"\nBase de demostración creada en {destino}")
    print(f"  {len(CLIENTES)} clientes · {len(SERVICIOS)} servicios · "
          f"{len(FACTURAS)} facturas · {len(LINEAS)} líneas")
    if args.sin_migrar:
        print("  esquema original, sin migrar (--sin-migrar)")
    print("  acceso: carlos.garcia@billease.es / Pass1234\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
