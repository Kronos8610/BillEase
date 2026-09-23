"""
Reglas de arquitectura, comprobadas automáticamente.

La auditoría encontró que la interfaz escribía SQL, abría tuplas por posición
y que el generador de PDF arrastraba Qt entero. Esas reglas se pueden
enunciar, pero si no se comprueban vuelven solas en el primer arreglo con
prisa. Aquí se comprueban.
"""

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PAQUETES = ("core", "data", "documents", "ui", "tools")


def modulos(paquete):
    return sorted(p for p in (RAIZ / paquete).rglob("*.py") if "__pycache__" not in p.parts)


def importa(ruta, prefijos):
    """Módulos de nivel superior que importa un fichero, filtrados por prefijo."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    encontrados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            nombres = [nodo.module or ""]
        else:
            continue
        for nombre in nombres:
            raiz = nombre.split(".")[0]
            if raiz in prefijos:
                encontrados.add(nombre)
    return encontrados


# ─────────────────────── dónde puede haber SQL ───────────────────────


def test_solo_la_capa_de_datos_habla_con_sqlite():
    """
    `sqlite3` únicamente en `data/`.

    Antes, `database/db.py` abría conexiones desde cualquier sitio y la
    interfaz llamaba a funciones que escribían SQL a mano.
    """
    culpables = []
    for paquete in ("core", "documents", "ui"):
        for ruta in modulos(paquete):
            if importa(ruta, {"sqlite3"}):
                culpables.append(str(ruta.relative_to(RAIZ)))
    assert culpables == [], f"estos módulos importan sqlite3 fuera de data/: {culpables}"


def test_el_modulo_database_ya_no_existe():
    assert not (RAIZ / "database").exists()
    assert not (RAIZ / "validators").exists()


# ─────────────────────── dónde puede haber Qt ───────────────────────


def test_el_nucleo_no_sabe_que_existe_qt():
    """`core/` tiene que poder probarse sin pantalla."""
    culpables = [
        str(r.relative_to(RAIZ)) for r in modulos("core") if importa(r, {"PyQt6"})
    ]
    assert culpables == [], f"el núcleo importa Qt en: {culpables}"


def test_el_generador_de_documentos_no_sabe_que_existe_qt():
    """Una factura se tiene que poder generar en un servidor sin pantalla."""
    culpables = [
        str(r.relative_to(RAIZ)) for r in modulos("documents")
        if importa(r, {"PyQt6", "sqlite3"})
    ]
    assert culpables == [], f"el generador arrastra Qt o SQL en: {culpables}"


def test_el_nucleo_no_depende_de_la_capa_de_datos():
    """La dependencia va en un sentido: data conoce core, core no conoce data."""
    culpables = [
        str(r.relative_to(RAIZ)) for r in modulos("core") if importa(r, {"data"})
    ]
    assert culpables == [], f"el núcleo depende de data en: {culpables}"


# ─────────────────────── tuplas por posición ───────────────────────

# Nombres que en la interfaz representan datos venidos de la base. Abrirlos
# por posición es lo que hacía que añadir una columna rompiera pantallas
# lejanas: `cliente[2]` era el nombre y `cliente[6]` el NIF.
NOMBRES_DE_DATOS = (
    "cliente", "clientes", "factura", "facturas", "servicio", "servicios",
    "autonomo", "det", "detalle", "detalles", "fila", "filas", "linea", "lineas",
    "sdata", "cliente_datos", "servicio_data",
)
ACCESO_POR_INDICE = re.compile(
    r"\b(" + "|".join(NOMBRES_DE_DATOS) + r")\s*\[\s*-?\d+\s*\]"
)


def test_ninguna_pantalla_abre_los_datos_por_posicion():
    culpables = []
    for ruta in modulos("ui"):
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if ACCESO_POR_INDICE.search(linea):
                culpables.append(f"{ruta.relative_to(RAIZ)}:{numero}: {linea.strip()}")
    assert culpables == [], "acceso por índice numérico:\n" + "\n".join(culpables)


@pytest.mark.parametrize("paquete", PAQUETES)
def test_todos_los_modulos_compilan(paquete):
    for ruta in modulos(paquete):
        ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
