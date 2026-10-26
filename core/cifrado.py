"""
El cifrado de la caja fuerte: Argon2id para la clave y AES-256-GCM para los datos.

Qué protege y qué no, dicho claro desde el principio:

- **Protege** el fichero de datos. Quien se lleve el portátil, copie la base a
  un USB o la rescate de un disco viejo, se encuentra con ruido: sin la
  contraseña no hay forma de leer ni un NIF.
- **No protege** de un programa malicioso que corra con tu sesión mientras
  BillEase está abierto. En ese momento los datos están descifrados en memoria
  porque los estás usando. Contra eso valen el antivirus y el sentido común,
  no la criptografía.

Cómo funciona, en tres ideas:

1. Los datos se cifran con una **clave aleatoria de 256 bits** (la clave de
   datos), no con la contraseña. La contraseña solo sirve para envolver esa
   clave.
2. Por eso **cambiar la contraseña es instantáneo**: se vuelve a envolver la
   misma clave de datos; no hay que descifrar y volver a cifrar nada.
3. La clave de datos está envuelta **dos veces**: con la contraseña y con un
   **código de recuperación** que se enseña una sola vez. Sin ese código, una
   contraseña olvidada sería la pérdida total de la facturación, y eso no es
   una opción aceptable en un programa de facturas.

`cryptography` y `argon2-cffi` son las dos bibliotecas estándar para esto y
tienen ruedas para Windows. SQLCipher, que sería la alternativa, no: no
publica ruedas para Windows en ninguna versión, y pedirle a un autónomo que
compile una biblioteca en C para poder facturar no es una solución.
"""

import base64
import json
import os
import secrets
from datetime import datetime, timezone

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIA = b"BILLEASE-CAJA\x00"
VERSION = 1

# Parámetros de Argon2id. 64 MiB y tres pasadas tardan unas décimas de segundo
# al abrir —que es una vez— y encarecen enormemente probar contraseñas a lo
# bruto, que es de lo que se trata.
MEMORIA = 64 * 1024          # KiB
TIEMPO = 3
PARALELISMO = 4
LONGITUD_CLAVE = 32          # AES-256
LONGITUD_SAL = 16
LONGITUD_NONCE = 12

# El código de recuperación: 20 bytes al azar en base32, que son 32 caracteres
# sin ceros ni unos que confundan, repartidos en grupos de cuatro.
BYTES_CODIGO = 20
GRUPO = 4
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
# Lo que la gente escribe cuando copia a mano un código que no tiene 0 ni 1.
CONFUSIONES = {"0": "O", "1": "I", "8": "B", "9": "G", " ": "", "-": ""}


class ErrorDeCifrado(Exception):
    """Algo va mal con la caja. Las de abajo dicen qué."""


class ClaveIncorrecta(ErrorDeCifrado):
    """La contraseña o el código no abren esta caja."""


class CajaCorrupta(ErrorDeCifrado):
    """El fichero está dañado o lo ha tocado alguien."""


class FormatoDesconocido(ErrorDeCifrado):
    """Esto no es una caja de BillEase."""


# ─────────────────────────── claves y códigos ───────────────────────────


def nueva_clave():
    """Una clave de datos nueva: 256 bits de azar de verdad."""
    return secrets.token_bytes(LONGITUD_CLAVE)


def nuevo_codigo():
    """
    Un código de recuperación legible, para apuntarlo en un papel.

    Sale así: `A3F7-K92M-…`, ocho grupos de cuatro.
    """
    crudo = base64.b32encode(secrets.token_bytes(BYTES_CODIGO)).decode().rstrip("=")
    return "-".join(crudo[i:i + GRUPO] for i in range(0, len(crudo), GRUPO))


def normalizar_codigo(texto):
    """
    Admite el código como lo escriba el usuario.

    Con guiones o sin ellos, en minúsculas, y con los cambios que todo el
    mundo hace al copiar a mano: un cero por una O, un uno por una I.
    """
    limpio = str(texto or "").strip().upper()
    for malo, bueno in CONFUSIONES.items():
        limpio = limpio.replace(malo, bueno)
    return "".join(c for c in limpio if c in ALFABETO)


def derivar(secreto, sal):
    """De una contraseña (o un código) a una clave de 256 bits, con Argon2id."""
    if isinstance(secreto, str):
        secreto = secreto.encode("utf-8")
    return hash_secret_raw(
        secret=secreto,
        salt=sal,
        time_cost=TIEMPO,
        memory_cost=MEMORIA,
        parallelism=PARALELISMO,
        hash_len=LONGITUD_CLAVE,
        type=Type.ID,
    )


# ─────────────────────────── envolver la clave ───────────────────────────


def _b64(crudo):
    return base64.b64encode(crudo).decode("ascii")


def _de_b64(texto):
    try:
        return base64.b64decode(texto.encode("ascii"))
    except Exception as e:      # noqa: BLE001
        raise CajaCorrupta(f"la cabecera no se entiende: {e}") from e


def envolver(clave_datos, secreto):
    """
    Guarda la clave de datos bajo llave, con la contraseña o con el código.

    Devuelve el trozo de cabecera que hay que escribir en el fichero: la sal,
    el nonce y la clave envuelta.
    """
    sal = secrets.token_bytes(LONGITUD_SAL)
    nonce = secrets.token_bytes(LONGITUD_NONCE)
    envuelta = AESGCM(derivar(secreto, sal)).encrypt(nonce, clave_datos, None)
    return {"sal": _b64(sal), "nonce": _b64(nonce), "clave": _b64(envuelta)}


