"""
La caja fuerte: la base de datos cifrada en el disco.

Cuando BillEase está cerrado, en el disco solo hay un fichero cifrado del que
no se puede sacar ni un NIF sin la contraseña. Cuando está abierto, la base
vive **en memoria**: nunca se escribe una copia en claro, ni siquiera
temporal, porque un fichero temporal en claro es justo lo que iríamos a
buscar si quisiéramos robar los datos.

    disco                        memoria
    ─────                        ───────
    billease.db  (cifrado)  ←→   SQLite en RAM
         ▲                            │
         └── se reescribe entero ─────┘
             en cada `commit()`

Reescribir el fichero entero en cada `commit()` parece bruto, y lo es: con mil
facturas son poco más de dos megas y unos milisegundos de AES. A cambio, no
hay forma de perder una factura por un corte de luz, que es lo que importa.

El fichero se escribe aparte y se mueve encima del bueno de un golpe
(`os.replace`), así que un apagón a mitad deja la caja anterior intacta: nunca
hay un estado «a medio escribir».

Nota: después de cifrar, `billease.db` **ya no es un fichero SQLite**. Es la
caja. Abrirlo con un visor de bases de datos no enseña nada, que es
exactamente lo que se busca.
"""

import os
import sqlite3
from pathlib import Path

from core.cifrado import (  # noqa: F401  (se reexportan para quien use la caja)
    CajaCorrupta,
    ClaveIncorrecta,
    ErrorDeCifrado,
    FormatoDesconocido,
    cambiar_contrasena as _recambiar,
    desempaquetar,
    empaquetar,
    es_caja as _es_caja_crudo,
    nueva_cabecera,
    nuevo_codigo,
)

SUFIJO_TEMPORAL = ".escribiendo"


def es_caja(ruta):
    """¿El fichero de esta ruta está cifrado?"""
    return _es_caja_crudo(Path(ruta))


# ─────────────────────────── abrir y guardar ───────────────────────────


class ConexionDeCaja(sqlite3.Connection):
    """
    Una conexión en memoria que se guarda cifrada en cada `commit()`.

    El resto del programa no se entera: los repositorios siguen haciendo
    `INSERT` y `commit()` como siempre. Quien decide cuándo tocar el disco es
    esta clase, y no cada pantalla.
    """

    caja = None          # ruta del fichero cifrado
    clave = None         # la clave de datos, solo en memoria
    cabecera = None

    def commit(self):
        super().commit()
        self.persistir()

    def persistir(self):
        """Vuelca la base entera al fichero cifrado."""
        if not (self.caja and self.clave):
            return False
        escribir(self.caja, self.serialize(), self.clave, self.cabecera)
        return True


