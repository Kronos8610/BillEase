"""
Ventanas que se pueden agrandar.

Las ventanas de crear factura, presupuesto o cliente eran diálogos de tamaño
fijo salvo por el tirador de la esquina: en Windows un diálogo no trae botón
de maximizar, así que para ver una factura de veinte conceptos había que
arrastrar la esquina cada vez.

Aquí se les añade el botón de maximizar, el atajo F11 y un tamaño inicial
cómodo que nunca se sale de la pantalla. Y como una ventana maximizada en un
monitor ancho estiraría los campos hasta hacerlos ilegibles, `centrado` deja
el contenido centrado con un ancho máximo, que es lo que ya hacen las
pantallas principales.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QWidget

# Lo que puede ocupar como mucho una ventana al abrirse, sobre el espacio
# libre de la pantalla. No el 100 %: una ventana que tapa la barra de tareas
# al abrirse parece colgada.
HOLGURA = 0.9


def alternar_tamano(ventana):
    """Maximiza, o devuelve al tamaño anterior si ya estaba maximizada."""
    if ventana.isMaximized():
        ventana.showNormal()
    else:
        ventana.showMaximized()


def _cabe(ventana, ancho, alto):
    """El tamaño pedido, recortado a lo que de verdad hay de pantalla."""
    pantalla = ventana.screen() or QGuiApplication.primaryScreen()
    if pantalla is None:
        return ancho, alto
    libre = pantalla.availableGeometry()
    return (
        min(ancho, int(libre.width() * HOLGURA)),
        min(alto, int(libre.height() * HOLGURA)),
    )


def agrandable(ventana, ancho=0, alto=0):
    """
    Le pone a un diálogo el botón de maximizar y lo abre a un tamaño cómodo.

    `ancho` y `alto` son el tamaño de partida; si no caben en la pantalla se
    recortan. El usuario puede maximizar con el botón del título, con doble
    clic en la barra o con F11.
    """
    ventana.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
    if hasattr(ventana, "setSizeGripEnabled"):
        ventana.setSizeGripEnabled(True)

    atajo = QShortcut(QKeySequence("F11"), ventana)
    atajo.activated.connect(lambda: alternar_tamano(ventana))
    ventana.atajo_maximizar = atajo      # que no se lo lleve el recolector

    if ancho or alto:
        ventana.resize(*_cabe(ventana, ancho, alto))
    return ventana


def centrado(ancho_maximo):
    """
    Un contenedor centrado que no pasa de `ancho_maximo`.

    Devuelve `(envoltorio, contenido)`: el envoltorio se mete en el diseño y
    el contenido es donde va todo lo demás. Sin esto, una ventana maximizada
    en un monitor de 27 pulgadas enseña campos de texto de dos palmos.
    """
    envoltorio = QWidget()
    fila = QHBoxLayout(envoltorio)
    fila.setContentsMargins(0, 0, 0, 0)

    contenido = QWidget()
    contenido.setMaximumWidth(ancho_maximo)
    fila.addStretch(1)
    fila.addWidget(contenido, 100)
    fila.addStretch(1)
    return envoltorio, contenido
