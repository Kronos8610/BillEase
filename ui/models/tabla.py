"""
El modelo de tabla del que cuelgan todos los listados.

La versión anterior pintaba cada fila con widgets: un `QWidget` con su
`QHBoxLayout`, cinco `QLabel` y hasta seis `QPushButton`, y lo destruía y
volvía a construir entero en cada `cargar_datos()`. Con las siete facturas de
la demostración eran unos cincuenta widgets; con mil facturas pasaban de siete
mil, y Qt tiene que medir, colocar y pintar todos (defecto 11).

Un `QTableView` sobre un modelo recicla las celdas: pinta las que caben en la
pantalla y ya está, tenga la base siete filas o cien mil. Además trae lo que
antes no había: ordenar pulsando en la cabecera, buscar y seleccionar.

Aquí está la parte que no sabe de facturas: una tabla se declara diciendo qué
columnas tiene y cómo se saca cada valor de un objeto del dominio.
"""

import unicodedata
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

# Roles propios. El de orden devuelve el valor con el que se compara (un
# `Decimal`, una fecha ISO), no el texto que se enseña: así «1.240,00 €» se
# ordena como número y «03/02/2025» como fecha.
ROL_ORDEN = Qt.ItemDataRole.UserRole + 1
ROL_OBJETO = Qt.ItemDataRole.UserRole + 2
ROL_ESTADO = Qt.ItemDataRole.UserRole + 3
ROL_BUSQUEDA = Qt.ItemDataRole.UserRole + 4

DERECHA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
IZQUIERDA = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
CENTRO = Qt.AlignmentFlag.AlignCenter


@dataclass(frozen=True)
class Columna:
    """Una columna: su título y cómo se saca su valor de un objeto."""

    titulo: str
    texto: Callable
    orden: Callable = None          # valor por el que se ordena
    alineacion: object = IZQUIERDA
    peso: int = 1                   # reparto del ancho sobrante
    fuerte: bool = False            # se pinta en negrita
    estado: Callable = None         # si devuelve algo, se pinta como píldora
    pista: Callable = None          # texto emergente

    def valor_orden(self, objeto):
        return (self.orden or self.texto)(objeto)


def sin_tildes(texto):
    """«Pérez» y «perez» son lo mismo cuando uno busca."""
    descompuesto = unicodedata.normalize("NFKD", str(texto).casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


class ModeloTabla(QAbstractTableModel):
    """Un listado de objetos del dominio, con sus columnas."""

    def __init__(self, columnas, filas=(), parent=None):
        super().__init__(parent)
        self.columnas = tuple(columnas)
        self._filas = list(filas)

    # ─────────────────────────── lo que pide Qt ───────────────────────────

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columnas)

    def data(self, indice, rol=Qt.ItemDataRole.DisplayRole):
        if not indice.isValid():
            return None
        objeto = self._filas[indice.row()]
        columna = self.columnas[indice.column()]

        if rol == Qt.ItemDataRole.DisplayRole:
            return columna.texto(objeto)
        if rol == Qt.ItemDataRole.TextAlignmentRole:
            return columna.alineacion
        if rol == Qt.ItemDataRole.ToolTipRole:
            return columna.pista(objeto) if columna.pista else None
        if rol == ROL_ORDEN:
            return columna.valor_orden(objeto)
        if rol == ROL_OBJETO:
            return objeto
        if rol == ROL_ESTADO:
            return columna.estado(objeto) if columna.estado else None
        if rol == ROL_BUSQUEDA:
            return sin_tildes(" ".join(str(c.texto(objeto)) for c in self.columnas))
        if rol == Qt.ItemDataRole.FontRole and columna.fuerte:
            from PyQt6.QtGui import QFont

            fuente = QFont()
            fuente.setWeight(QFont.Weight.DemiBold)
            return fuente
        return None

    def headerData(self, seccion, orientacion, rol=Qt.ItemDataRole.DisplayRole):
        if orientacion != Qt.Orientation.Horizontal:
            return None
        if rol == Qt.ItemDataRole.DisplayRole:
            return self.columnas[seccion].titulo
        if rol == Qt.ItemDataRole.TextAlignmentRole:
            return self.columnas[seccion].alineacion
        return None

    # ─────────────────────────── uso propio ───────────────────────────

    def poner(self, filas):
        """Cambia el contenido entero. Una sola señal, un solo repintado."""
        self.beginResetModel()
        self._filas = list(filas)
        self.endResetModel()

    def objeto(self, indice):
        if not indice.isValid():
            return None
        return self._filas[indice.row()]

    @property
    def elementos(self):
        return tuple(self._filas)


class FiltroTexto(QSortFilterProxyModel):
    """
    La búsqueda: mira todas las columnas de la fila, sin tildes ni mayúsculas.

    Y el orden: compara por `ROL_ORDEN`, de modo que los importes se ordenan
    como importes y las fechas como fechas, no como texto.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(ROL_ORDEN)
        self.setDynamicSortFilter(True)
        self._buscado = ""

    def buscar(self, texto):
        self._buscado = sin_tildes(texto.strip())
        self.invalidateFilter()

    @property
    def buscado(self):
        return self._buscado

    def filterAcceptsRow(self, fila, padre):
        if not self._buscado:
            return True
        indice = self.sourceModel().index(fila, 0, padre)
        donde = self.sourceModel().data(indice, ROL_BUSQUEDA) or ""
        return all(trozo in donde for trozo in self._buscado.split())

    def lessThan(self, uno, otro):
        a = self.sourceModel().data(uno, ROL_ORDEN)
        b = self.sourceModel().data(otro, ROL_ORDEN)
        if a is None or b is None:
            return a is None
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)
