"""
Copias de seguridad de la base de datos.

Una base de datos de facturación de un autónomo es irreemplazable: no hay otro
sitio de donde sacar lo que se emitió en marzo. Hasta ahora la única copia que
existía era la que dejaba la migración, y solo al migrar.

Se copia con la API de copia de SQLite —`Connection.backup()`— y no con
`shutil.copy`: la base está en modo WAL, así que el fichero `.db` por sí solo
puede no contener las últimas escrituras. La API hace una copia coherente
aunque la aplicación esté funcionando.

Las copias viven junto a la base, en `copias/`, con la fecha en el nombre:

    billease-2026-10-14_0932.db

Se guardan las últimas y las demás se van borrando, para que la carpeta no
crezca sin fin.
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from config import ruta_base_datos

CARPETA = "copias"
PATRON = "billease-*.db"
FORMATO = "%Y-%m-%d_%H%M%S"
CUANTAS_SE_GUARDAN = 10

_FECHA_EN_NOMBRE = re.compile(r"billease-(\d{4}-\d{2}-\d{2}_\d{6})\.db$")


def directorio(base=None):
    """Dónde viven las copias de una base."""
    origen = Path(base) if base else ruta_base_datos()
    return origen.parent / CARPETA


def copiar(base=None, destino=None, cuantas_se_guardan=CUANTAS_SE_GUARDAN):
    """
    Hace una copia coherente y devuelve su ruta.

    Si la base no existe todavía no hay nada que copiar y devuelve None: es lo
    que pasa la primera vez que se abre el programa.
    """
    origen = Path(base) if base else ruta_base_datos()
    if not origen.exists():
        return None

    if destino is None:
        carpeta = directorio(origen)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"billease-{datetime.now().strftime(FORMATO)}.db"
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    entrada = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    salida = sqlite3.connect(destino)
    try:
        entrada.backup(salida)       # copia coherente, aunque haya WAL
    finally:
        salida.close()
        entrada.close()

    if cuantas_se_guardan:
        limpiar(origen, cuantas_se_guardan)
    return destino


def copias(base=None):
    """Las copias que hay, de la más reciente a la más antigua."""
    carpeta = directorio(base)
    if not carpeta.exists():
        return []
    return sorted(carpeta.glob(PATRON), key=lambda p: p.name, reverse=True)


def fecha_de(copia):
    """Cuándo se hizo una copia, leído de su nombre."""
    encontrado = _FECHA_EN_NOMBRE.search(Path(copia).name)
    if not encontrado:
        return None
    try:
        return datetime.strptime(encontrado.group(1), FORMATO)
    except ValueError:
        return None


def limpiar(base=None, cuantas_se_guardan=CUANTAS_SE_GUARDAN):
    """Deja solo las últimas. Devuelve las que ha borrado."""
    sobran = copias(base)[cuantas_se_guardan:]
    for vieja in sobran:
        vieja.unlink(missing_ok=True)
    return sobran


def restaurar(copia, base=None):
    """
    Devuelve una copia a su sitio.

    Antes de pisar nada se guarda lo que hay ahora —con `-antes-de-restaurar`
    en el nombre—, porque restaurar la copia equivocada no puede ser un camino
    de ida. La conexión abierta se cierra primero: en Windows no se puede
    sobrescribir un fichero que está en uso.
    """
    copia = Path(copia)
    if not copia.exists():
        raise FileNotFoundError(f"No existe la copia {copia}")

    destino = Path(base) if base else ruta_base_datos()
    from data.connection import cerrar

    cerrar()

    anterior = None
    if destino.exists():
        marca = datetime.now().strftime(FORMATO)
        anterior = directorio(destino) / f"billease-{marca}-antes-de-restaurar.db"
        anterior.parent.mkdir(parents=True, exist_ok=True)
        copiar(destino, anterior, cuantas_se_guardan=0)

    destino.parent.mkdir(parents=True, exist_ok=True)
    entrada = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    salida = sqlite3.connect(destino)
    try:
        entrada.backup(salida)
    finally:
        salida.close()
        entrada.close()

    # Los ficheros del WAL de la base vieja ya no valen para la nueva.
    for extra in (destino.with_suffix(destino.suffix + "-wal"),
                  destino.with_suffix(destino.suffix + "-shm")):
        extra.unlink(missing_ok=True)

    return {"restaurada": destino, "copia_previa": anterior}
