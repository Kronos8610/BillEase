"""
Aplicar las migraciones desde la terminal.

    python -m data.migrations --dry-run
    python -m data.migrations
    python -m data.migrations --base tests/fixtures/baseline.db
"""

import argparse
from pathlib import Path

from config import ruta_base_datos
from data.connection import abrir
from data.migrations import aplicadas, migrar


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--base", help="fichero a migrar (por defecto, el de la aplicación)")
    parser.add_argument(
        "--dry-run", action="store_true", help="enseña qué se aplicaría, sin tocar nada"
    )
    args = parser.parse_args()

    ruta = Path(args.base) if args.base else ruta_base_datos()
    if not ruta.exists():
        print(f"\nNo existe la base {ruta}.\n")
        return 2

    conn = abrir(ruta)
    try:
        print(f"\nBase: {ruta}")
        print(f"Versiones ya aplicadas: {sorted(aplicadas(conn)) or 'ninguna'}\n")
        migrar(conn, ruta=ruta, dry_run=args.dry_run)
        print()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