def desenvolver(trozo, secreto):
    """Saca la clave de datos. Lanza `ClaveIncorrecta` si el secreto no vale."""
    if not trozo:
        raise ClaveIncorrecta("esta caja no admite esa forma de abrirse")
    try:
        clave = derivar(secreto, _de_b64(trozo["sal"]))
        return AESGCM(clave).decrypt(_de_b64(trozo["nonce"]), _de_b64(trozo["clave"]), None)
    except InvalidTag as e:
        raise ClaveIncorrecta("la contraseña o el código no son correctos") from e
    except KeyError as e:
        raise CajaCorrupta(f"falta {e} en la cabecera") from e


# ─────────────────────────── el fichero entero ───────────────────────────


def nueva_cabecera(contrasena, codigo=None):
    """
    Monta la cabecera de una caja nueva y devuelve `(cabecera, clave, código)`.

    El código de recuperación se devuelve **una sola vez**: no se guarda en
    ninguna parte legible, solo la clave envuelta con él.
    """
    codigo = codigo or nuevo_codigo()
    clave = nueva_clave()
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cabecera = {
        "version": VERSION,
        "kdf": {
            "algoritmo": "argon2id",
            "memoria": MEMORIA,
            "tiempo": TIEMPO,
            "paralelismo": PARALELISMO,
        },
        "cifrado": "aes-256-gcm",
        "contrasena": envolver(clave, contrasena),
        "recuperacion": envolver(clave, normalizar_codigo(codigo)),
        "creada": ahora,
        "modificada": ahora,
    }
    return cabecera, clave, codigo


def abrir_cabecera(cabecera, contrasena=None, codigo=None):
    """La clave de datos, a partir de la contraseña o del código."""
    if contrasena is not None:
        return desenvolver(cabecera.get("contrasena"), contrasena)
    if codigo is not None:
        return desenvolver(cabecera.get("recuperacion"), normalizar_codigo(codigo))
    raise ClaveIncorrecta("hace falta la contraseña o el código de recuperación")


def cambiar_contrasena(cabecera, nueva, clave_datos):
    """
    Vuelve a envolver la misma clave de datos con otra contraseña.

    Los datos no se tocan: por eso cambiar la contraseña es instantáneo aunque
    la base pese cien megas. Y el código de recuperación sigue valiendo, lo que
    hace que **una copia de seguridad antigua se pueda abrir siempre** con él,
    aunque se hiciera con la contraseña de antes.
    """
    nueva_cab = dict(cabecera)
    nueva_cab["contrasena"] = envolver(clave_datos, nueva)
    nueva_cab["modificada"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return nueva_cab


def empaquetar(datos, clave, cabecera):
    """
    El fichero completo: magia, cabecera y datos cifrados.

    La cabecera viaja como datos autenticados del cifrado, así que cambiarle
    una coma invalida el contenido entero: nadie puede rebajar los parámetros
    de Argon2 ni colar otra clave envuelta sin que se note.
    """
    cabecera_cruda = json.dumps(cabecera, ensure_ascii=False, sort_keys=True).encode("utf-8")
    nonce = secrets.token_bytes(LONGITUD_NONCE)
    cuerpo = AESGCM(clave).encrypt(nonce, datos, cabecera_cruda)
    return (
        MAGIA
        + len(cabecera_cruda).to_bytes(4, "big")
        + cabecera_cruda
        + nonce
        + cuerpo
    )


def leer_cabecera(crudo):
    """La cabecera de un fichero, sin descifrar nada."""
    if not crudo.startswith(MAGIA):
        raise FormatoDesconocido("esto no es una caja de BillEase")
    inicio = len(MAGIA)
    try:
        largo = int.from_bytes(crudo[inicio:inicio + 4], "big")
        cabecera_cruda = crudo[inicio + 4:inicio + 4 + largo]
        cabecera = json.loads(cabecera_cruda.decode("utf-8"))
    except Exception as e:      # noqa: BLE001
        raise CajaCorrupta(f"la cabecera está dañada: {e}") from e
    if cabecera.get("version") != VERSION:
        raise FormatoDesconocido(
            f"caja de la versión {cabecera.get('version')}; este programa entiende la {VERSION}"
        )
    return cabecera, cabecera_cruda, inicio + 4 + largo


def desempaquetar(crudo, contrasena=None, codigo=None):
    """
    Abre un fichero entero y devuelve `(datos, clave, cabecera)`.

    Si alguien ha tocado un solo byte, AES-GCM lo detecta y esto falla con
    `CajaCorrupta` en lugar de devolver datos a medias.
    """
    cabecera, cabecera_cruda, donde = leer_cabecera(crudo)
    clave = abrir_cabecera(cabecera, contrasena=contrasena, codigo=codigo)

    nonce = crudo[donde:donde + LONGITUD_NONCE]
    cuerpo = crudo[donde + LONGITUD_NONCE:]
    if len(nonce) < LONGITUD_NONCE or not cuerpo:
        raise CajaCorrupta("el fichero está cortado")
    try:
        datos = AESGCM(clave).decrypt(nonce, cuerpo, cabecera_cruda)
    except InvalidTag as e:
        raise CajaCorrupta(
            "el contenido no cuadra con su firma: el fichero está dañado o lo han tocado"
        ) from e
    return datos, clave, cabecera


def es_caja(crudo_o_ruta):
    """¿Esto es una caja cifrada? Admite los primeros bytes o una ruta."""
    if isinstance(crudo_o_ruta, (bytes, bytearray)):
        return bytes(crudo_o_ruta).startswith(MAGIA)
    try:
        with open(crudo_o_ruta, "rb") as fichero:
            return fichero.read(len(MAGIA)) == MAGIA
    except OSError:
        return False
