"""
NIF, NIE y CIF.

El validador anterior solo aceptaba el patrón «8 dígitos + letra», así que
**un cliente con NIE no se podía dar de alta**: cualquier residente extranjero
quedaba fuera del programa. Y el de CIF exigía dígito de control numérico en
los tipos C, D, F, G, J, U y V, cuando esos admiten las dos formas, de modo
que rechazaba CIF perfectamente válidos (defecto 12 de la auditoría).
"""

import re

# La letra del NIF sale del resto de dividir el número entre 23.
LETRAS_NIF = "TRWAGMYFPDXBNJZSQVHLCKE"

# En el NIE la primera letra vale como un dígito: X=0, Y=1, Z=2.
PREFIJOS_NIE = {"X": "0", "Y": "1", "Z": "2"}

# Tipos de CIF cuyo carácter de control tiene que ser una letra: entidades sin
# ánimo de lucro, organismos públicos, congregaciones…
CIF_CONTROL_LETRA = "KPQRSNW"
# Tipos cuyo control tiene que ser una cifra: sociedades anónimas, limitadas…
CIF_CONTROL_CIFRA = "ABEH"
# El resto (C, D, F, G, J, L, M, U, V) admite cualquiera de las dos.
LETRAS_CIF = "JABCDEFGHI"

PATRON_NIF = re.compile(r"^[0-9]{8}[A-Z]$")
PATRON_NIE = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")
PATRON_CIF = re.compile(r"^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[0-9A-J]$")


def normalizar(valor):
    """Quita espacios y guiones y pasa a mayúsculas."""
    if not valor:
        return ""
    return re.sub(r"[\s\-\.]", "", str(valor)).upper()


def letra_nif(numero):
    """Letra que le corresponde a un número de ocho cifras."""
    return LETRAS_NIF[int(numero) % 23]


def es_nif(valor):
    """NIF de persona física: ocho cifras y su letra."""
    valor = normalizar(valor)
    if not PATRON_NIF.match(valor):
        return False
    return valor[8] == letra_nif(valor[:8])


def es_nie(valor):
    """
    NIE de residente extranjero: X, Y o Z, siete cifras y letra.

    La letra inicial se sustituye por su cifra y se aplica el mismo módulo 23
    que el NIF.
    """
    valor = normalizar(valor)
    if not PATRON_NIE.match(valor):
        return False
    numero = PREFIJOS_NIE[valor[0]] + valor[1:8]
    return valor[8] == letra_nif(numero)


def es_nif_o_nie(valor):
    """Documento válido de una persona física, sea española o extranjera."""
    return es_nif(valor) or es_nie(valor)


def _control_cif(numeros):
    """Dígito de control de un CIF, por el algoritmo de la AEAT."""
    pares = sum(int(d) for i, d in enumerate(numeros) if i % 2 == 1)
    impares = 0
    for i, d in enumerate(numeros):
        if i % 2 == 0:
            doble = int(d) * 2
            impares += doble - 9 if doble > 9 else doble
    unidad = (pares + impares) % 10
    return 10 - unidad if unidad else 0


def es_cif(valor):
    """CIF de persona jurídica."""
    valor = normalizar(valor)
    if not PATRON_CIF.match(valor):
        return False

    tipo, numeros, control = valor[0], valor[1:8], valor[8]
    esperado = _control_cif(numeros)
    como_cifra = str(esperado)
    como_letra = LETRAS_CIF[esperado]

    if tipo in CIF_CONTROL_LETRA:
        return control == como_letra
    if tipo in CIF_CONTROL_CIFRA:
        return control == como_cifra
    # Los demás tipos admiten las dos formas. El validador anterior no lo
    # contemplaba y rechazaba, por ejemplo, un G con letra de control.
    return control in (como_cifra, como_letra)


def es_documento_fiscal(valor):
    """Cualquiera de los tres: NIF, NIE o CIF."""
    return es_nif_o_nie(valor) or es_cif(valor)
