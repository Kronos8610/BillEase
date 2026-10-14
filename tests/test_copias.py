"""
Pruebas de las copias de seguridad y de la exportación a CSV (fase 6).

Una copia que no se puede restaurar no es una copia. Aquí se restaura de
verdad y se comprueba que vuelven los datos, no que exista un fichero.
"""

import csv
import sqlite3

import pytest

from core.models import COBRADA, PRESUPUESTO, Cliente, Linea
from data import backup
from data.connection import abrir, cerrar
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo
from data.schema import crear_esquema_y_migrar
from documents.export_csv import (
    CODIFICACION,
    SEPARADOR,
    exportar_clientes,
    exportar_documentos,
    exportar_lineas,
    exportar_resumen,
    exportar_todo,
)


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Una base con un cliente, dos facturas y un presupuesto."""
    ruta = tmp_path / "billease.db"
    monkeypatch.setenv("BILLEASE_DB", str(ruta))
    cerrar()
    crear_esquema_y_migrar()
    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, codigo_postal="08020", telefono="654321098")
    )
    repo.crear("15/01/2026", cliente_id, [
        Linea("Armario a medida de dos módulos", cantidad=1, precio_ud=1240),
        Linea("Desmontaje del anterior", cantidad=2, precio_ud=97.5),
    ])
    repo.crear("20/02/2026", cliente_id, [Linea("Pintura", cantidad=15, precio_ud="12,50")])
    repo.crear("25/02/2026", cliente_id, [Linea("Obra ofertada", cantidad=1, precio_ud=800)],
               tipo=PRESUPUESTO, validez="2026-03-27")
    yield ruta
    cerrar()


# ─────────────────────── copias de seguridad ───────────────────────


def test_la_copia_tiene_los_mismos_datos(base):
    copia = backup.copiar(base)

    assert copia.exists()
    original = sqlite3.connect(base)
    guardada = sqlite3.connect(copia)
    try:
        for tabla in ("Autonomo", "Cliente", "Factura", "Detalle_linea"):
            assert (guardada.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()
                    == original.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone())
        assert (guardada.execute("SELECT SUM(base) FROM Factura").fetchone()[0]
                == original.execute("SELECT SUM(base) FROM Factura").fetchone()[0])
    finally:
        original.close()
        guardada.close()


def test_la_copia_recoge_lo_que_todavia_esta_en_el_wal(base):
    """
    Copiar el `.db` a pelo puede dejarse fuera lo último escrito.

    La base va en modo WAL: hasta que no se consolida, las escrituras viven en
    el fichero `-wal`. Por eso se copia con la API de SQLite y no con
    `shutil.copy`.
    """
    cliente = repo_clientes.listar()[0]
    repo.crear("01/03/2026", cliente.id, [Linea("Recién escrita", cantidad=1, precio_ud=100)])

    copia = backup.copiar(base)
    guardada = sqlite3.connect(copia)
    try:
        conceptos = {f[0] for f in guardada.execute("SELECT descripcion FROM Detalle_linea")}
    finally:
        guardada.close()
    assert "Recién escrita" in conceptos


def test_restaurar_devuelve_los_datos_borrados(base):
    copia = backup.copiar(base)
    antes = len(repo.listar())

    for documento in repo.listar():
        repo.eliminar(documento.id)
    assert repo.listar() == []

    resultado = backup.restaurar(copia, base)
    assert resultado["restaurada"] == base
    assert len(repo.listar()) == antes


def test_restaurar_guarda_antes_lo_que_habia(base):
    """Restaurar la copia equivocada no puede ser un camino de ida."""
    copia = backup.copiar(base)
    cliente = repo_clientes.listar()[0]
    repo.crear("05/03/2026", cliente.id, [Linea("Posterior a la copia", cantidad=1, precio_ud=10)])

    resultado = backup.restaurar(copia, base)
    previa = resultado["copia_previa"]

    assert previa is not None and previa.exists()
    guardada = sqlite3.connect(previa)
    try:
        conceptos = {f[0] for f in guardada.execute("SELECT descripcion FROM Detalle_linea")}
    finally:
        guardada.close()
    assert "Posterior a la copia" in conceptos


def test_las_copias_se_listan_de_la_mas_reciente_a_la_mas_antigua(base):
    nombres = []
    for marca in ("2026-01-01_090000", "2026-03-01_090000", "2026-02-01_090000"):
        destino = backup.directorio(base) / f"billease-{marca}.db"
        backup.copiar(base, destino, cuantas_se_guardan=0)
        nombres.append(destino.name)

    listadas = [c.name for c in backup.copias(base)]
    assert listadas == sorted(nombres, reverse=True)
    assert backup.fecha_de(listadas[0]).year == 2026
    assert backup.fecha_de(listadas[0]).month == 3


def test_solo_se_guardan_las_ultimas_copias(base):
    for numero in range(8):
        backup.copiar(
            base,
            backup.directorio(base) / f"billease-2026-01-{numero + 1:02d}_090000.db",
            cuantas_se_guardan=0,
        )
    backup.limpiar(base, cuantas_se_guardan=5)

    quedan = backup.copias(base)
    assert len(quedan) == 5
    # Se quedan las más recientes, no cinco cualesquiera.
    assert quedan[0].name.endswith("08_090000.db")
    assert quedan[-1].name.endswith("04_090000.db")


def test_copiar_una_base_que_no_existe_no_es_un_error(tmp_path):
    assert backup.copiar(tmp_path / "no-existe.db") is None


def test_restaurar_una_copia_que_no_existe_avisa(base):
    with pytest.raises(FileNotFoundError):
        backup.restaurar(base.parent / "inventada.db", base)


# ─────────────────────── exportación a CSV ───────────────────────


def leer_csv(ruta):
    with open(ruta, newline="", encoding=CODIFICACION) as fichero:
        return list(csv.reader(fichero, delimiter=SEPARADOR))


def test_el_csv_de_documentos_lleva_el_desglose_de_iva(base, tmp_path):
    documentos = repo.listar()
    destino = tmp_path / "documentos.csv"
    cuantas = exportar_documentos(documentos, destino)

    filas = leer_csv(destino)
    assert cuantas == 2
    assert len(filas) == 3                       # cabecera + dos facturas
    assert filas[0][0] == "Número"

    # 1.240 + 2 × 97,50 = 1.435,00 de base · 21 % = 301,35 · total 1.736,35
    fila = next(f for f in filas[1:] if f[0] == "2026-001")
    assert fila[6] == "1.435,00"
    assert fila[8] == "301,35"
    assert fila[9] == "1.736,35"
    assert fila[10] == "Pendiente"


def test_el_csv_lo_entiende_un_excel_en_espanol(base, tmp_path):
    """Punto y coma, coma decimal y BOM: si no, Excel parte las columnas."""
    destino = tmp_path / "documentos.csv"
    exportar_documentos(repo.listar(), destino)

    crudo = destino.read_bytes()
    assert crudo.startswith(b"\xef\xbb\xbf")     # el BOM que necesita Excel
    texto = crudo.decode(CODIFICACION)
    assert ";" in texto.splitlines()[0]
    assert "1.435,00" in texto                   # coma decimal, no punto


def test_el_csv_de_conceptos_tiene_una_fila_por_linea(base, tmp_path):
    destino = tmp_path / "conceptos.csv"
    cuantas = exportar_lineas(repo.listar(), destino, lineas_de=repo.lineas_de)

    filas = leer_csv(destino)
    assert cuantas == 3
    assert len(filas) == 4

    # El listado viene de la más reciente a la más antigua: se busca la fila,
    # no se da por supuesto que esté la primera.
    armario = next(f for f in filas[1:] if f[4].startswith("Armario a medida"))
    assert armario[0] == "2026-001"
    assert armario[5] == "1"          # cantidad
    assert armario[8] == "1.240,00"   # importe


def test_el_csv_de_clientes_dice_si_es_persona_o_empresa(base, tmp_path):
    destino = tmp_path / "clientes.csv"
    exportar_clientes(repo_clientes.listar(), destino)

    filas = leer_csv(destino)
    assert filas[1][0] == "Construcciones Pérez S.L."
    assert filas[1][1] == "B12345674"
    assert filas[1][2] == "Persona jurídica"


def test_el_csv_del_resumen_lleva_los_cuatro_trimestres_y_el_ano(base, tmp_path):
    from core.reports import resumen_trimestral

    resumen = resumen_trimestral(repo.listar(), 2026)
    destino = tmp_path / "resumen.csv"
    exportar_resumen(resumen, destino)

    filas = leer_csv(destino)
    assert len(filas) == 6                        # cabecera + 4 trimestres + año
    assert filas[1][0] == "1.º trimestre"
    assert filas[5][0] == "Ejercicio 2026"
    assert filas[5][4] == "1.622,50"              # 1.435,00 + 187,50 de base


def test_exportar_todo_deja_los_tres_ficheros(base, tmp_path):
    destino = tmp_path / "exportado"
    escrito = exportar_todo(
        destino, repo.listar(), repo_clientes.listar(), lineas_de=repo.lineas_de
    )

    assert escrito == {"documentos.csv": 2, "conceptos.csv": 3, "clientes.csv": 1}
    for nombre in escrito:
        assert (destino / nombre).exists()


def test_el_csv_no_parte_un_concepto_con_salto_de_linea(base, tmp_path):
    cliente = repo_clientes.listar()[0]
    repo.crear("10/03/2026", cliente.id, [
        Linea("Primera línea\nsegunda línea", cantidad=1, precio_ud=50)
    ])
    destino = tmp_path / "conceptos.csv"
    exportar_lineas(repo.listar(), destino, lineas_de=repo.lineas_de)

    filas = leer_csv(destino)
    concepto = [f for f in filas if f[4].startswith("Primera línea")][0]
    assert concepto[4] == "Primera línea segunda línea"


def test_el_csv_marca_las_cobradas(base, tmp_path):
    documento = repo.listar()[0]
    assert repo.cambiar_estado(documento.id, COBRADA)

    destino = tmp_path / "documentos.csv"
    exportar_documentos(repo.listar(), destino)
    filas = leer_csv(destino)
    situaciones = {f[0]: f[10] for f in filas[1:]}
    assert situaciones[documento.referencia] == "Cobrada"
