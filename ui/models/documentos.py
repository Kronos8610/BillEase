"""
Las columnas de un listado de facturas y de uno de presupuestos.

Son el mismo modelo con dos juegos de columnas: una factura enseña su base y su
total; un presupuesto, en qué estado está y hasta cuándo vale.
"""

from core.cobros import PENDIENTE, VENCIDA, dias_de_retraso, situacion
from core.fechas import a_espanol
from core.models import ACEPTADO, BORRADOR, COBRADA, EMITIDA, ENVIADO, RECHAZADO
from core.money import formatear
from core.quotes import esta_caducado
from core.taxes import desde_base
from ui.models.tabla import DERECHA, Columna, ModeloTabla

CADUCADO = "caducado"

# Cómo se lee cada estado y de qué color se pinta su píldora. El color es el
# nombre de un token del tema, no un `#rrggbb`: en oscuro es otro.
ESTADOS = {
    BORRADOR: ("Borrador", "neutro"),
    ENVIADO: ("Enviado", "aviso"),
    ACEPTADO: ("Aceptado", "ok"),
    RECHAZADO: ("Rechazado", "peligro"),
    CADUCADO: ("Caducado", "peligro"),
    EMITIDA: ("Pendiente", "neutro"),
    PENDIENTE: ("Pendiente", "neutro"),
    COBRADA: ("Cobrada", "ok"),
    VENCIDA: ("Vencida", "peligro"),
}


def estado_de(documento):
    """
    El estado que se enseña.

    Un presupuesto pasado de fecha está caducado, y una factura sin cobrar a
    la que se le ha pasado el vencimiento está vencida. Ninguno de los dos se
    guarda así: se deducen de la fecha, para no tener que repasar la base cada
    mañana moviendo documentos de sitio.
    """
    if documento.es_presupuesto:
        return CADUCADO if esta_caducado(documento) else documento.estado
    return situacion(documento)


def _pista_cobro(documento):
    retraso = dias_de_retraso(documento)
    if retraso:
        return f"Vencía el {a_espanol(documento.vencimiento)} · {retraso} días de retraso"
    if documento.vencimiento:
        return f"Vence el {a_espanol(documento.vencimiento)}"
    return None


def _totales(documento):
    return desde_base(documento.base, documento.tipo_iva)


def _pista(documento):
    totales = _totales(documento)
    return (
        f"Base {formatear(totales.base)} € + IVA {formatear(totales.cuota_iva)} €"
        f" = {formatear(totales.total)} €"
    )


def _nombre(documento):
    return documento.cliente_nombre or "Cliente desconocido"


def _serie(documento):
    return (documento.ejercicio or 0, documento.numero or 0)


COLUMNAS_FACTURAS = (
    Columna("Número", lambda d: d.referencia, orden=_serie, peso=2, fuerte=True),
    Columna("Fecha", lambda d: a_espanol(d.fecha), orden=lambda d: d.fecha, peso=2),
    Columna("Cliente", _nombre, peso=5),
    Columna("Base", lambda d: f"{formatear(_totales(d).base)} €",
            orden=lambda d: _totales(d).base, alineacion=DERECHA, peso=2, pista=_pista),
    Columna("Total", lambda d: f"{formatear(_totales(d).total)} €",
            orden=lambda d: _totales(d).total, alineacion=DERECHA, peso=2,
            fuerte=True, pista=_pista),
    # Emitir no es cobrar: esta columna es la que se mira en enero.
    Columna("Cobro", lambda d: ESTADOS[estado_de(d)][0],
            orden=lambda d: (d.vencimiento or "9999", ESTADOS[estado_de(d)][0]),
            estado=lambda d: ESTADOS[estado_de(d)][1], peso=2, pista=_pista_cobro),
)

COLUMNAS_PRESUPUESTOS = (
    Columna("Número", lambda d: d.referencia, orden=_serie, peso=2, fuerte=True),
    Columna("Fecha", lambda d: a_espanol(d.fecha), orden=lambda d: d.fecha, peso=2),
    Columna("Cliente", _nombre, peso=5),
    Columna("Estado", lambda d: ESTADOS[estado_de(d)][0],
            orden=lambda d: ESTADOS[estado_de(d)][0],
            estado=lambda d: ESTADOS[estado_de(d)][1], peso=2,
            pista=lambda d: f"Válido hasta {a_espanol(d.validez)}" if d.validez else None),
    Columna("Total", lambda d: f"{formatear(_totales(d).total)} €",
            orden=lambda d: _totales(d).total, alineacion=DERECHA, peso=2,
            fuerte=True, pista=_pista),
)


def modelo_facturas(documentos=(), parent=None):
    return ModeloTabla(COLUMNAS_FACTURAS, documentos, parent)


def modelo_presupuestos(documentos=(), parent=None):
    return ModeloTabla(COLUMNAS_PRESUPUESTOS, documentos, parent)
