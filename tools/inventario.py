"""
Inventario de una base de datos de BillEase.

Módulo compartido por `baseline.py` (que lo congela) y `verify.py` (que lo
comprueba). No importa Qt ni nada de la interfaz: se puede ejecutar en un
servidor sin pantalla.
"""

import hashlib
import sqlite3
from pathlib import Path

BASE_POR_DEFECTO = Path("BillEase.db")
FICHERO_BASELINE = Path("tests/fixtures/baseline.json")

TABLAS = ("Autonomo", "Cliente", "Factura", "Servicio", "Detalle_linea")


def sha256(ruta):
    """Huella del fichero, para saber si la base es la misma de siempre."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def leer(ruta=BASE_POR_DEFECTO):
    """
    Devuelve el inventario de la base como un diccionario simple.

    Son las cifras contra las que se verifica cada fase de la ruta: si una
    migración las mueve, algo se ha perdido por el camino.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la base de datos: {ruta}")

    conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        tablas_existentes = {
            fila[0]
            for fila in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        conteos = {}
        for tabla in TABLAS:
            if tabla in tablas_existentes:
                conteos[tabla] = cur.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]

        suma_bases = cur.execute("SELECT COALESCE(SUM(total), 0) FROM Factura").fetchone()[0]

        # La suma de las líneas tiene que cuadrar con la suma de los totales
        # guardados. Es el invariante que delata una migración mal hecha.
        if "Detalle_linea" in tablas_existentes:
            suma_lineas = cur.execute(
                "SELECT COALESCE(SUM(NumServicios * precioPorServicio), 0) FROM Detalle_linea"
            ).fetchone()[0]
        else:
            suma_lineas = 0.0

        numeros = [
            fila[0]
            for fila in cur.execute("SELECT Num_factura FROM Factura ORDER BY Num_factura")
        ]

        # Líneas que apuntan a un servicio inexistente. Mientras sea 0, la
        # migración de la fase 2 puede copiar la descripción sin perder nada.
        if {"Detalle_linea", "Servicio"} <= tablas_existentes:
            huerfanas = cur.execute(
                "SELECT COUNT(*) FROM Detalle_linea d "
                "LEFT JOIN Servicio s ON s.Cod_servicio = d.cod_servicio "
                "WHERE s.Cod_servicio IS NULL"
            ).fetchone()[0]
        else:
            huerfanas = 0

        return {
            "conteos": conteos,
            "suma_bases": round(float(suma_bases), 2),
            "suma_lineas": round(float(suma_lineas), 2),
            "numeros_factura": [int(n) for n in numeros],
            "lineas_huerfanas": huerfanas,
            "sha256": sha256(ruta),
        }
    finally:
        conn.close()


def formatear(inv):
    """Inventario en texto, para mirarlo por encima desde la terminal."""
    lineas = []
    for tabla in TABLAS:
        if tabla in inv["conteos"]:
            lineas.append(f"  {tabla:<14} {inv['conteos'][tabla]:>4}")
    lineas.append(f"  {'suma de bases':<14} {inv['suma_bases']:>10.2f} €")
    lineas.append(f"  {'suma de líneas':<14} {inv['suma_lineas']:>10.2f} €")
    lineas.append(f"  {'facturas':<14} {inv['numeros_factura']}")
    lineas.append(f"  {'huérfanas':<14} {inv['lineas_huerfanas']:>4}")
    lineas.append(f"  {'sha256':<14} {inv['sha256'][:16]}…")
    return "\n".join(lineas)
