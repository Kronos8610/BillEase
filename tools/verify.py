"""
Comprueba los invariantes de la base de datos contra la línea base.

    python tools/verify.py                          verifica BillEase.db
    python tools/verify.py --base otra.db           verifica otra base
    python tools/verify.py --baseline otro.json     usa otra referencia

Devuelve 0 si todo está en verde y 1 si falla algo, de modo que sirve tal
cual como puerta en un script o en integración continua.

Esta es la herramienta que usan todas las puertas de la ruta (docs/RUTA.md).
Cada fase añade aquí sus comprobaciones:

    fase 1 → --totales        el total de la lista coincide con el del PDF  ✓
    fase 2 → --post-migracion tipos, fechas ISO y claves ajenas aplicadas  ✓
    fase 3 → --conexiones     una sola conexión para pintar la lista  ✓
    fase 4 → --abrir-todas    todos los documentos se abren y se imprimen  ✓
    fase 5 → --pintar         el listado se pinta al instante con 1.000  ✓
    fase 6 → --fiscal         el resumen de IVA cuadra con la suma a mano  ✓
    fase 6 → --copia          la copia se hace y se restaura de verdad  ✓
"""

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventario import FICHERO_BASELINE, _base_por_defecto, leer

OK = "  OK  "
FALLA = " FALLA"


class Resultado:
    """Acumula comprobaciones y las imprime en una tabla legible."""

    def __init__(self):
        self.fallos = 0
        self.total = 0

    def comprobar(self, etiqueta, obtenido, esperado, detalle=""):
        self.total += 1
        bien = obtenido == esperado
        if not bien:
            self.fallos += 1
        marca = OK if bien else FALLA
        linea = f"[{marca}] {etiqueta:<34} {obtenido!r}"
        if not bien:
            linea += f"   ← se esperaba {esperado!r}"
        if detalle:
            linea += f"\n         {detalle}"
        print(linea)
        return bien

    def resumen(self):
        buenas = self.total - self.fallos
        print()
        if self.fallos:
            print(f"{buenas}/{self.total} invariantes OK — {self.fallos} FALLAN")
        else:
            print(f"{buenas}/{self.total} invariantes OK")
        print()
        return 1 if self.fallos else 0


# Tablas que desaparecen a propósito en alguna migración. Cualquier otra que
# falte es una pérdida de datos, no una decisión.
TABLAS_RETIRADAS = {"Servicio": "migración 007: el catálogo se retira"}


@contextmanager
def apuntando_a(ruta):
    """
    Hace que la aplicación mire a otra base, y lo deja como estaba al salir.

    Varias comprobaciones trabajan sobre una base temporal. Si una de ellas se
    dejara `BILLEASE_DB` apuntando a un directorio ya borrado, la siguiente
    fallaría con «no such table» sin que nada estuviera mal.
    """
    from data import connection

    anterior = os.environ.get("BILLEASE_DB")
    os.environ["BILLEASE_DB"] = str(ruta)
    connection.cerrar()
    try:
        yield ruta
    finally:
        connection.cerrar()
        if anterior is None:
            os.environ.pop("BILLEASE_DB", None)
        else:
            os.environ["BILLEASE_DB"] = anterior


def verificar_linea_base(inv, base, r):
    """Los ocho invariantes de la fase 0."""
    for tabla in ("Autonomo", "Cliente", "Factura", "Servicio", "Detalle_linea"):
        if tabla not in base["conteos"]:
            continue
        if tabla not in inv["conteos"] and tabla in TABLAS_RETIRADAS:
            print(f"[  --  ] {'tabla ' + tabla:<34} retirada · {TABLAS_RETIRADAS[tabla]}")
            continue
        r.comprobar(
            f"filas en {tabla}",
            inv["conteos"].get(tabla),
            base["conteos"][tabla],
        )

    r.comprobar("suma de bases (€)", inv["suma_bases"], base["suma_bases"])

    # No se compara contra la línea base sino contra sí misma: la suma de las
    # líneas TIENE que ser la suma de los totales guardados, ahora y siempre.
    r.comprobar(
        "suma de líneas = suma de bases",
        inv["suma_lineas"],
        inv["suma_bases"],
        detalle="Si no cuadra, alguna factura guarda un total que sus líneas no justifican.",
    )

    numeros = inv["numeros_factura"]
    sin_huecos = numeros == list(range(min(numeros), max(numeros) + 1)) if numeros else True
    r.comprobar(
        "serie de facturas sin huecos",
        sin_huecos,
        True,
        detalle=f"números: {numeros}",
    )


