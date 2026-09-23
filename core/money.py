"""
Aritmética de dinero.

Todo importe se calcula con `Decimal`, nunca con `float`. Con coma flotante
binaria 0,1 + 0,2 no es 0,3, y en una factura eso acaba siendo un céntimo que
no cuadra con la suma de las líneas.

Vive aparte para que lo puedan usar tanto los modelos como el cálculo de
impuestos sin que uno dependa del otro.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

CENTIMO = Decimal("0.01")

# «1.240», «12.345.678»: un punto cada tres cifras es separador de miles, no
# decimal. Sin esto, leer de vuelta lo que el propio programa ha escrito
# («1.240,00») daba un importe corrupto.
MILES = re.compile(r"^-?\d{1,3}(\.\d{3})+$")


def normalizar_numero(texto):
    """
    Deja un número escrito a la española en forma de que Decimal lo entienda.

    Casos que llegan de verdad:
        «1.240,00»  → 1240.00   (lo que escribe el propio programa)
        «12,50»     → 12.50     (coma decimal, lo normal aquí)
        «12.50»     → 12.50     (punto decimal, de quien tiene esa costumbre)
        «1.240»     → 1240      (punto de millar, sin decimales)

    Cuando aparecen los dos separadores, el de la derecha es el decimal.
    """
    texto = str(texto).strip().replace(" ", "")
    if not texto:
        return "0"

    tiene_coma = "," in texto
    tiene_punto = "." in texto

    if tiene_coma and tiene_punto:
        if texto.rfind(",") > texto.rfind("."):
            return texto.replace(".", "").replace(",", ".")
        return texto.replace(",", "")
    if tiene_coma:
        return texto.replace(",", ".")
    if tiene_punto and MILES.match(texto):
        return texto.replace(".", "")
    return texto


def a_decimal(valor):
    """
    Convierte a Decimal sin heredar el ruido de la coma flotante.

    `Decimal(0.1)` es 0,1000000000000000055511151231257827…, mientras que
    `Decimal("0.1")` es exactamente 0,1. Por eso se pasa siempre por `str`.
    """
    if isinstance(valor, Decimal):
        return valor
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    return Decimal(normalizar_numero(valor))


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
