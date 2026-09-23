"""
Teléfono, código postal y correo.

El validador de teléfono anterior rechazaba «612 34 56 78» por llevar
espacios, que es exactamente como lo tiene todo el mundo apuntado en la
agenda. Ahora se normaliza antes de comprobar: el usuario escribe como quiera
y el programa guarda una forma canónica.
"""

import re

PATRON_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Las provincias españolas van de la 01 a la 52.
PATRON_CP = re.compile(r"^(0[1-9]|[1-4][0-9]|5[0-2])[0-9]{3}$")

PATRON_TELEFONO = re.compile(r"^[6789][0-9]{8}$")


def normalizar_telefono(valor):
    """
    Deja el número en nueve cifras, quitando adornos y el prefijo de España.

    «+34 612 34 56 78», «0034-612345678» y «612345678» son el mismo teléfono.
    """
    if not valor:
        return ""
    limpio = re.sub(r"[\s\-\.\(\)/]", "", str(valor))
    if limpio.startswith("+34"):
        limpio = limpio[3:]
    elif limpio.startswith("0034"):
        limpio = limpio[4:]
    elif limpio.startswith("34") and len(limpio) == 11:
        limpio = limpio[2:]
    return limpio


def es_telefono(valor):
    """Teléfono español de nueve cifras que empieza por 6, 7, 8 o 9."""
    return bool(PATRON_TELEFONO.match(normalizar_telefono(valor)))


def normalizar_cp(valor):
    """
    Código postal a cinco cifras, recuperando el cero inicial si falta.

    Acepta el número que devuelve una columna REAL de las bases sin migrar
    (8001.0 es Barcelona, 08001) y también el caso de quien escribe cuatro
    cifras porque se ha comido el cero. Cuatro cifras se completan; menos, no:
    ahí ya no hay forma de saber qué falta.
    """
    if valor in (None, ""):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    limpio = re.sub(r"\D", "", str(valor))
    if len(limpio) == 4:
        return "0" + limpio
    return limpio


def es_codigo_postal(valor):
    """Código postal español: provincia del 01 al 52 y tres cifras más."""
    return bool(PATRON_CP.match(normalizar_cp(valor)))


def es_email(valor):
    return bool(valor) and bool(PATRON_EMAIL.match(str(valor).strip()))


def es_contrasena(valor):
    """Ocho caracteres como mínimo, con al menos una letra y una cifra."""
    if not valor:
        return False
    return (
        len(valor) >= 8
        and any(c.isalpha() for c in valor)
        and any(c.isdigit() for c in valor)
    )