def verificar_totales(ruta_base, r):
    """
    Fase 1 · el importe que ve el usuario es el mismo en los dos sitios.

    Para cada factura se calculan los totales por los dos caminos que usa el
    programa —desde la base guardada, como el listado, y desde las líneas, como
    el PDF— y se comprueba que dan el mismo céntimo. Además se genera el PDF de
    verdad y se comprueba que el total impreso es ese mismo.
    """
    import sqlite3
    import tempfile
    from pathlib import Path as _Path

    from core.taxes import calcular, desde_base, desde_detalles, formatear
    from documents.invoice_pdf import generar_documento_pdf

    conn = sqlite3.connect(f"file:{ruta_base}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        # La columna de la base se llamaba `total` antes de la migración 003,
        # y las líneas no tenían descripción propia antes de la 005: esta
        # comprobación se usa a los dos lados de la fase 2.
        columnas_factura = {f[1] for f in cur.execute("PRAGMA table_info(Factura)")}
        columna_base = "base" if "base" in columnas_factura else "total"
        columnas_linea = {f[1] for f in cur.execute("PRAGMA table_info(Detalle_linea)")}
        linea_con_texto = "descripcion" in columnas_linea

        facturas = cur.execute(
            f"SELECT Num_factura, fecha, {columna_base}, Cod_cliente"
            " FROM Factura ORDER BY Num_factura"
        ).fetchall()

        with tempfile.TemporaryDirectory(prefix="billease-verify-") as tmp:
            for num, fecha, base_guardada, _cod_cliente in facturas:
                if linea_con_texto:
                    filas = cur.execute(
                        "SELECT descripcion, NumServicios, precioPorServicio"
                        " FROM Detalle_linea WHERE Num_Factura = ? ORDER BY Num_Linea",
                        (num,),
                    ).fetchall()
                else:
                    filas = cur.execute(
                        "SELECT COALESCE(s.descripcion, ''), d.NumServicios, d.precioPorServicio"
                        " FROM Detalle_linea d"
                        " LEFT JOIN Servicio s ON s.Cod_servicio = d.cod_servicio"
                        " WHERE d.Num_Factura = ? ORDER BY d.Num_Linea",
                        (num,),
                    ).fetchall()
                detalles = [(0, 0, f[1], f[2], 0, f[0]) for f in filas]

                lineas = desde_detalles(detalles)
                del_listado = desde_base(base_guardada)
                de_las_lineas = calcular(lineas)

                ruta_pdf = _Path(tmp) / f"factura_{int(num)}.pdf"
                resultado = generar_documento_pdf(
                    {
                        "tipo": "factura",
                        "numero": str(int(num)),
                        "fecha": fecha,
                        "emisor": {"nombre": "Emisor de prueba", "nif": "00000000T"},
                        "cliente": {"nombre": "Cliente de prueba", "nif": "00000000T"},
                        "lineas": lineas,
                    },
                    ruta_pdf,
                )

                r.comprobar(
                    f"factura {int(num)}: listado = líneas",
                    formatear(del_listado.total),
                    formatear(de_las_lineas.total),
                )
                r.comprobar(
                    f"factura {int(num)}: PDF = listado",
                    formatear(resultado["totales"].total),
                    formatear(del_listado.total),
                )
    finally:
        conn.close()


def verificar_post_migracion(ruta_base, r):
    """
    Fase 2 · la base ya no puede corromper ni admitir datos incoherentes.

    Comprueba lo que exige la puerta 2, mirando el esquema y los datos, no el
    código de las migraciones.
    """
    import sqlite3

    conn = sqlite3.connect(ruta_base)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        r.comprobar(
            "PRAGMA foreign_keys",
            conn.execute("PRAGMA foreign_keys").fetchone()[0],
            1,
        )

        tipos_cp = {f[0] for f in conn.execute("SELECT DISTINCT typeof(cod_postal) FROM Cliente")}
        r.comprobar("cod_postal guardado como texto", sorted(tipos_cp), ["text"])

        con_punto = conn.execute(
            "SELECT COUNT(*) FROM Cliente WHERE telefono LIKE '%.0'"
        ).fetchone()[0]
        r.comprobar("teléfonos sin el «.0» del tipo REAL", con_punto, 0)

        no_iso = conn.execute(
            "SELECT COUNT(*) FROM Factura WHERE fecha NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
        ).fetchone()[0]
        r.comprobar("fechas en formato ISO", no_iso, 0)

        sin_numero = conn.execute(
            "SELECT COUNT(*) FROM Factura WHERE numero IS NULL OR ejercicio IS NULL"
        ).fetchone()[0]
        r.comprobar("facturas con número de serie", sin_numero, 0)

        sin_descripcion = conn.execute(
            "SELECT COUNT(*) FROM Detalle_linea WHERE descripcion IS NULL OR descripcion = ''"
        ).fetchone()[0]
        r.comprobar("líneas con descripción propia", sin_descripcion, 0)

        en_claro = conn.execute(
            "SELECT COUNT(*) FROM Autonomo WHERE contrasena NOT LIKE '$argon2%'"
        ).fetchone()[0]
        r.comprobar("contraseñas cifradas", en_claro, 0)

        descuadre = conn.execute(
            "SELECT COUNT(*) FROM Factura"
            " WHERE ABS(importe_total - ROUND(base * (1 + tipo_iva / 100.0), 2)) > 0.01"
        ).fetchone()[0]
        r.comprobar("total = base + IVA en todas", descuadre, 0)

        # La prueba de fuego: la base tiene que rechazar una línea huérfana.
        try:
            conn.execute("SAVEPOINT prueba")
            conn.execute(
                "INSERT INTO Detalle_linea (Num_Factura, Num_Linea, descripcion,"
                " NumServicios, unidad, precioPorServicio)"
                " VALUES (999999, 1, 'inventada', 1, 'ud', 10)"
            )
            conn.execute("ROLLBACK TO prueba")
            rechazada = False
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK TO prueba")
            rechazada = True
        r.comprobar("una línea huérfana se rechaza", rechazada, True)

        r.comprobar(
            "claves ajenas coherentes",
            len(conn.execute("PRAGMA foreign_key_check").fetchall()),
            0,
        )
    finally:
        conn.close()


def verificar_conexiones(ruta_base, r):
    """
    Fase 3 · pintar el listado deja de ser un N+1.

    Antes se pedía la lista de facturas y después, una consulta por fila, el
    nombre del cliente: con siete facturas eran ocho viajes a la base y con
    quinientas, quinientos uno (defecto 09).

    Se cuentan de verdad las conexiones abiertas y las sentencias ejecutadas.
    """
    import os
    import sqlite3

    os.environ["BILLEASE_DB"] = str(ruta_base)

    from data import connection
    from data.repositories import documentos as repo_documentos

    connection.cerrar()

    abrir_original = sqlite3.connect
    conexiones = []

    def espia(*args, **kwargs):
        conn = abrir_original(*args, **kwargs)
        conexiones.append(conn)
        return conn

    sentencias = []
    sqlite3.connect = espia
    try:
        conn = connection.conexion()
        conn.set_trace_callback(sentencias.append)
        documentos = repo_documentos.listar()
        conn.set_trace_callback(None)
    finally:
        sqlite3.connect = abrir_original

    consultas = [s for s in sentencias if s.strip().upper().startswith("SELECT")]

    r.comprobar("conexiones para pintar el listado", len(conexiones), 1)
    r.comprobar(
        "consultas para pintar el listado",
        len(consultas),
        1,
        detalle=f"{len(documentos)} facturas, con el nombre del cliente ya incluido",
    )
    con_nombre = all(d.cliente_nombre for d in documentos)
    r.comprobar("el nombre del cliente viene en la misma consulta", con_nombre, True)

    connection.cerrar()


def verificar_abrir_todas(ruta_base, r):
    """
    Fase 4 · todos los documentos que ya existían siguen abriéndose e
    imprimiéndose después de retirar el catálogo de servicios.
    """
    import os
    import tempfile
    from pathlib import Path as _Path

    os.environ["BILLEASE_DB"] = str(ruta_base)

    from core.taxes import calcular, formatear
    from data import connection
    from data.repositories import clientes as repo_clientes
    from data.repositories import documentos as repo_documentos
    from documents.invoice_pdf import generar_documento_pdf

    connection.cerrar()

    documentos = repo_documentos.listar("factura") + repo_documentos.listar("presupuesto")
    r.comprobar("documentos encontrados", len(documentos) > 0, True)

    with tempfile.TemporaryDirectory(prefix="billease-abrir-") as tmp:
        fallos = []
        sin_concepto = []
        for documento in documentos:
            completo = repo_documentos.obtener(documento.id)
            if not completo.lineas or any(not l.descripcion for l in completo.lineas):
                sin_concepto.append(completo.referencia)
            cliente = repo_clientes.obtener(completo.cliente_id)
            try:
                totales = calcular(completo.lineas)
                resultado = generar_documento_pdf(
                    {
                        "tipo": completo.tipo,
                        "numero": completo.referencia,
                        "fecha": completo.fecha,
                        "emisor": {"nombre": "Emisor de prueba", "nif": "00000000T"},
                        "cliente": {"nombre": cliente.nombre if cliente else "",
                                    "nif": cliente.nif if cliente else ""},
                        "lineas": completo.lineas,
                    },
                    _Path(tmp) / f"{completo.referencia}.pdf",
                    totales=totales,
                )
                if formatear(resultado["totales"].total) != formatear(completo.importe_total):
                    fallos.append(f"{completo.referencia}: el total del PDF no cuadra")
            except Exception as e:  # noqa: BLE001
                fallos.append(f"{completo.referencia}: {e}")

        r.comprobar("documentos que se imprimen sin fallo", fallos, [])
        r.comprobar("documentos con todos sus conceptos", sin_concepto, [])

    connection.cerrar()


# Lo que exige la puerta 5 para el listado.
LIMITE_MS = 300
LIMITE_WIDGETS = 100
FACTURAS_DE_PRUEBA = 1000


def verificar_pintar(ruta_base, r):
    """
    Fase 5 · el listado se pinta al instante, tenga la base siete filas o mil.

    Antes cada fila eran hasta once widgets que se creaban y se destruían en
    cada recarga: con mil facturas, más de siete mil widgets que Qt tiene que
    medir, colocar y pintar (defecto 11). Ahora es una `QTableView` sobre un
    modelo, que solo pinta lo que cabe en la pantalla.

    Se mide de verdad: se genera una base con mil facturas, se abre el listado
    y se cronometra. Si no se le pasa `--base`, la base de prueba se crea en
    un directorio temporal y se borra al salir, sin tocar la del usuario.
    """
    import tempfile
    from pathlib import Path as _Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    with tempfile.TemporaryDirectory(prefix="billease-pintar-") as tmp:
        if ruta_base is None:
            ruta_base = _Path(tmp) / "grande.db"
            _base_grande(ruta_base)
        with apuntando_a(ruta_base):
            _medir_pintado(r)


def _base_grande(ruta):
    """Una base con mil facturas, recorriendo las mismas migraciones de siempre."""
    from data.connection import abrir
    from data.migrations import migrar
    from tools import seed_demo

    conn = abrir(ruta)
    try:
        seed_demo.crear_esquema(conn)
        seed_demo.rellenar(conn)
        seed_demo.rellenar_muchas(conn, FACTURAS_DE_PRUEBA)
        migrar(conn, registrar=lambda *_: None)
    finally:
        conn.close()


def _medir_pintado(r):
    """Abre el listado y cronometra, con la base ya puesta."""
    import time

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    import theme
    from data.repositories import documentos as repo_documentos
    from ui.models import ROL_ORDEN
    from ui.views.listado import FACTURAS, Listado

    app = QApplication.instance() or QApplication([])
    theme.aplicar_tema(app, "claro")

    cuantas = len(repo_documentos.listar("factura"))
    r.comprobar("facturas en la base de prueba", cuantas >= FACTURAS_DE_PRUEBA, True,
                detalle=f"{cuantas} facturas")

    widgets_antes = len(app.allWidgets())

    comienzo = time.perf_counter()
    listado = Listado(FACTURAS)              # consulta + modelo + primera pintura
    listado.resize(1280, 800)
    listado.show()
    app.processEvents()
    milisegundos = (time.perf_counter() - comienzo) * 1000

    vivos = len(app.allWidgets()) - widgets_antes

    r.comprobar(
        f"el listado se pinta en menos de {LIMITE_MS} ms",
        milisegundos < LIMITE_MS,
        True,
        detalle=f"{milisegundos:.0f} ms con {cuantas} facturas",
    )
    r.comprobar(
        f"menos de {LIMITE_WIDGETS} widgets vivos",
        vivos < LIMITE_WIDGETS,
        True,
        detalle=f"{vivos} widgets para {cuantas} filas"
                f" (antes eran ~11 por fila: {cuantas * 11})",
    )
    r.comprobar("todas las filas en el modelo", listado.modelo.rowCount(), cuantas)

    # Y que la búsqueda y el orden de verdad funcionan sobre esos mil.
    listado.buscador.setText("perez")
    app.processEvents()
    filtradas = listado.filtro.rowCount()
    r.comprobar("la búsqueda filtra", 0 < filtradas < cuantas, True,
                detalle=f"«perez» deja {filtradas} de {cuantas}")
    listado.buscador.clear()

    # La columna del importe, buscada por su título: el orden de las columnas
    # cambia cuando se añade alguna, como la del cobro en la fase 6.
    columna_total = next(
        numero for numero, columna in enumerate(listado.modelo.columnas)
        if columna.titulo == "Total"
    )
    listado.vista.sortByColumn(columna_total, Qt.SortOrder.DescendingOrder)
    app.processEvents()
    importes = [
        listado.filtro.index(fila, columna_total).data(ROL_ORDEN)
        for fila in range(min(50, listado.filtro.rowCount()))
    ]
    r.comprobar("el orden por importe es numérico",
                importes == sorted(importes, reverse=True), True,
                detalle=f"de {importes[0]} € a {importes[-1]} €")

    listado.close()
    listado.deleteLater()


def verificar_fiscal(ruta_base, r):
    """
    Fase 6 · el resumen trimestral cuadra con la suma a mano.

    Se suman las facturas una a una, con `Decimal`, sin pasar por
    `core.reports`, y se compara con lo que dice el resumen. Si el resumen se
    comprobara contra sí mismo no se estaría comprobando nada.
    """
    with apuntando_a(ruta_base):
        _cuadrar_resumen(r)


def _cuadrar_resumen(r):
    from decimal import Decimal

    from core.money import formatear
    from core.reports import resumen_trimestral, trimestre_de
    from core.taxes import desde_base
    from data.repositories import documentos as repo_documentos

    facturas = repo_documentos.listar("factura")
    presupuestos = repo_documentos.listar("presupuesto")
    r.comprobar("facturas que entran en el resumen", len(facturas) > 0, True)

    ejercicios = repo_documentos.ejercicios()
    for ejercicio in ejercicios:
        del_ano = [f for f in facturas if f.ejercicio == ejercicio]
        resumen = resumen_trimestral(del_ano + presupuestos, ejercicio)

        # La suma a mano, factura por factura.
        base = cuota = total = Decimal("0")
        por_trimestre = {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("0"), 4: Decimal("0")}
        for factura in del_ano:
            totales = desde_base(factura.base, factura.tipo_iva)
            base += totales.base
            cuota += totales.cuota_iva
            total += totales.total
            por_trimestre[trimestre_de(factura.fecha)] += totales.base

        r.comprobar(
            f"{ejercicio}: base del ejercicio",
            formatear(resumen.anual.base), formatear(base),
            detalle=f"{len(del_ano)} facturas sumadas una a una",
        )
        r.comprobar(f"{ejercicio}: IVA repercutido",
                    formatear(resumen.anual.cuota_iva), formatear(cuota))
        r.comprobar(f"{ejercicio}: total facturado",
                    formatear(resumen.anual.total), formatear(total))
        r.comprobar(
            f"{ejercicio}: los 4 trimestres suman el año",
            formatear(sum((t.base for t in resumen.trimestres), Decimal("0"))),
            formatear(base),
        )
        for numero in (1, 2, 3, 4):
            tramo = resumen.trimestre(numero)
            r.comprobar(f"{ejercicio}: base del {numero}T",
                        formatear(tramo.base), formatear(por_trimestre[numero]))

    # Un presupuesto no es un ingreso: no puede colarse en el resumen.
    if presupuestos:
        de_presupuestos = sum((p.base for p in presupuestos), Decimal("0"))
        suma_resumenes = sum(
            (resumen_trimestral(facturas + presupuestos, e).anual.base for e in ejercicios),
            Decimal("0"),
        )
        suma_facturas = sum((f.base for f in facturas), Decimal("0"))
        r.comprobar(
            "los presupuestos quedan fuera del resumen",
            formatear(suma_resumenes), formatear(suma_facturas),
            detalle=f"{len(presupuestos)} presupuestos por "
                    f"{formatear(de_presupuestos)} € sin declarar",
        )


def verificar_copia(ruta_base, r):
    """
    Fase 6 · la copia de seguridad se hace y se restaura.

    Una copia que no se ha restaurado nunca no es una copia: es un fichero.
    Aquí se copia, se borra todo, se restaura y se comprueba que han vuelto
    los mismos datos —sobre una copia de trabajo, nunca sobre la del usuario.
    """
    import shutil
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory(prefix="billease-copia-") as tmp:
        trabajo = _Path(tmp) / "billease.db"
        shutil.copy2(ruta_base, trabajo)
        with apuntando_a(trabajo):
            _ida_y_vuelta(r, trabajo)


def _ida_y_vuelta(r, trabajo):
    """Copiar, borrar, restaurar y comprobar que ha vuelto todo."""
    from data import backup
    from data.repositories import documentos as repo_documentos

    antes = repo_documentos.listar("factura")
    suma_antes = sum(float(f.importe_total) for f in antes)

    copia = backup.copiar(trabajo)
    r.comprobar("la copia se escribe", copia is not None and copia.exists(), True,
                detalle=str(copia))

    for documento in antes:
        repo_documentos.eliminar(documento.id)
    r.comprobar("se borra todo para la prueba", len(repo_documentos.listar("factura")), 0)

    resultado = backup.restaurar(copia, trabajo)
    despues = repo_documentos.listar("factura")

    r.comprobar("al restaurar vuelven las facturas", len(despues), len(antes))
    r.comprobar(
        "y vuelven con sus importes",
        round(sum(float(f.importe_total) for f in despues), 2),
        round(suma_antes, 2),
    )
    r.comprobar(
        "restaurar guarda antes lo que había",
        resultado["copia_previa"] is not None and resultado["copia_previa"].exists(),
        True,
    )

    # Y la limpieza: no se guardan copias sin fin.
    for numero in range(backup.CUANTAS_SE_GUARDAN + 4):
        backup.copiar(
            trabajo,
            backup.directorio(trabajo) / f"billease-2026-01-{numero + 1:02d}_120000.db",
            cuantas_se_guardan=0,
        )
    backup.limpiar(trabajo)
    r.comprobar(
        "solo se guardan las últimas copias",
        len(backup.copias(trabajo)) <= backup.CUANTAS_SE_GUARDAN,
        True,
        detalle=f"{len(backup.copias(trabajo))} copias, máximo {backup.CUANTAS_SE_GUARDAN}",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--base", default=None, help="base de datos a verificar (por defecto, la de la aplicación)")
    parser.add_argument("--baseline", default=FICHERO_BASELINE, help="línea base de referencia")
    for comprobacion in ("totales", "post-migracion", "conexiones", "abrir-todas",
                         "pintar", "fiscal", "copia"):
        parser.add_argument(f"--{comprobacion}", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    baseline = Path(args.baseline)
    if not baseline.exists():
        print(f"\nERROR: no existe la línea base {baseline}.")
        print("Créala con:  python tools/baseline.py --escribir\n")
        return 2

    try:
        inv = leer(args.base)
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        print("Genera una base de demostración con:  python tools/seed_demo.py\n")
        return 2

    base = json.loads(baseline.read_text(encoding="utf-8"))

    print(f"\nVerificando {args.base} contra {baseline}\n")
    r = Resultado()
    verificar_linea_base(inv, base, r)
    if args.totales:
        print()
        verificar_totales(args.base or _base_por_defecto(), r)
    if args.post_migracion:
        print()
        verificar_post_migracion(str(args.base or _base_por_defecto()), r)
    if args.conexiones:
        print()
        verificar_conexiones(args.base or _base_por_defecto(), r)
    if args.abrir_todas:
        print()
        verificar_abrir_todas(args.base or _base_por_defecto(), r)
    if args.pintar:
        print()
        # Sin --base se genera una base de mil facturas aparte: medir sobre la
        # del usuario, que tiene siete, no dice nada.
        verificar_pintar(args.base, r)
    if args.fiscal:
        print()
        verificar_fiscal(args.base or _base_por_defecto(), r)
    if args.copia:
        print()
        verificar_copia(args.base or _base_por_defecto(), r)
    return r.resumen()


if __name__ == "__main__":
    raise SystemExit(main())
