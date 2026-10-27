"""
El cobro de una factura.

Emitir no es cobrar. Una factura emitida está pendiente hasta que el dinero
entra, y entonces está cobrada. No hay más estados: aquí no se trabaja con
plazos de vencimiento, así que una factura no «se pasa de fecha» ni hay nada
que repasar cada mañana.

Este módulo no toca la base de datos ni sabe que existe Qt: decide qué estado
tiene una factura y qué cambios son legítimos.
"""

from core.models import COBRADA, EMITIDA

PENDIENTE = "pendiente"

# Una factura se cobra, y un cobro se puede deshacer: un recibo devuelto
# existe, y la factura vuelve a estar pendiente.
TRANSICIONES = {
    EMITIDA: (COBRADA,),
    COBRADA: (EMITIDA,),
}


def esta_cobrada(documento):
    return not documento.es_presupuesto and documento.estado == COBRADA


def situacion(documento):
    """`cobrada` o `pendiente`. Es lo que se enseña en la lista."""
    if documento.es_presupuesto:
        return documento.estado
    return COBRADA if esta_cobrada(documento) else PENDIENTE


def puede_pasar_a(documento, estado):
    """¿Es legítimo este cambio de estado de cobro?"""
    if documento.es_presupuesto:
        return False
    return estado in TRANSICIONES.get(documento.estado, ())


def reparto(documentos):
    """
    Cuánto hay cobrado y cuánto pendiente, en euros.

    Es el resumen que encabeza la pantalla: sumar la columna a mano con
    doscientas facturas no es razonable.
    """
    from core.money import a_decimal

    totales = {COBRADA: a_decimal(0), PENDIENTE: a_decimal(0)}
    cuantas = {COBRADA: 0, PENDIENTE: 0}
    for documento in documentos:
        if documento.es_presupuesto:
            continue
        donde = situacion(documento)
        totales[donde] += documento.importe_total
        cuantas[donde] += 1
    return {"importes": totales, "documentos": cuantas}
