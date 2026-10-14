"""
Comprueba que todo el texto de la interfaz se puede leer.

    python tools/check_contraste.py            los dos temas
    python tools/check_contraste.py --tema oscuro
    python tools/check_contraste.py --minimo 7     exigencia AAA

La WCAG 2.1 pide una razón de contraste de 4,5:1 para texto normal. El menú
lateral de la versión anterior pintaba texto `#950952` sobre fondo `#66023C`:
1,49:1, es decir, morado sobre morado (defecto 13). Esto es la puerta que
impide que vuelva a pasar.

Devuelve 0 si todos los pares pasan y 1 si alguno no llega.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from theme.tokens import MINIMO, PARES, paleta, revisar, temas

OK = "  OK  "
FALLA = " FALLA"


def comprobar(modo, minimo):
    valores = paleta(modo)
    fallos = []
    print(f"\nTema {modo} — {len(PARES)} pares, mínimo {minimo:.1f}:1\n")
    for razon, frente, fondo, descripcion in sorted(revisar(modo)):
        bien = razon >= minimo
        if not bien:
            fallos.append((razon, frente, fondo, descripcion))
        print(
            f"[{OK if bien else FALLA}] {razon:5.2f}:1  "
            f"{valores[frente]} sobre {valores[fondo]}   {descripcion}"
        )
    return fallos


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--tema", choices=temas(), default=None)
    parser.add_argument("--minimo", type=float, default=MINIMO)
    args = parser.parse_args()

    fallos = []
    for modo in ((args.tema,) if args.tema else temas()):
        fallos += comprobar(modo, args.minimo)

    print()
    if fallos:
        print(f"{len(fallos)} par(es) por debajo de {args.minimo:.1f}:1:")
        for razon, frente, fondo, _ in fallos:
            print(f"  · {frente} sobre {fondo}: {razon:.2f}:1")
        print()
        return 1
    print(f"Todos los pares llegan a {args.minimo:.1f}:1.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
