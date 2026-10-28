"""
El diccionario que espera el generador de PDF, armado desde la base.

Vivía dentro del botón «Generar PDF» del listado. Al añadir la vista previa
habría hecho falta escribirlo dos veces, y dos copias de lo mismo es una que
se queda atrás: la factura impresa y la de la pantalla enseñarían cosas
distintas el día que se añada un campo.

Aquí no se sabe de Qt ni de SQL: entran tres objetos del modelo y sale el
diccionario que describe `documents.invoice_pdf`.
"""

from core.fechas import a_espanol


def datos_de(documento, cliente, emisor):
    """
    El documento, su cliente y el emisor, en el formato que pide el PDF.

    La dirección de la obra y las observaciones salen solo si las hay: el
    generador se las salta cuando llegan vacías.
    """
    return {
        "tipo": documento.tipo,
        "numero": documento.referencia,
        "fecha": a_espanol(documento.fecha),
        "emisor": {
            "nombre": emisor.nombre_completo,
            "nif": emisor.nif,
            "direccion": emisor.direccion,
            "poblacion": emisor.codigo_postal,
            "telefono": emisor.telefono,
            "email": emisor.email,
            "logotipo": emisor.logotipo,
            "entidad": emisor.entidad,
            "iban": emisor.iban,
        },
        "cliente": {
            "nombre": cliente.nombre,
            "nif": cliente.nif,
            "direccion": cliente.direccion,
            "poblacion": cliente.codigo_postal,
            "telefono": cliente.telefono,
            "email": cliente.email,
        },
        "obra": documento.direccion_obra,
        "lineas": documento.lineas,
        "nota": documento.observaciones,
    }
