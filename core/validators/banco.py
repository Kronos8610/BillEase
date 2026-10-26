"""
La cuenta donde se cobra: entidad e IBAN.

Un IBAN mal escrito no se nota hasta que el cliente intenta transferir y el
banco le devuelve el dinero, así que se comprueba el dígito de control antes
de guardarlo: el mismo algoritmo (módulo 97) que usa cualquier banco.

Se guarda sin espacios y en mayúsculas, y se enseña en grupos de cuatro, que
es como se lee y como se copia.
"""

import re

# ES + 2 de control + 20 dígitos = 24 caracteres. Se admite cualquier país
# —un autónomo puede cobrar en una cuenta de otro— con el largo que le toque.
LARGOS = {
    "ES": 24, "PT": 25, "FR": 27, "DE": 22, "IT": 27, "GB": 22, "NL": 18,
    "BE": 16, "AD": 24, "IE": 22, "LU": 20, "CH": 21, "AT": 20, "PL": 28,
}
FORMATO = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$")
GRUPO = 4


def normalizar_iban(texto):
    """Sin espacios, sin guiones y en mayúsculas: como se guarda."""
    return re.sub(r"[^A-Za-z0-9]", "", str(texto or "")).upper()


def formatear_iban(texto):
    """En grupos de cuatro: `ES91 2100 0418 4502 0005 1332`."""
    limpio = normalizar_iban(texto)
    return " ".join(limpio[i:i + GRUPO] for i in range(0, len(limpio), GRUPO))


def es_iban(texto):
    """
    Comprueba el dígito de control del IBAN, con el módulo 97 de la norma.

    Se mueven los cuatro primeros caracteres al final, cada letra se
    convierte en dos cifras (A=10 … Z=35) y el número resultante tiene que
    dar resto 1 al dividirlo entre 97.
    """
    limpio = normalizar_iban(texto)
    if not FORMATO.match(limpio):
        return False

    largo = LARGOS.get(limpio[:2])
    if largo and len(limpio) != largo:
        return False

    movido = limpio[4:] + limpio[:4]
    numero = "".join(
        str(ord(c) - ord("A") + 10) if c.isalpha() else c for c in movido
    )
    return int(numero) % 97 == 1


def es_entidad(texto):
    """El nombre del banco: lo que haya, pero algo. No se valida más."""
    return bool(str(texto or "").strip())
