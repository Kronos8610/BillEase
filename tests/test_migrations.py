"""
Pruebas de las migraciones de la fase 2.

Se ejecutan siempre sobre una base recién generada con el esquema original,
nunca sobre la del usuario. Lo que se comprueba es lo que exige la puerta 2:
que no se pierde ni un dato, que aplicarlas dos veces no cambia nada y que a
partir de ahora la base se defiende sola.
"""

import sqlite3

import pytest

from core.fechas import a_espanol, a_iso
from core.security import es_hash, verificar
from data.connection import abrir
from data.migrations import aplicadas, migrar, pendientes
from tools import seed_demo
from tools.inventario import leer


@pytest.fixture
def base_v0(tmp_path):
    """Una base con el esquema y los datos de partida, sin migrar."""
    ruta = tmp_path / "v0.db"
    conn = abrir(ruta)
    seed_demo.crear_esquema(conn)
    seed_demo.rellenar(conn)
    conn.close()
    return ruta


@pytest.fixture
def base_migrada(base_v0):
    conn = abrir(base_v0)
    migrar(conn, registrar=lambda *_: None)
    conn.close()
    return base_v0


# ─────────────────────── no se pierde nada ───────────────────────


def test_el_inventario_no_cambia_al_migrar(base_v0):
    antes = leer(base_v0)

    conn = abrir(base_v0)
    migrar(conn, registrar=lambda *_: None)
    conn.close()

    despues = leer(base_v0)

    # El catálogo desaparece a propósito en la 007; lo demás tiene que estar
    # exactamente igual, fila por fila.
    permanecen = {t: n for t, n in antes["conteos"].items() if t != "Servicio"}
    assert {t: n for t, n in despues["conteos"].items() if t != "Servicio"} == permanecen
    assert "Servicio" not in despues["conteos"]
    assert despues["suma_bases"] == antes["suma_bases"] == 3768.5
    assert despues["suma_lineas"] == antes["suma_lineas"]
    assert despues["numeros_factura"] == antes["numeros_factura"]


def test_las_dieciseis_lineas_conservan_su_descripcion(base_migrada):
    conn = abrir(base_migrada)
    filas = conn.execute(
        "SELECT Num_Factura, Num_Linea, descripcion FROM Detalle_linea"
        " ORDER BY Num_Factura, Num_Linea"
    ).fetchall()
    conn.close()

    assert len(filas) == 16
    vacias = [(f["Num_Factura"], f["Num_Linea"]) for f in filas if not f["descripcion"]]
    assert vacias == [], f"líneas sin descripción: {vacias}"
    assert filas[0]["descripcion"] == "Instalación de fontanería"


def test_los_importes_quedan_desglosados(base_migrada):
    conn = abrir(base_migrada)
    filas = {f["Num_factura"]: f for f in conn.execute("SELECT * FROM Factura")}
    conn.close()

    # La columna `total` de antes era la base imponible.
    assert filas[4]["base"] == 537.5
    assert filas[4]["tipo_iva"] == 21
    assert filas[4]["importe_total"] == 650.38
    # Y para todas: total = base + IVA, al céntimo.
    for f in filas.values():
        assert round(f["base"] * 1.21, 2) == pytest.approx(f["importe_total"], abs=0.01)


# ─────────────────────── los defectos cerrados ───────────────────────


def test_el_codigo_postal_recupera_su_cero_inicial(tmp_path):
    """«08001» se guardaba como 8001.0 porque la columna era REAL (defecto 04)."""
    from data.migrations.m001_tipos_texto import _cp

    conn = sqlite3.connect(tmp_path / "cp.db")
    conn.execute("CREATE TABLE t (cp REAL)")
    for valor in ("08001", "28001", "01001"):
        conn.execute("INSERT INTO t VALUES (?)", (valor,))

    assert [f[0] for f in conn.execute("SELECT cp FROM t")] == [8001.0, 28001.0, 1001.0]
    assert [f[0] for f in conn.execute(f"SELECT {_cp('cp')} FROM t")] == [
        "08001", "28001", "01001",
    ]
    conn.close()


def test_los_codigos_postales_quedan_guardados_como_texto(base_migrada):
    conn = abrir(base_migrada)
    tipos = {f[0] for f in conn.execute("SELECT DISTINCT typeof(cod_postal) FROM Cliente")}
    cps = {f[0] for f in conn.execute("SELECT cod_postal FROM Cliente")}
    telefono = conn.execute("SELECT telefono FROM Autonomo").fetchone()[0]
    conn.close()

    assert tipos == {"text"}
    assert "08020" in cps
    assert telefono == "612345678"  # sin el «.0» que arrastraba el tipo REAL


def test_las_fechas_quedan_en_iso_y_ordenan_bien(base_migrada):
    conn = abrir(base_migrada)
    fechas = [f[0] for f in conn.execute("SELECT fecha FROM Factura ORDER BY fecha")]
    conn.close()

    assert fechas[0] == "2025-01-15"
    assert fechas == sorted(fechas)          # ordenar por fecha ordena de verdad
    assert a_espanol(fechas[0]) == "15/01/2025"


def test_la_serie_fiscal_queda_correlativa(base_migrada):
    conn = abrir(base_migrada)
    filas = conn.execute(
        "SELECT ejercicio, numero FROM Factura ORDER BY ejercicio, numero"
    ).fetchall()
    conn.close()

    assert [f["numero"] for f in filas] == [1, 2, 3, 4, 5, 6, 7]
    assert {f["ejercicio"] for f in filas} == {2025}


