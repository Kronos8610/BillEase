"""
Contraseña del autónomo.

Hasta ahora se guardaba en claro: abrir el fichero de la base con cualquier
visor mostraba «Pass1234» (defecto 03). Y el `login()` comparaba cadenas, así
que quien pudiera leer el fichero entraba.

Ahora se guarda un hash de Argon2, que es lento a propósito: probar
contraseñas a lo bruto deja de ser viable. Del hash no se puede volver a la
contraseña.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

# Parámetros por defecto de argon2-cffi: pensados para un ordenador de
# escritorio, ni tan flojos que sean inútiles ni tan duros que el acceso tarde.
_hasher = PasswordHasher()

PREFIJO = "$argon2"


def hashear(contrasena):
    """Devuelve el hash que hay que guardar en la base."""
    return _hasher.hash(contrasena)


def es_hash(valor):
    """¿Este valor ya está cifrado, o es una contraseña en claro heredada?"""
    return bool(valor) and str(valor).startswith(PREFIJO)


def verificar(contrasena, guardado):
    """
    Comprueba una contraseña contra lo guardado.

    Acepta también las bases anteriores a la migración 006, donde el valor
    guardado es la contraseña en claro. Devuelve `(correcta, hay_que_recifrar)`:
    lo segundo avisa de que conviene guardar el hash en cuanto se pueda.
    """
    if not guardado:
        return False, False

    if not es_hash(guardado):
        # Base antigua sin migrar: se compara en claro y se pide recifrado.
        return contrasena == guardado, contrasena == guardado

    try:
        _hasher.verify(guardado, contrasena)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False

    # Si los parámetros recomendados han cambiado desde que se guardó,
    # argon2 lo dice y se vuelve a cifrar con los nuevos.
    return True, _hasher.check_needs_rehash(guardado)
