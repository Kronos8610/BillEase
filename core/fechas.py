"""
Conversión entre la fecha que se guarda y la que se enseña.

En la base se guarda ISO-8601 («2025-01-15»), que ordena solo y se puede
filtrar con un BETWEEN para sacar un trimestre. En pantalla y en el papel se
enseña el formato español («15/01/2025»), que es el que el usuario escribe.

Antes se guardaba directamente lo que el usuario tecleara, así que ordenar
por fecha ordenaba alfabéticamente (defecto 08).
"""

from datetime import date

FORMATO_ESPANOL = "%d/%m/%Y"


def a_iso(texto):
    """
    «15/01/2025» → «2025-01-15». Lo que ya viene en ISO se deja igual.

    Si la fecha no se entiende se devuelve tal cual: es preferible conservar
    lo que escribió el usuario, aunque sea raro, a perderlo.
    """
    if not texto:
        return texto
    texto = str(texto).strip()
    if len(texto) == 10 and texto[4] == "-" and texto[7] == "-":
        return texto
    for separador in ("/", "-", "."):
        partes = texto.split(separador)
        if len(partes) == 3 and len(partes[0]) <= 2:
            dia, mes, anio = (p.strip() for p in partes)
            if dia.isdigit() and mes.isdigit() and anio.isdigit() and len(anio) == 4:
                return f"{anio}-{int(mes):02d}-{int(dia):02d}"
    return texto


def a_espanol(iso):
    """«2025-01-15» → «15/01/2025». Lo que no sea ISO se devuelve igual."""
    if not iso:
        return ""
    texto = str(iso).strip()
    partes = texto.split("-")
    if len(partes) == 3 and len(partes[0]) == 4:
        anio, mes, dia = partes
        if anio.isdigit() and mes.isdigit() and dia[:2].isdigit():
            return f"{int(dia[:2]):02d}/{int(mes):02d}/{anio}"
    return texto


def hoy_iso():
    return date.today().isoformat()


def ejercicio_de(iso):
    """Año fiscal de una fecha ISO; 0 si no se puede saber."""
    texto = str(iso or "")[:4]
    return int(texto) if texto.isdigit() else 0
