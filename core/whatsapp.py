"""
El enlace al chat de WhatsApp de uno mismo.

WhatsApp no deja que un programa mande un fichero: no hay forma gratuita ni
oficial de hacerlo desde el escritorio. Lo que sí hay es `wa.me/<número>`,
que abre el chat con ese número —y con el propio abre «Mensaje a ti mismo»—
con un texto ya escrito. El PDF lo adjunta el usuario pegándolo, y de dejarlo
copiado se encarga la interfaz.
"""

import re
from urllib.parse import quote

PREFIJO_ESPANA = "34"


def numero_internacional(telefono):
    """
    El teléfono como lo quiere `wa.me`: solo cifras, con prefijo de país.

    Un móvil español de nueve cifras recibe el 34 delante. Uno que ya venga
    con `+` o `00` se respeta. Devuelve cadena vacía si no hay por dónde.
    """
    crudo = str(telefono or "").strip()
    cifras = re.sub(r"\D", "", crudo)
    if not cifras:
        return ""
    if crudo.startswith("+"):
        return cifras
    if cifras.startswith("00"):
        return cifras[2:]
    if len(cifras) == 9:
        return PREFIJO_ESPANA + cifras
    return cifras


def enlace(telefono, texto=""):
    """La dirección que abre el chat, o cadena vacía si no hay teléfono."""
    numero = numero_internacional(telefono)
    if not numero:
        return ""
    cola = f"?text={quote(texto)}" if texto else ""
    return f"https://wa.me/{numero}{cola}"
