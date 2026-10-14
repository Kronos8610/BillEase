"""
Los resúmenes fiscales: el IVA de cada trimestre y el año entero.

Es lo que un autónomo necesita cuatro veces al año para el modelo 303 y una
para el 390, y hasta ahora había que sacarlo sumando a mano la columna de la
lista. Se puede calcular ahora porque las fechas se guardan en ISO desde la
fase 2: un trimestre es un `BETWEEN` y no una comparación de texto que
mezclaba enero con octubre.

Aquí no se toca la base ni se pinta nada: entran documentos y salen cifras,
calculadas con `core.taxes`, la misma función que usan el listado y el PDF.
Si el papel y el resumen discreparan, el resumen no serviría para nada.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from core.cobros import situacion
from core.fechas import ejercicio_de
from core.models import COBRADA, PRESUPUESTO
from core.money import a_decimal, redondear
from core.taxes import desde_base

# El año fiscal español: cuatro trimestres naturales.
TRIMESTRES = (1, 2, 3, 4)
MESES_DE = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
NOMBRES = {1: "1.º trimestre", 2: "2.º trimestre", 3: "3.er trimestre", 4: "4.º trimestre"}
MODELO = {1: "1T", 2: "2T", 3: "3T", 4: "4T"}


def trimestre_de(iso):
    """A qué trimestre pertenece una fecha ISO. 0 si no se puede saber."""
    partes = str(iso or "").split("-")
    if len(partes) < 2 or not partes[1].isdigit():
        return 0
    mes = int(partes[1])
    if not 1 <= mes <= 12:
        return 0
    return (mes - 1) // 3 + 1


def limites(ejercicio, trimestre):
    """Las dos fechas ISO que acotan un trimestre, ambas incluidas."""
    primero, ultimo = MESES_DE[trimestre]
    dia_final = 31 if ultimo in (3, 12) else 30
    return f"{ejercicio}-{primero:02d}-01", f"{ejercicio}-{ultimo:02d}-{dia_final:02d}"


@dataclass(frozen=True)
class Tramo:
    """Lo facturado en un periodo: cuántas facturas, cuánto y cuánto IVA."""

    etiqueta: str
    trimestre: int = 0
    ejercicio: int = 0
    documentos: int = 0
    base: Decimal = Decimal("0")
    cuota_iva: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    cobrado: Decimal = Decimal("0")
    desde: str = ""
    hasta: str = ""

    @property
    def pendiente(self):
        """Lo emitido que todavía no ha entrado."""
        return redondear(self.total - self.cobrado)

    @property
    def vacio(self):
        return self.documentos == 0


@dataclass(frozen=True)
class Resumen:
    """Un ejercicio entero: sus cuatro trimestres y la suma."""

    ejercicio: int
    trimestres: tuple = field(default_factory=tuple)
    anual: Tramo = None

    def trimestre(self, numero):
        for tramo in self.trimestres:
            if tramo.trimestre == numero:
                return tramo
        return None


def solo_facturas(documentos):
    """Un presupuesto no se declara: es una oferta, no un ingreso."""
    return [d for d in documentos if d.tipo != PRESUPUESTO]


def _sumar(documentos, etiqueta, ejercicio=0, trimestre=0, desde="", hasta=""):
    base = cuota = total = cobrado = a_decimal(0)
    for documento in documentos:
        totales = desde_base(documento.base, documento.tipo_iva)
        base += totales.base
        cuota += totales.cuota_iva
        total += totales.total
        if situacion(documento) == COBRADA:
            cobrado += totales.total
    return Tramo(
        etiqueta=etiqueta,
        trimestre=trimestre,
        ejercicio=ejercicio,
        documentos=len(documentos),
        base=redondear(base),
        cuota_iva=redondear(cuota),
        total=redondear(total),
        cobrado=redondear(cobrado),
        desde=desde,
        hasta=hasta,
    )


def resumen_trimestral(documentos, ejercicio):
    """
    Los cuatro trimestres de un ejercicio, y el año entero.

    Un trimestre sin facturas sale igualmente, con ceros: en el modelo 303
    también hay que presentarlo, y verlo vacío es información.
    """
    facturas = [
        d for d in solo_facturas(documentos) if ejercicio_de(d.fecha) == int(ejercicio)
    ]

    tramos = []
    for numero in TRIMESTRES:
        desde, hasta = limites(int(ejercicio), numero)
        del_trimestre = [d for d in facturas if trimestre_de(d.fecha) == numero]
        tramos.append(_sumar(
            del_trimestre, NOMBRES[numero], int(ejercicio), numero, desde, hasta
        ))

    anual = _sumar(
        facturas, f"Ejercicio {ejercicio}", int(ejercicio), 0,
        f"{ejercicio}-01-01", f"{ejercicio}-12-31",
    )
    return Resumen(ejercicio=int(ejercicio), trimestres=tuple(tramos), anual=anual)


def ejercicios(documentos):
    """Los años con facturas, del más reciente al más antiguo."""
    anios = {ejercicio_de(d.fecha) for d in solo_facturas(documentos)}
    return sorted((a for a in anios if a), reverse=True)


def resumen_por_ejercicio(documentos):
    """Un tramo por año, para ver la evolución de un vistazo."""
    return [
        resumen_trimestral(documentos, ejercicio).anual
        for ejercicio in ejercicios(documentos)
    ]


def por_cliente(documentos, ejercicio=None, limite=0):
    """
    Lo facturado a cada cliente, de más a menos.

    Sirve para el 347 —operaciones con terceros por encima de 3.005,06 €— y
    para saber de quién se vive.
    """
    facturas = solo_facturas(documentos)
    if ejercicio:
        facturas = [d for d in facturas if ejercicio_de(d.fecha) == int(ejercicio)]

    agrupado = {}
    for documento in facturas:
        clave = (documento.cliente_id, documento.cliente_nombre or "Cliente desconocido")
        agrupado.setdefault(clave, []).append(documento)

    tramos = [
        _sumar(suyas, nombre, ejercicio=int(ejercicio or 0))
        for (_id, nombre), suyas in agrupado.items()
    ]
    tramos.sort(key=lambda t: t.total, reverse=True)
    return tramos[:limite] if limite else tramos
