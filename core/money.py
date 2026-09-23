"""
Aritmética de dinero.

Todo importe se calcula con `Decimal`, nunca con `float`. Con coma flotante
binaria 0,1 + 0,2 no es 0,3, y en una factura eso acaba siendo un céntimo que
no cuadra con la suma de las líneas.

Vive aparte para que lo puedan usar tanto los modelos como el cálculo de
impuestos sin que uno dependa del otro.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTIMO = Decimal("0.01")


def a_decimal(valor):
    """
    Convierte a Decimal sin heredar el ruido de la coma flotante.

    `Decimal(0.1)` es 0,1000000000000000055511151231257827…, mientras que
    `Decimal("0.1")` es exactamente 0,1. Por eso se pasa siempre por `str`.
    Acepta también la coma decimal española.
    """
    if isinstance(valor, Decimal):
        return valor
    if valor is None or valor == "":
        return Decimal("0")
    return Decimal(str(valor).replace(",", ".").strip())


def redondear(valor):
    """Redondea a céntimos con la regla comercial (0,005 sube a 0,01)."""
    return a_decimal(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def formatear(valor):
    """Importe en formato español: 1.736,35"""
    entero, _, decimales = f"{redondear(valor):.2f}".partition(".")
    negativo = entero.startswith("-")
    entero = entero.lstrip("-")
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    return ("-" if negativo else "") + ".".join(grupos) + "," + decimales
