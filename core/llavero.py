"""
Dónde se guarda la contraseña del correo: en el llavero del sistema.

La contraseña de aplicación de Gmail deja mandar correo en nombre del
usuario, así que no va en la base de datos: si la base no está cifrada, la
leería cualquiera con un visor de SQLite. Va en el Administrador de
credenciales de Windows —o el llavero de macOS, o el de Linux—, que es donde
el sistema guarda las contraseñas y que solo abre la sesión del usuario.

Este módulo es lo único que sabe de `keyring`. Si no hay llavero —un Linux
sin escritorio, por ejemplo—, lo dice con `LlaveroNoDisponible` en vez de
guardar la contraseña en otro sitio peor sin avisar.
"""

SERVICIO = "BillEase · correo"


class LlaveroNoDisponible(Exception):
    """Este sistema no tiene dónde guardar una contraseña con garantías."""


def _llavero():
    try:
        import keyring
        from keyring.backends.fail import Keyring as SinLlavero
    except ImportError as e:
        raise LlaveroNoDisponible("Falta el módulo «keyring».") from e
    if isinstance(keyring.get_keyring(), SinLlavero):
        raise LlaveroNoDisponible(
            "Este sistema no tiene un llavero donde guardar la contraseña."
        )
    return keyring


def guardar(cuenta, clave):
    """Guarda la contraseña de esa cuenta. Sustituye la que hubiera."""
    try:
        _llavero().set_password(SERVICIO, cuenta, clave)
    except LlaveroNoDisponible:
        raise
    except Exception as e:                                      # noqa: BLE001
        raise LlaveroNoDisponible(f"El llavero no ha querido guardarla: {e}") from e


def leer(cuenta):
    """La contraseña guardada para esa cuenta, o cadena vacía si no hay."""
    try:
        return _llavero().get_password(SERVICIO, cuenta) or ""
    except LlaveroNoDisponible:
        return ""
    except Exception:                                           # noqa: BLE001
        return ""


def borrar(cuenta):
    """Olvida la contraseña de esa cuenta. Si no había, no pasa nada."""
    try:
        _llavero().delete_password(SERVICIO, cuenta)
    except Exception:                                           # noqa: BLE001
        pass
