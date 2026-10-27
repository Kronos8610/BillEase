"""
Presupuestos.

Un presupuesto no tiene valor contable: es una oferta. Cuando el cliente la
acepta, se convierte en factura, y ahí sí entra en la serie de facturación y
en los libros.

No caduca solo: aquí no se trabaja con plazos. Una oferta sigue en pie hasta
que se acepta, se rechaza o se borra, y eso lo decide una persona.

Este módulo no toca la base de datos: decide qué se puede hacer y qué sale de
una conversión. Quien guarda es el repositorio.
"""

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

# Un presupuesto se envía, y desde ahí lo aceptan o lo rechazan. Un rechazado
# se puede volver a enviar: el cliente cambia de idea más veces de las que uno
# querría.
TRANSICIONES = {
    BORRADOR: (ENVIADO,),
    ENVIADO: (ACEPTADO, RECHAZADO),
    ACEPTADO: (),
    RECHAZADO: (ENVIADO,),
}


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
        origen_id=presupuesto.id,
        direccion_obra=presupuesto.direccion_obra,
        cliente_id=presupuesto.cliente_id,
        cliente_nombre=presupuesto.cliente_nombre,
        observaciones=presupuesto.observaciones,
        base=presupuesto.base,
        tipo_iva=presupuesto.tipo_iva,
        importe_total=presupuesto.importe_total,
        lineas=presupuesto.lineas,
    )
