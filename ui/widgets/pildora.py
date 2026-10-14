"""
La píldora de estado de la columna «Estado».

Antes el estado era un `QLabel` con el color puesto a mano en cada fila. Aquí
lo dibuja un delegado: la tabla no crea ni un widget por fila, y el color sale
del tema, así que en oscuro se pinta solo del color que toca.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate

import theme
from ui.models.tabla import ROL_ESTADO

ALTO = 22
HOLGURA = 10


class PildoraEstado(QStyledItemDelegate):
    """Pinta el texto de la celda dentro de una cápsula del color del estado."""

    def paint(self, dibujante, opciones, indice):
        color = indice.data(ROL_ESTADO)
        if not color:
            super().paint(dibujante, opciones, indice)
            return

        # El fondo de la fila (alterno, señalado o seleccionado) lo pinta la
        # vista; aquí solo va la píldora encima.
        self.initStyleOption(opciones, indice)
        opciones.text = ""
        estilo = opciones.widget.style() if opciones.widget else None
        if estilo is not None:
            estilo.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, opciones, dibujante, opciones.widget
            )

        texto = indice.data(Qt.ItemDataRole.DisplayRole) or ""
        fuente = QFont(opciones.font)
        fuente.setWeight(QFont.Weight.DemiBold)

        ancho = opciones.fontMetrics.horizontalAdvance(texto) + HOLGURA * 2
        rectangulo = QRectF(
            opciones.rect.left() + 10,
            opciones.rect.center().y() - ALTO / 2 + 1,
            ancho,
            ALTO,
        )

        camino = QPainterPath()
        camino.addRoundedRect(rectangulo, ALTO / 2, ALTO / 2)

        dibujante.save()
        dibujante.setRenderHint(QPainter.RenderHint.Antialiasing)
        dibujante.fillPath(camino, QColor(theme.color(f"{color}_tenue")))
        dibujante.setPen(QColor(theme.color(color)))
        dibujante.setFont(fuente)
        dibujante.drawText(rectangulo, Qt.AlignmentFlag.AlignCenter.value, texto)
        dibujante.restore()

    def sizeHint(self, opciones, indice):
        tamano = super().sizeHint(opciones, indice)
        tamano.setWidth(tamano.width() + HOLGURA * 2)
        return tamano