def escribir(ruta, datos, clave, cabecera):
    """
    Escribe la caja de forma atómica.

    Primero en un fichero aparte y después un `os.replace`, que en todos los
    sistemas operativos es atómico: o está la caja nueva o está la vieja,
    nunca media.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + SUFIJO_TEMPORAL)

    paquete = empaquetar(datos, clave, cabecera)
    with open(temporal, "wb") as fichero:
        fichero.write(paquete)
        fichero.flush()
        os.fsync(fichero.fileno())      # que esté en el disco, no en el camino
    os.replace(temporal, ruta)
    return ruta


CABECERA_SQLITE = b"SQLite format 3\x00"
VERSION_WAL = 2
VERSION_NORMAL = 1


def sin_wal(imagen):
    """
    Le quita a una imagen la marca de «base en modo WAL».

    Una base en WAL lo lleva escrito en dos bytes de su cabecera (el 18 y el
    19), y SQLite, al abrirla, busca el fichero `-wal` que debería
    acompañarla. Dentro de la caja no hay ficheros que valgan: sin esto, la
    primera consulta falla con «unable to open database file».

    Le pasa a cualquier base que venga de una instalación anterior, porque
    todas iban en WAL. El PRAGMA no sirve aquí: en memoria devuelve «memory»
    y no toca la cabecera que se copió.
    """
    if len(imagen) < 20 or not imagen.startswith(CABECERA_SQLITE):
        return imagen
    if imagen[18] != VERSION_WAL and imagen[19] != VERSION_WAL:
        return imagen
    datos = bytearray(imagen)
    datos[18] = datos[19] = VERSION_NORMAL
    return bytes(datos)


def _conectar(imagen, ruta, clave, cabecera):
    """Monta una conexión en memoria a partir de la imagen descifrada."""
    conn = sqlite3.connect(":memory:", factory=ConexionDeCaja)
    if imagen:
        conn.deserialize(sin_wal(imagen))
    conn.caja = Path(ruta)
    conn.clave = clave
    conn.cabecera = cabecera
    return conn


def abrir(ruta, contrasena=None, codigo=None):
    """
    Abre la caja y devuelve una conexión en memoria.

    Lanza `ClaveIncorrecta` si la contraseña no vale y `CajaCorrupta` si el
    fichero está dañado o lo ha tocado alguien.
    """
    crudo = Path(ruta).read_bytes()
    imagen, clave, cabecera = desempaquetar(crudo, contrasena=contrasena, codigo=codigo)
    return _conectar(imagen, ruta, clave, cabecera)


def crear(ruta, contrasena):
    """
    Crea una caja vacía y devuelve `(conexión, código de recuperación)`.

    El código se devuelve **una sola vez**: en el fichero solo queda la clave
    envuelta con él, no el código. Si el usuario no lo apunta, no hay segunda
    oportunidad, y eso hay que decírselo en la pantalla.
    """
    cabecera, clave, codigo = nueva_cabecera(contrasena)
    conn = _conectar(b"", ruta, clave, cabecera)
    # Una base recién creada no tiene ni una página, y SQLite no sabe
    # serializar lo que todavía no existe. Con esto se materializa la cabecera
    # del fichero y ya hay algo que guardar.
    conn.execute("PRAGMA user_version = 1")
    conn.persistir()
    return conn, codigo


def cerrar(conn):
    """Guarda y cierra."""
    if isinstance(conn, ConexionDeCaja):
        conn.persistir()
    conn.close()


# ─────────────────────── pasar de claro a cifrado ───────────────────────


def cifrar(origen, contrasena, destino=None):
    """
    Convierte una base en claro en una caja cifrada.

    Devuelve `(ruta, código de recuperación)`. El original **no se borra
    aquí**: eso lo decide quien llama, después de comprobar que la caja nueva
    se abre. Perder la base al cifrarla sería el peor final posible para una
    función que existe para proteger datos.
    """
    origen = Path(origen)
    if es_caja(origen):
        raise ErrorDeCifrado("esa base ya está cifrada")

    # Se lee con la API de copia de SQLite y no leyendo el fichero: la base
    # va en modo WAL, así que el `.db` a secas puede no tener lo último.
    from data.connection import uri_solo_lectura

    entrada = sqlite3.connect(uri_solo_lectura(origen), uri=True)
    memoria = sqlite3.connect(":memory:")
    try:
        entrada.backup(memoria)
        imagen = sin_wal(memoria.serialize())   # en la caja no hay `-wal`
    finally:
        memoria.close()
        entrada.close()

    cabecera, clave, codigo = nueva_cabecera(contrasena)
    ruta = escribir(destino or origen, imagen, clave, cabecera)

    # El `-wal` y el `-shm` de la base en claro ya no pintan nada, y dejarlos
    # ahí despista: parecen parte de una base que ya no existe.
    if Path(destino or origen) == Path(origen):
        for sobrante in ("-wal", "-shm"):
            Path(str(origen) + sobrante).unlink(missing_ok=True)
    return ruta, codigo


def descifrar(origen, contrasena, destino, codigo=None):
    """
    Saca una copia **en claro** de la caja, a la ruta que se diga.

    Existe a propósito: los datos son del usuario y tiene que poder llevárselos
    a otro programa o mirarlos con un visor de SQLite. Lo que no se puede es
    hacerlo sin la contraseña.
    """
    conn = abrir(origen, contrasena=contrasena, codigo=codigo)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        salida = sqlite3.connect(destino)
        try:
            conn.backup(salida)
        finally:
            salida.close()
    finally:
        conn.close()
    return destino


def recifrar(conn, nueva):
    """
    Cambia la contraseña **de la conexión abierta** y guarda.

    Es la forma correcta de hacerlo con el programa en marcha. Cambiarla
    tocando el fichero mientras hay una conexión viva no sirve: esa conexión
    guarda su propia cabecera y, al cerrarse, volvería a escribir la de antes
    —dejando otra vez la contraseña vieja—.
    """
    if not isinstance(conn, ConexionDeCaja) or not conn.clave:
        return False
    conn.cabecera = _recambiar(conn.cabecera, nueva, conn.clave)
    conn.persistir()
    return True


def cambiar_contrasena(ruta, actual, nueva, codigo=None):
    """
    Cambia la contraseña sin tocar los datos.

    Se vuelve a envolver la misma clave, así que es instantáneo aunque la base
    pese cien megas. El código de recuperación **no cambia**: por eso sigue
    abriendo las copias de seguridad hechas con la contraseña anterior.

    Esta versión trabaja sobre el fichero y es la que vale cuando no hay nada
    abierto —al recuperar el acceso, por ejemplo—. Con el programa en marcha,
    `recifrar()`.
    """
    crudo = Path(ruta).read_bytes()
    imagen, clave, cabecera = desempaquetar(crudo, contrasena=actual, codigo=codigo)
    escribir(ruta, imagen, clave, _recambiar(cabecera, nueva, clave))
    return ruta


def información(ruta):
    """Lo que se puede saber de una caja sin abrirla: cuándo se creó y se tocó."""
    from core.cifrado import leer_cabecera

    cabecera, _, _ = leer_cabecera(Path(ruta).read_bytes())
    return {
        "version": cabecera.get("version"),
        "cifrado": cabecera.get("cifrado"),
        "creada": cabecera.get("creada"),
        "modificada": cabecera.get("modificada"),
        "recuperable": bool(cabecera.get("recuperacion")),
    }
