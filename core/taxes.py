"""
Cálculo de importes de un documento: base, IVA y total.

Este es el **único** sitio del programa donde se calcula el importe de una
factura o un presupuesto. Antes había dos: `crearFactura.py` guardaba la suma
de líneas sin IVA y `generar_factura_pdf` le añadía un 21 % por su cuenta, así
que la misma factura valía dos cifras distintas según dónde se mirara
(defecto 01 de la auditoría).

No importa Qt ni sqlite3: se puede probar en un servidor sin pantalla y sin
base de datos.

Todo se calcula con `Decimal`, nunca con `float`. Con coma flotante binaria,
0,1 + 0,2 no es 0,3, y en una factura eso acaba siendo un céntimo que no
cuadra con la suma de las líneas.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

# Tipos de IVA vigentes en España. El general es el que se aplica si no se
# indica otro; el 0 cubre las operaciones exentas.
IVA_GENERAL = Decimal("21")
IVA_REDUCIDO = Decimal("10")
IVA_SUPERREDUCIDO = Decimal("4")
IVA_EXENTO = Decimal("0")

TIPOS_IVA = (IVA_GENERAL, IVA_REDUCIDO, IVA_SUPERREDUCIDO, IVA_EXENTO)

CENTIMO = Decimal("0.01")


def a_decimal(valor):
    """
    Convierte a Decimal sin heredar el ruido de la coma flotante.

    `Decimal(0.1)` es 0,1000000000000000055511151231257827…, mientras que
    `Decimal("0.1")` es exactamente 0,1. Por eso se pasa siempre por `str`.
    """
    if isinstance(valor, Decimal):
        return valor
    if valor is None or valor == "":
        return Decimal("0")
    return Decimal(str(valor).replace(",", ".").strip())


def redondear(valor):
    """Redondea a céntimos con la regla comercial (0,005 sube a 0,01)."""
    return a_decimal(valor).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def formatear(valor):
    """Importe en formato español: 1.736,35"""
    entero, _, decimales = f"{redondear(valor):.2f}".partition(".")
    negativo = entero.startswith("-")
    entero = entero.lstrip("-")
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    return ("-" if negativo else "") + ".".join(grupos) + "," + decimales


@dataclass(frozen=True)
class Linea:
    """Una línea de concepto de un documento."""

    descripcion: str
    cantidad: Decimal
    precio_ud: Decimal
    tipo_iva: Decimal = IVA_GENERAL
    unidad: str = "ud"

    def __post_init__(self):
        # frozen=True obliga a usar object.__setattr__ para normalizar.
        object.__setattr__(self, "cantidad", a_decimal(self.cantidad))
        object.__setattr__(self, "precio_ud", a_decimal(self.precio_ud))
        object.__setattr__(self, "tipo_iva", a_decimal(self.tipo_iva))

    @property
    def importe(self):
        """Cantidad por precio, ya redondeado a céntimos."""
        return redondear(self.cantidad * self.precio_ud)


@dataclass(frozen=True)
class TramoIVA:
    """Base y cuota de un tipo de IVA concreto, para el desglose."""

    tipo: Decimal
    base: Decimal
    cuota: Decimal


@dataclass(frozen=True)
class Totales:
    """Resultado del cálculo. Es lo que ven la pantalla y el papel."""

    base: Decimal
    cuota_iva: Decimal
    total: Decimal
    desglose: tuple = field(default_factory=tuple)

    @property
    def tipo_unico(self):
        """El tipo de IVA si todo el documento va al mismo; si no, None."""
        return self.desglose[0].tipo if len(self.desglose) == 1 else None


def calcular(lineas):
    """
    Calcula los totales de un documento a partir de sus líneas.

    La base es la suma de los importes de línea **ya redondeados**: así la
    suma que ve el cliente en el papel cuadra exactamente con el total, sin
    céntimos que aparecen de la nada.

    La cuota se calcula por tramos de IVA, no sobre el total, porque un
    documento puede mezclar tipos (materiales al 21 % y una reforma de
    vivienda al 10 %, por ejemplo).
    """
    por_tipo = {}
    for linea in lineas:
        por_tipo.setdefault(linea.tipo_iva, Decimal("0"))
        por_tipo[linea.tipo_iva] += linea.importe

    desglose = []
    for tipo in sorted(por_tipo, reverse=True):
        base_tramo = redondear(por_tipo[tipo])
        cuota_tramo = redondear(base_tramo * tipo / Decimal("100"))
        desglose.append(TramoIVA(tipo=tipo, base=base_tramo, cuota=cuota_tramo))

    base = redondear(sum((t.base for t in desglose), Decimal("0")))
    cuota = redondear(sum((t.cuota for t in desglose), Decimal("0")))
    return Totales(
        base=base,
        cuota_iva=cuota,
        total=redondear(base + cuota),
        desglose=tuple(desglose),
    )


def desde_base(base, tipo_iva=IVA_GENERAL):
    """
    Totales a partir de una base imponible ya conocida.

    La columna `Factura.total` guarda la base imponible, no el total: es el
    defecto 01. Mientras la fase 2 no separe `base`, `tipo_iva` e
    `importe_total` en columnas propias, el listado necesita calcular el total
    a partir de ese valor sin releer las líneas de cada factura.

    Pasa por la misma función que el resto del programa, así que la pantalla y
    el papel no pueden discrepar.
    """
    base = redondear(base)
    tipo_iva = a_decimal(tipo_iva)
    cuota = redondear(base * tipo_iva / Decimal("100"))
    return Totales(
        base=base,
        cuota_iva=cuota,
        total=redondear(base + cuota),
        desglose=(TramoIVA(tipo=tipo_iva, base=base, cuota=cuota),),
    )


def desde_detalles(detalles, tipo_iva=IVA_GENERAL):
    """
    Construye las líneas a partir de las filas de `Detalle_linea`.

    Acepta las filas de `obtener_detalles_factura`, que se leen por nombre de
    columna, y también las tuplas de la forma antigua
    `(Num_Factura, Num_Linea, cantidad, precio, cod_servicio, descripcion)`,
    para no romper el código que todavía las construya a mano.
    """
    lineas = []
    for fila in detalles:
        claves = set(fila.keys()) if hasattr(fila, "keys") else set()
        if {"NumServicios", "precioPorServicio"} <= claves:
            lineas.append(
                Linea(
                    descripcion=fila["descripcion"] if "descripcion" in claves else "",
                    cantidad=fila["NumServicios"],
                    precio_ud=fila["precioPorServicio"],
                    unidad=fila["unidad"] if "unidad" in claves else "ud",
                    tipo_iva=tipo_iva,
                )
            )
        else:
            lineas.append(
                Linea(
                    descripcion=fila[5] if len(fila) > 5 else "",
                    cantidad=fila[2],
                    precio_ud=fila[3],
                    tipo_iva=tipo_iva,
                )
            )
    return lineas
