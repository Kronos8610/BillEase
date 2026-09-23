"""
Migraciones de la base de datos.

Cada migración es un módulo con tres cosas: `VERSION`, `DESCRIPCION` y una
función `aplicar(conn)`. El orden lo da el número, y lo aplicado se anota en
la tabla `schema_migrations`, así que **ejecutarlas dos veces no cambia
nada**: es la propiedad que permite arrancar la aplicación con confianza sin
saber de qué versión viene la base del usuario.

Uso desde la terminal:

    python -m data.migrations --dry-run           qué se aplicaría
    python -m data.migrations                     aplicar
    python -m data.migrations --base copia.db     sobre otro fichero

Antes de tocar nada se guarda una copia con la fecha en el nombre.
"""

import shutil
from datetime import datetime
from pathlib import Path

from data.migrations._esquema import reconstruir_tabla  # noqa: F401  (reexportado)
from data.migrations import (
    m001_tipos_texto,
    m002_fechas_iso,
    m003_importes,
    m004_serie_fiscal,
    m005_lineas_con_texto,
    m006_password_hash,
)

MIGRACIONES = (
    m001_tipos_texto,
    m002_fechas_iso,
    m003_importes,
    m004_serie_fiscal,
    m005_lineas_con_texto,
    m006_password_hash,
)


def _asegurar_registro(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version   INTEGER PRIMARY KEY,
            aplicada  TEXT NOT NULL,
            descripcion TEXT
        )
        """
    )


def aplicadas(conn):
    """Versiones ya aplicadas a esta base."""
    _asegurar_registro(conn)
    return {fila[0] for fila in conn.execute("SELECT version FROM schema_migrations")}


def pendientes(conn):
    """Migraciones que le faltan a esta base, en orden."""
    hechas = aplicadas(conn)
    return [m for m in MIGRACIONES if m.VERSION not in hechas]


def copia_de_seguridad(ruta):
    """Guarda una copia con fecha junto al fichero original."""
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = ruta.with_name(f"{ruta.name}.{marca}.bak")
    shutil.copy2(ruta, destino)
    return destino


def migrar(conn, ruta=None, dry_run=False, registrar=print):
    """
    Aplica las migraciones que le falten a la base.

    Devuelve la lista de versiones aplicadas (vacía si ya estaba al día).
    Cada migración va en su propia transacción: si una falla, las anteriores
    quedan aplicadas y la base sigue siendo coherente.
    """
    faltan = pendientes(conn)
    if not faltan:
        registrar("La base ya está al día.")
        return []

    registrar(f"Migraciones pendientes: {len(faltan)}")
    for m in faltan:
        registrar(f"  {m.VERSION:03d}  {m.DESCRIPCION}")

    if dry_run:
        registrar("\nNada aplicado (--dry-run).")
        return []

    if ruta:
        copia = copia_de_seguridad(ruta)
        if copia:
            registrar(f"\nCopia de seguridad: {copia}")

    hechas = []
    for m in faltan:
        # Las claves ajenas se apagan mientras se rehacen tablas y se vuelven
        # a comprobar antes de confirmar: es el procedimiento de SQLite.
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN")
            m.aplicar(conn)
            problemas = conn.execute("PRAGMA foreign_key_check").fetchall()
            if problemas:
                raise RuntimeError(
                    f"la migración {m.VERSION:03d} deja claves ajenas rotas: {problemas[:3]}"
                )
            conn.execute(
                "INSERT INTO schema_migrations (version, aplicada, descripcion)"
                " VALUES (?, ?, ?)",
                (m.VERSION, datetime.now().isoformat(timespec="seconds"), m.DESCRIPCION),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

        registrar(f"  aplicada {m.VERSION:03d}  {m.DESCRIPCION}")
        hechas.append(m.VERSION)

    return hechas
