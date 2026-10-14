"""
Comprueba que el aspecto se decide en un sitio y no en cada widget.

    python tools/check_estilos.py
    python tools/check_estilos.py --maximo 0

Dos cosas, las dos de la puerta 5:

1. **`setStyleSheet` casi no se usa.** Qt vuelve a analizar la hoja en cada
   llamada, y repartir colores por los widgets es lo que hacía imposible tener
   tema oscuro. La versión anterior hacía 54 llamadas; ahora solo la hay en
   `theme/`, que viste la aplicación entera de una vez.
2. **Cero emojis en la interfaz.** Un emoji lo dibuja la fuente del sistema y
   sale distinto en cada máquina; los iconos son SVG propios (`ui/iconos.py`).

Devuelve 0 si se cumple y 1 si no.
"""

import argparse
import ast
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Donde se mira: el código de la aplicación, no las pruebas ni las
# herramientas (una prueba puede necesitar forzar un estilo).
PAQUETES = ("ui", "theme", "core", "data", "documents")
SUELTOS = ("main_start.py", "config.py")

MAXIMO = 5


def ficheros():
    for paquete in PAQUETES:
        carpeta = RAIZ / paquete
        if carpeta.exists():
            yield from sorted(
                p for p in carpeta.rglob("*.py") if "__pycache__" not in p.parts
            )
    for nombre in SUELTOS:
        if (RAIZ / nombre).exists():
            yield RAIZ / nombre


def llamadas_a_estilo(ruta):
    """Las líneas donde se llama a `setStyleSheet`, leyendo el árbol sintáctico."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    encontradas = []
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "setStyleSheet"):
            encontradas.append(nodo.lineno)
    return encontradas


def es_emoji(caracter):
    """
    Un emoji de verdad, no cualquier carácter que no sea una letra.

    Se mira por bloques de Unicode, no por categoría: los acentos, la «ñ», el
    «€», las comillas españolas, los guiones largos y las rayas con las que
    están dibujadas las separaciones de los comentarios son texto normal y
    tienen que poder usarse. Los cinco emojis del menú anterior —🏠 📄 📝 ➕
    🗑— caen todos dentro de estos bloques.
    """
    punto = ord(caracter)
    bloques = (
        (0x1F000, 0x1FAFF),   # emoticonos, pictogramas, símbolos y fichas
        (0x1F1E6, 0x1F1FF),   # banderas
        (0x2600, 0x27BF),     # símbolos varios y dingbats (➕, ✂, ⚠…)
        (0x2B00, 0x2BFF),     # flechas y formas decorativas
        (0xFE00, 0xFE0F),     # selectores de variación de emoji
    )
    return any(desde <= punto <= hasta for desde, hasta in bloques)


def _docstrings(arbol):
    """Los textos que son documentación, no interfaz: nunca se pintan."""
    sueltos = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        cuerpo = getattr(nodo, "body", ())
        if (cuerpo and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)):
            sueltos.add(id(cuerpo[0].value))
    return sueltos


def emojis(ruta):
    """
    Emojis en texto que puede acabar en la pantalla.

    Se mira el árbol sintáctico, no el fichero en bruto: lo que cuenta es un
    texto que se le pasa a un widget. Un comentario o una cadena de
    documentación que explique qué emojis se retiraron no se pinta en ninguna
    parte, así que no es un emoji en la interfaz.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    documentacion = _docstrings(arbol)
    encontrados = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Constant) or not isinstance(nodo.value, str):
            continue
        if id(nodo) in documentacion:
            continue
        for caracter in nodo.value:
            if es_emoji(caracter):
                encontrados.append((nodo.lineno, caracter, nodo.value.strip()[:70]))
    return encontrados


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--maximo", type=int, default=MAXIMO,
                        help=f"llamadas a setStyleSheet admitidas (por defecto {MAXIMO})")
    args = parser.parse_args()

    total = 0
    con_emoji = []
    print("\nHojas de estilo repartidas por el código\n")
    for ruta in ficheros():
        lineas = llamadas_a_estilo(ruta)
        if lineas:
            relativa = ruta.relative_to(RAIZ)
            print(f"  {relativa}:{','.join(str(n) for n in lineas)}  "
                  f"→ {len(lineas)} llamada(s)")
            total += len(lineas)
        for numero, caracter, texto in emojis(ruta):
            con_emoji.append((ruta.relative_to(RAIZ), numero, caracter, texto))

    if not total:
        print("  (ninguna)")

    print(f"\n  total: {total} llamada(s) a setStyleSheet (máximo {args.maximo})")

    print("\nEmojis en la interfaz\n")
    if con_emoji:
        for relativa, numero, caracter, texto in con_emoji:
            print(f"  {relativa}:{numero}  «{caracter}»  {texto}")
    else:
        print("  (ninguno)")

    fallos = []
    if total > args.maximo:
        fallos.append(f"{total} llamadas a setStyleSheet; el máximo es {args.maximo}")
    if con_emoji:
        fallos.append(f"{len(con_emoji)} emoji(s) en la interfaz; deben ser iconos SVG")

    print()
    if fallos:
        for fallo in fallos:
            print(f"FALLA: {fallo}")
        print()
        return 1
    print("Una sola hoja de estilos y ningún emoji.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