def test_no_se_puede_repetir_un_numero_de_la_serie(base_migrada):
    conn = abrir(base_migrada)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO Factura (fecha, base, tipo_iva, importe_total, Cod_cliente,"
            " serie, ejercicio, numero) VALUES ('2025-04-01', 10, 21, 12.1, 1, '', 2025, 1)"
        )
    conn.close()


def test_la_contrasena_deja_de_estar_en_claro(base_migrada):
    conn = abrir(base_migrada)
    guardada = conn.execute("SELECT contrasena FROM Autonomo").fetchone()[0]
    conn.close()

    assert guardada != "Pass1234"
    assert es_hash(guardada)
    assert verificar("Pass1234", guardada)[0] is True
    assert verificar("otra cosa", guardada)[0] is False


def test_una_linea_huerfana_deja_de_admitirse(base_migrada):
    """Antes se aceptaba: las claves ajenas estaban declaradas pero apagadas."""
    conn = abrir(base_migrada)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
            " NumServicios, unidad, precioPorServicio)"
            " VALUES (9999, 1, 'inventada', 1, 'ud', 10)"
        )
    conn.close()


def test_el_catalogo_desaparece_pero_los_conceptos_se_conservan(base_migrada):
    """La 005 copió el texto en cada línea; la 007 retira la tabla."""
    conn = abrir(base_migrada)
    tablas = {f[0] for f in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    descripciones = [f[0] for f in conn.execute(
        "SELECT descripcion FROM Detalle_linea ORDER BY Num_Factura, Num_Linea"
    )]
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(Detalle_linea)")}
    conn.close()

    assert "Servicio" not in tablas
    assert "cod_servicio" not in columnas
    assert len(descripciones) == 16
    assert all(descripciones)
    assert descripciones[0] == "Instalación de fontanería"


def test_todo_lo_que_habia_queda_marcado_como_factura(base_migrada):
    conn = abrir(base_migrada)
    filas = conn.execute("SELECT tipo, estado FROM Factura").fetchall()
    conn.close()
    assert {f["tipo"] for f in filas} == {"factura"}
    assert {f["estado"] for f in filas} == {"emitida"}


def test_borrar_una_factura_arrastra_sus_lineas(base_migrada):
    conn = abrir(base_migrada)
    assert conn.execute(
        "SELECT COUNT(*) FROM Detalle_linea WHERE Num_Factura = 1"
    ).fetchone()[0] == 2

    conn.execute("DELETE FROM Factura WHERE Num_factura = 1")
    assert conn.execute(
        "SELECT COUNT(*) FROM Detalle_linea WHERE Num_Factura = 1"
    ).fetchone()[0] == 0
    conn.close()


# ─────────────────────── se pueden repetir ───────────────────────


def test_migrar_dos_veces_no_cambia_nada(base_v0):
    conn = abrir(base_v0)
    primera = migrar(conn, registrar=lambda *_: None)
    inventario_tras_la_primera = leer(base_v0)

    segunda = migrar(conn, registrar=lambda *_: None)
    conn.close()

    assert primera == [1, 2, 3, 4, 5, 6, 7, 8]
    assert segunda == []
    assert leer(base_v0)["conteos"] == inventario_tras_la_primera["conteos"]


def test_una_base_a_medio_migrar_solo_aplica_lo_que_falta(base_v0):
    conn = abrir(base_v0)
    # Se aplican a mano las tres primeras, como si hubiera fallado la cuarta.
    from data.migrations import MIGRACIONES

    aplicadas(conn)  # crea la tabla de registro
    for m in MIGRACIONES[:3]:
        conn.execute("PRAGMA foreign_keys = OFF")
        m.aplicar(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, aplicada, descripcion)"
            " VALUES (?, 'a mano', ?)",
            (m.VERSION, m.DESCRIPCION),
        )
        conn.commit()

    assert [m.VERSION for m in pendientes(conn)] == [4, 5, 6, 7, 8]
    assert migrar(conn, registrar=lambda *_: None) == [4, 5, 6, 7, 8]
    assert aplicadas(conn) == {1, 2, 3, 4, 5, 6, 7, 8}
    conn.close()


def test_se_guarda_una_copia_antes_de_migrar(base_v0, tmp_path):
    conn = abrir(base_v0)
    migrar(conn, ruta=base_v0, registrar=lambda *_: None)
    conn.close()

    copias = list(tmp_path.glob("v0.db.*.bak"))
    assert len(copias) == 1, "la migración debe dejar una copia de seguridad"

    # Y la copia sigue teniendo los datos de partida, sin migrar.
    anterior = sqlite3.connect(copias[0])
    columnas = {f[1] for f in anterior.execute("PRAGMA table_info(Factura)")}
    anterior.close()
    assert "total" in columnas and "base" not in columnas


# ─────────────────────── conversión de fechas ───────────────────────


@pytest.mark.parametrize(
    "entrada,esperada",
    [
        ("15/01/2025", "2025-01-15"),
        ("3/2/2025", "2025-02-03"),
        ("2025-01-15", "2025-01-15"),
        ("", ""),
        ("lo que sea", "lo que sea"),   # no se entiende: se conserva tal cual
    ],
)
def test_conversion_de_fechas(entrada, esperada):
    assert a_iso(entrada) == esperada
