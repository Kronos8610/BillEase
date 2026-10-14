"""Los modelos de los listados: `QTableView` en lugar de filas de widgets."""

from ui.models.clientes import COLUMNAS_CLIENTES, modelo_clientes
from ui.models.documentos import (
    COLUMNAS_FACTURAS,
    COLUMNAS_PRESUPUESTOS,
    ESTADOS,
    estado_de,
    modelo_facturas,
    modelo_presupuestos,
)
from ui.models.tabla import (
    CENTRO,
    DERECHA,
    IZQUIERDA,
    ROL_BUSQUEDA,
    ROL_ESTADO,
    ROL_OBJETO,
    ROL_ORDEN,
    Columna,
    FiltroTexto,
    ModeloTabla,
    sin_tildes,
)

__all__ = [
    "COLUMNAS_CLIENTES", "COLUMNAS_FACTURAS", "COLUMNAS_PRESUPUESTOS", "ESTADOS",
    "CENTRO", "DERECHA", "IZQUIERDA", "Columna", "FiltroTexto", "ModeloTabla",
    "ROL_BUSQUEDA", "ROL_ESTADO", "ROL_OBJETO", "ROL_ORDEN",
    "estado_de", "modelo_clientes", "modelo_facturas", "modelo_presupuestos",
    "sin_tildes",
]
