"""
Validación de formularios.

Una regla es una función que dice si un valor vale, más el mensaje que hay que
enseñar cuando no. Los campos opcionales solo se comprueban si el usuario ha
escrito algo: antes, dejar el teléfono en blanco daba error de formato.
"""

from dataclasses import dataclass
from typing import Callable

from core.validators.contacto import (  # noqa: F401
    es_codigo_postal,
    es_contrasena,
    es_email,
    es_telefono,
    normalizar_cp,
    normalizar_telefono,
)
from core.validators.documento import (  # noqa: F401
    es_cif,
    es_documento_fiscal,
    es_nie,
    es_nif,
    es_nif_o_nie,
    normalizar as normalizar_documento,
)


@dataclass(frozen=True)
class Regla:
    """Cómo se comprueba un campo y qué se le dice al usuario si falla."""

    comprueba: Callable
    mensaje: str
    obligatorio: bool = True

    def evaluar(self, valor):
        """Devuelve el mensaje de error, o None si el valor está bien."""
        vacio = valor is None or str(valor).strip() == ""
        if vacio:
            return self.mensaje if self.obligatorio else None
        return None if self.comprueba(valor) else self.mensaje


def _siempre(_valor):
    return True


OBLIGATORIO = Regla(_siempre, "Este campo es obligatorio")
NIF_O_NIE = Regla(es_nif_o_nie, "NIF o NIE inválido: revisa la letra")
CIF = Regla(es_cif, "CIF inválido: revisa el dígito de control")
DOCUMENTO = Regla(es_documento_fiscal, "Documento fiscal inválido")
EMAIL = Regla(es_email, "Formato de correo electrónico inválido")
CONTRASENA = Regla(
    es_contrasena, "La contraseña necesita 8 caracteres, con una letra y un número"
)
TELEFONO = Regla(es_telefono, "Teléfono inválido: 9 cifras empezando por 6, 7, 8 o 9")
TELEFONO_OPCIONAL = Regla(es_telefono, TELEFONO.mensaje, obligatorio=False)
CODIGO_POSTAL = Regla(es_codigo_postal, "Código postal inválido: 5 cifras, de 01000 a 52999")
CODIGO_POSTAL_OPCIONAL = Regla(es_codigo_postal, CODIGO_POSTAL.mensaje, obligatorio=False)


def validar_formulario(datos, reglas):
    """
    Comprueba un diccionario de datos contra un diccionario de reglas.

    Devuelve `(todo_bien, errores)`, con `errores` indexado por campo.
    """
    errores = {}
    for campo, regla in reglas.items():
        error = regla.evaluar(datos.get(campo))
        if error:
            errores[campo] = error
    return not errores, errores
