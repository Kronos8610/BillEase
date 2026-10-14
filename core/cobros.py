"""
El cobro de una factura.

Emitir no es cobrar. Una factura emitida está pendiente hasta que el dinero
entra, y si se le pasa el vencimiento sin cobrarse está vencida —que es la
información que de verdad se mira en enero, cuando hay que reclamar.

El estado «vencida» no se guarda: se deduce de la fecha de vencimiento y de si
está cobrada o no. Guardarlo obligaría a repasar la base cada mañana para
mover de sitio las que se hubieran pasado de plazo.

Este módulo no toca la base de datos ni sabe que existe Qt: decide qué estado
tiene una factura y qué cambios son legítimos.
"""

from core.fechas import hoy_iso
from core.models import COBRADA, EMITIDA

PENDIENTE = "pendiente"
VENCIDA = "vencida"

# Una factura se cobra, y un cobro se puede deshacer: un recibo devuelto
# existe, y la factura vuelve a estar pendiente.
TRANSICIONES = {
    EMITIDA: (COBRADA,),
    COBRADA: (EMITIDA,),
}


def esta_cobrada(documento):
    return not documento.es_presupuesto and documento.estado == COBRADA


def esta_vencida(documento, hoy=None):
    """¿Se le ha pasado el vencimiento a una factura sin cobrar?"""
    if documento.es_presupuesto or esta_cobrada(documento):
        return False
    if not documento.vencimiento:
        return False
    return documento.vencimiento < (hoy or hoy_iso())


def situacion(documento, hoy=None):
    """`cobrada`, `vencida` o `pendiente`. Es lo que se enseña en la lista."""
    if documento.es_presupuesto:
        return documento.estado
    if esta_cobrada(documento):
        return COBRADA
    return VENCIDA if esta_vencida(documento, hoy) else PENDIENTE


def dias_de_retraso(documento, hoy=None):
    """Cuántos días lleva vencida. Cero si no lo está."""
    from datetime import date

    if not esta_vencida(documento, hoy):
        return 0
    try:
        vencio = date.fromisoformat(documento.vencimiento)
        referencia = date.fromisoformat(hoy or hoy_iso())
    except ValueError:
        return 0
    return (referencia - vencio).days


def puede_pasar_a(documento, estado):
    """¿Es legítimo este cambio de estado de cobro?"""
    if documento.es_presupuesto:
        return False
    return estado in TRANSICIONES.get(documento.estado, ())


def reparto(documentos, hoy=None):
    """
    Cuánto hay cobrado, pendiente y vencido, en euros.

    Es el resumen que encabeza la pantalla: sumar la columna a mano con
    doscientas facturas no es razonable.
    """
    from core.money import a_decimal

    totales = {COBRADA: a_decimal(0), PENDIENTE: a_decimal(0), VENCIDA: a_decimal(0)}
    cuantas = {COBRADA: 0, PENDIENTE: 0, VENCIDA: 0}
    for documento in documentos:
        if documento.es_presupuesto:
            continue
        donde = situacion(documento, hoy)
        totales[donde] += documento.importe_total
        cuantas[donde] += 1
    return {"importes": totales, "documentos": cuantas}
