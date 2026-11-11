"""
Mandarse un PDF por correo.

El programa no manda nada a los clientes: le manda el documento al propio
autónomo, a su Gmail, para tenerlo en el móvil o reenviarlo desde ahí. Se
entra en Gmail con una **contraseña de aplicación** —no con la contraseña de
la cuenta—, que Google da en «Verificación en dos pasos → Contraseñas de
aplicaciones» y que se puede anular cuando se quiera sin tocar la cuenta.

Este módulo no sabe de Qt ni de la base: recibe los bytes del PDF y una
cuenta, y devuelve o lanza. El servidor se puede cambiar por uno de mentira
para probarlo sin red.
"""

import re
import smtplib
import ssl
from email.message import EmailMessage

SERVIDOR = "smtp.gmail.com"
PUERTO = 465
ESPERA = 25          # segundos; sin tope, una red caída congela la ventana


class ErrorDeCorreo(Exception):
    """El correo no ha salido. El mensaje se puede enseñar tal cual."""


def limpiar_clave(clave):
    """
    Google enseña la contraseña de aplicación en cuatro grupos con espacios
    —«abcd efgh ijkl mnop»— y la gente la pega así. Los espacios sobran.
    """
    return re.sub(r"\s+", "", clave or "")


def montar(cuenta, pdf, nombre, asunto, cuerpo, adjuntar=True):
    """El mensaje, de la cuenta a sí misma, con el PDF adjunto."""
    mensaje = EmailMessage()
    mensaje["From"] = cuenta
    mensaje["To"] = cuenta
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    if adjuntar:
        mensaje.add_attachment(
            pdf, maintype="application", subtype="pdf", filename=nombre
        )
    return mensaje


def enviar(cuenta, clave, pdf, nombre, asunto, cuerpo, conectar=None, adjuntar=True):
    """
    Manda el PDF a la propia cuenta. Lanza `ErrorDeCorreo` si no sale.

    `conectar` es para las pruebas: algo que se use como
    `smtplib.SMTP_SSL(servidor, puerto, ...)`. `adjuntar=False` manda solo el
    texto, que es lo que hace el correo de prueba de Ajustes.
    """
    cuenta = (cuenta or "").strip()
    clave = limpiar_clave(clave)
    if not cuenta or not clave:
        raise ErrorDeCorreo(
            "Falta la cuenta de Gmail o su contraseña de aplicación. "
            "Ponlas en Ajustes."
        )

    mensaje = montar(cuenta, pdf, nombre, asunto, cuerpo, adjuntar)
    conectar = conectar or (
        lambda: smtplib.SMTP_SSL(
            SERVIDOR, PUERTO, timeout=ESPERA, context=ssl.create_default_context()
        )
    )
    try:
        with conectar() as servidor:
            servidor.login(cuenta, clave)
            servidor.send_message(mensaje)
    except smtplib.SMTPAuthenticationError as e:
        raise ErrorDeCorreo(
            "Gmail no ha aceptado la contraseña. Tiene que ser una contraseña "
            "de aplicación —16 letras—, no la de tu cuenta, y la cuenta tiene "
            "que tener la verificación en dos pasos activada."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise ErrorDeCorreo(
            f"No se ha podido conectar con Gmail. ¿Hay internet?\n\nMotivo: {e}"
        ) from e
    return mensaje
