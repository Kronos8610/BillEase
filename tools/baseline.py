"""
Congela la fotografía de partida de la base de datos.

    python tools/baseline.py              muestra el inventario actual
    python tools/baseline.py --escribir   lo guarda en tests/fixtures/baseline.json

El fichero resultante es la referencia contra la que `verify.py` comprueba
todas las fases de la ruta. Se escribe UNA vez, en la fase 0; a partir de ahí
solo se vuelve a tocar si el cambio de cifras es intencionado y está
justificado en el mensaje del commit.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventario import BASE_POR_DEFECTO, FICHERO_BASELINE, formatear, leer


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help="base de datos a leer")
    parser.add_argument("--salida", default=FICHERO_BASELINE, help="fichero JSON a escribir")
    parser.add_argument(
        "--escribir", action="store_true", help="guarda el inventario en disco"
    )
    args = parser.parse_args()

    try:
        inv = leer(args.base)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Genera una base de demostración con:  python tools/seed_demo.py")
        return 2

    print(f"\nInventario de {args.base}\n")
    print(formatear(inv))
    print()

    if not args.escribir:
        print("Nada escrito. Añade --escribir para guardarlo como línea base.\n")
        return 0

    salida = Path(args.salida)
    if salida.exists():
        anterior = json.loads(salida.read_text(encoding="utf-8"))
        if anterior != inv:
            print(f"AVISO: {salida} ya existe y NO coincide con la base actual.")
            print("Sobrescribirla borra la referencia de las verificaciones.")
            respuesta = input("¿Sobrescribir de todas formas? [s/N] ").strip().lower()
            if respuesta != "s":
                print("Cancelado.\n")
                return 1

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(
        json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Línea base escrita en {salida}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
