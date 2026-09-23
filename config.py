"""
Dónde vive la base de datos.

Hasta ahora la ruta era la cadena `"BillEase.db"` repetida en veintidós
funciones, relativa al directorio de trabajo: ejecutar la aplicación desde
otra carpeta creaba una base nueva y vacía sin avisar de nada, y los datos
«desaparecían».

Ahora la base vive junto a los datos del usuario, como cualquier programa de
escritorio:

    Windows   %LOCALAPPDATA%\\BillEase\\billease.db
    macOS     ~/Library/Application Support/BillEase/billease.db
    Linux     ~/.local/share/BillEase/billease.db

La variable de entorno `BILLEASE_DB` manda sobre todo lo demás. Las
herramientas de `tools/` y las pruebas la usan para trabajar sobre una copia
sin tocar la base real.
"""

import os
import shutil
import sys
from pathlib import Path

NOMBRE_APP = "BillEase"
NOMBRE_FICHERO = "billease.db"

# Nombre y ubicación que tenía la base antes de la fase 2.
NOMBRE_ANTIGUO = "BillEase.db"


def directorio_datos():
    """Carpeta de datos del usuario para esta aplicación."""
    if sys.platform == "win32":
        raiz = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        raiz = Path.home() / "Library" / "Application Support"
    else:
        raiz = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(raiz) / NOMBRE_APP


def ruta_base_datos():
    """
    Ruta del fichero de base de datos que debe usar la aplicación.

    No crea nada ni mueve nada: solo responde dónde mirar.
    """
    override = os.environ.get("BILLEASE_DB")
    if override:
        return Path(override)
    return directorio_datos() / NOMBRE_FICHERO


def recuperar_base_antigua(origen=None, destino=None):
    """
    Trae a su sitio la base que quedó junto al código.

    Se ejecuta al arrancar. Si el usuario ya venía usando BillEase, su
    `BillEase.db` está en la carpeta del programa: se copia a la carpeta de
    datos y la original se renombra —nunca se borra— para que no se siga
    usando por error.

    Devuelve la ruta de destino si ha movido algo, o None si no había nada
    que mover. Con `BILLEASE_DB` definida no hace nada: manda la variable.
    """
    if os.environ.get("BILLEASE_DB"):
        return None

    origen = Path(origen) if origen else Path.cwd() / NOMBRE_ANTIGUO
    destino = Path(destino) if destino else ruta_base_datos()

    if not origen.exists() or destino.exists():
        return None

    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    origen.rename(origen.with_suffix(origen.suffix + ".movida"))
    return destino


def asegurar_directorio(ruta=None):
    """Crea la carpeta de la base si hace falta y devuelve la ruta."""
    ruta = Path(ruta) if ruta else ruta_base_datos()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta
