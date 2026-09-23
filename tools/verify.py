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
    fase 2 → --post-migracion tipos, fechas ISO y claves ajenas aplicadas
    fase 3 → --conexiones     una sola conexión para pintar la lista
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventario import BASE_POR_DEFECTO, FICHERO_BASELINE, leer

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


def verificar_linea_base(inv, base, r):
    """Los ocho invariantes de la fase 0."""
    for tabla in ("Autonomo", "Cliente", "Factura", "Servicio", "Detalle_linea"):
        if tabla in base["conteos"]:
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
        facturas = cur.execute(
            "SELECT Num_factura, fecha, total, Cod_cliente FROM Factura ORDER BY Num_factura"
        ).fetchall()

        with tempfile.TemporaryDirectory(prefix="billease-verify-") as tmp:
            for num, fecha, base_guardada, _cod_cliente in facturas:
                detalles = cur.execute(
                    "SELECT d.Num_Factura, d.Num_Linea, d.NumServicios, d.precioPorServicio,"
                    " d.cod_servicio, s.descripcion"
                    " FROM Detalle_linea d JOIN Servicio s ON s.Cod_servicio = d.cod_servicio"
                    " WHERE d.Num_Factura = ? ORDER BY d.Num_Linea",
                    (num,),
                ).fetchall()

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


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--base", default=BASE_POR_DEFECTO, help="base de datos a verificar")
    parser.add_argument("--baseline", default=FICHERO_BASELINE, help="línea base de referencia")
    for pendiente in ("totales", "post-migracion", "conexiones", "abrir-todas", "pintar"):
        parser.add_argument(f"--{pendiente}", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    fase_pendiente = {
        "post_migracion": 2,
        "conexiones": 3,
        "abrir_todas": 4,
        "pintar": 5,
    }
    for nombre, fase in fase_pendiente.items():
        if getattr(args, nombre):
            print(f"\n--{nombre.replace('_', '-')} se implementa en la fase {fase}.")
            print("Consulta docs/RUTA.md.\n")
            return 2

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
        verificar_totales(args.base, r)
    return r.resumen()


if __name__ == "__main__":
    raise SystemExit(main())
