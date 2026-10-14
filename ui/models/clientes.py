"""Las columnas del listado de clientes."""

from ui.models.tabla import Columna, ModeloTabla

COLUMNAS_CLIENTES = (
    Columna("Nombre o razón social", lambda c: c.nombre, peso=5, fuerte=True),
    Columna("NIF/CIF", lambda c: c.nif, peso=2),
    Columna("Teléfono", lambda c: c.telefono or "—", peso=2),
    Columna("Correo", lambda c: c.email or "—", peso=4),
    Columna("Código postal", lambda c: c.codigo_postal or "—", peso=2),
)


def modelo_clientes(clientes=(), parent=None):
    return ModeloTabla(COLUMNAS_CLIENTES, clientes, parent)
