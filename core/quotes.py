"""
Presupuestos.

Un presupuesto no tiene valor contable: es una oferta con fecha de caducidad.
Cuando el cliente la acepta, se convierte en factura, y ahí sí entra en la
serie de facturación y en los libros.

Este módulo no toca la base de datos: decide qué se puede hacer y qué sale de
una conversión. Quien guarda es el repositorio.
"""

from datetime import date, timedelta

from core.fechas import a_iso, hoy_iso
from core.models import (
    ACEPTADO,
    BORRADOR,
    EMITIDA,
    ENVIADO,
    FACTURA,
    PRESUPUESTO,
    RECHAZADO,
    Documento,
)

DIAS_VALIDEZ = 30
DIAS_VENCIMIENTO = 30

# Un presupuesto se envía, y desde ahí lo aceptan o lo rechazan. Un rechazado
# se puede volver a enviar: el cliente cambia de idea más veces de las que uno
# querría.
TRANSICIONES = {
    BORRADOR: (ENVIADO,),
    ENVIADO: (ACEPTADO, RECHAZADO),
    ACEPTADO: (),
    RECHAZADO: (ENVIADO,),
}


def sumar_dias(fecha_iso, dias):
    """Fecha ISO más N días, en ISO."""
    if not fecha_iso:
        return ""
    try:
        base = date.fromisoformat(a_iso(fecha_iso))
    except ValueError:
        return ""
    return (base + timedelta(days=dias)).isoformat()


def validez_por_defecto(fecha_iso=None):
    return sumar_dias(fecha_iso or hoy_iso(), DIAS_VALIDEZ)


def vencimiento_por_defecto(fecha_iso=None):
    return sumar_dias(fecha_iso or hoy_iso(), DIAS_VENCIMIENTO)


def esta_caducado(documento, hoy=None):
    """¿Se le ha pasado el plazo a este presupuesto sin respuesta?"""
    if not documento.es_presupuesto or not documento.validez:
        return False
    if documento.estado in (ACEPTADO, RECHAZADO):
        return False
    return documento.validez < (hoy or hoy_iso())


def puede_pasar_a(documento, estado):
    """¿Es legítimo este cambio de estado?"""
    if not documento.es_presupuesto:
        return False
    return estado in TRANSICIONES.get(documento.estado, ())


def puede_convertirse(documento):
    """
    Solo se factura un presupuesto aceptado, y solo una vez.

    Facturar dos veces el mismo presupuesto es cobrar dos veces el mismo
    trabajo, así que el repositorio comprueba además que no tenga ya factura.
    """
    return documento.es_presupuesto and documento.estado == ACEPTADO


def a_factura(presupuesto, fecha=None):
    """
    La factura que sale de un presupuesto aceptado.

    Copia líneas, importes y cliente. El número no se decide aquí: lo asigna la
    serie de facturación cuando se guarda.
    """
    if not puede_convertirse(presupuesto):
        raise ValueError(
            f"Solo se puede facturar un presupuesto aceptado; este está «{presupuesto.estado}»."
        )

    fecha_emision = a_iso(fecha) if fecha else hoy_iso()
    return Documento(
        tipo=FACTURA,
        estado=EMITIDA,
        fecha=fecha_emision,
        vencimiento=vencimiento_por_defecto(fecha_emision),
        origen_id=presupuesto.id,
        cliente_id=presupuesto.cliente_id,
        cliente_nombre=presupuesto.cliente_nombre,
        observaciones=presupuesto.observaciones,
        base=presupuesto.base,
        tipo_iva=presupuesto.tipo_iva,
        importe_total=presupuesto.importe_total,
        lineas=presupuesto.lineas,
    )
