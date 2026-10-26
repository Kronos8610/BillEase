"""
Los iconos de la interfaz, dibujados aquí.

La versión anterior usaba emojis en los botones —🏠 📄 📝 ➕ 🗑—. Un emoji no
es un icono: lo dibuja la fuente del sistema, sale de otro color, de otro
tamaño y de otro estilo en cada máquina, y en una pantalla de facturación
queda como un mensaje de móvil.

Estos son trazos SVG de 24×24, del grosor de los de Windows 11, que se pintan
del color del tema en uso. Al cambiar de claro a oscuro se vuelven a generar
solos, porque el color se resuelve al pedirlos.
"""

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

import theme

# Trazos de 24×24. El color se pone al dibujar.
TRAZOS = {
    "documentos": "M4 4.5h9l4 4V19.5H4zM13 4.5v4.5h4M7 12h7M7 15.5h7",
    "factura": "M5.5 3.5h9l4 4V20.5H5.5zM14.5 3.5v4h4M8 11h8M8 14.5h8M8 18h4",
    "presupuesto": "M5.5 3.5h13v17l-3.2-2-3.3 2-3.3-2-3.2 2zM9 9h6M9 13h6",
    "clientes": "M9 11.5a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4zM3.5 19.5c0-3 2.5-5 5.5-5"
                "s5.5 2 5.5 5M16 6.2a2.6 2.6 0 0 1 0 5M17.5 14.8c1.8.5 3 1.9 3 3.7",
    "buscar": "M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM16 16l4 4",
    "mas": "M12 5v14M5 12h14",
    "menos": "M5 12h14",
    "pdf": "M12 3.5v11M8 11l4 3.5 4-3.5M4.5 17v2.5h15V17",
    "editar": "M4.5 19.5h4L19 9a2.1 2.1 0 0 0-3-3L5.5 16.5zM14.5 7.5l2 2",
    "borrar": "M4.5 6.5h15M9 6.5V4.5h6v2M6.5 6.5l1 13h9l1-13M10 10v6M14 10v6",
    "actualizar": "M20 12a8 8 0 1 1-2.6-5.9M20 4v4.5h-4.5",
    "facturar": "M4.5 12.5l5 5 10-11",
    "aceptar": "M5 12.5l4.5 4.5L19 7",
    "enviar": "M3.5 12 20.5 4l-7 16-2.5-6.5z",
    "rechazar": "M6 6l12 12M18 6 6 18",
    "vacio": "M3.5 13.5h5l1.5 3h4l1.5-3h5M3.5 13.5 6 5h12l2.5 8.5v6h-17zM10 9h4",
    "resumen": "M4 20V9M9.3 20V4M14.7 20v-8M20 20V7M3 20h18",
    "cobrado": "M17.5 8.5A5.5 5.5 0 0 0 8 12a5.5 5.5 0 0 0 9.5 3.5M5 10.5h6M5 13.5h6",
    "copia": "M4.5 7.5c0-1.7 3.4-3 7.5-3s7.5 1.3 7.5 3-3.4 3-7.5 3-7.5-1.3-7.5-3z"
             "M4.5 7.5v9c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-9M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3",
    "exportar": "M12 14.5V3.5M8 7l4-3.5L16 7M4.5 15v4.5h15V15",
    "imagen": "M4.5 4.5h15v15h-15zM4.5 15.5l4.5-4.5 4 4 3-2.5 3.5 3M15 9a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z",
    "restaurar": "M4 12a8 8 0 1 0 2.6-5.9M4 4v4.5h4.5",
    "carpeta": "M3.5 6.5h6l2 2.5h9v10h-17zM3.5 6.5v12.5",
    "candado": "M6 10.5h12v9H6zM8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3M12 14v2.5",
    "llave": "M14.5 9.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0zM13.6 12.2 20 18.6"
             "M17.5 16.1l-1.6 1.6M19.4 18l-1.6 1.6",
    "escudo": "M12 3.5l7 2.5v5.5c0 4-2.9 7.3-7 9-4.1-1.7-7-5-7-9V6zM8.8 12l2.3 2.3L15.6 10",
    "ajustes": "M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z"
               "M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5"
               "M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1 5.3 5.3",
}

PLANTILLA = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
    '<path d="{trazo}" fill="none" stroke="{color}" stroke-width="1.5"'
    ' stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def svg(nombre, color=None):
    """El icono como texto SVG, por si hace falta fuera de Qt."""
    if nombre not in TRAZOS:
        raise KeyError(f"no hay icono «{nombre}»; hay {sorted(TRAZOS)}")
    return PLANTILLA.format(trazo=TRAZOS[nombre], color=color or theme.color("texto"))


def pixmap(nombre, medida=20, color=None, escala=1):
    # El nombre se comprueba antes de abrir el lienzo: un QPainter que se
    # queda a medias por una excepción se lleva el programa por delante.
    dibujo = svg(nombre, color)

    lienzo = QPixmap(int(medida * escala), int(medida * escala))
    lienzo.fill(Qt.GlobalColor.transparent)
    dibujante = QPainter(lienzo)
    try:
        dibujante.setRenderHint(QPainter.RenderHint.Antialiasing)
        QSvgRenderer(QByteArray(dibujo.encode())).render(dibujante)
    finally:
        dibujante.end()
    return lienzo


def icono(nombre, medida=20, color=None):
    """
    El icono listo para un botón, del color del tema.

    No se guarda en caché a propósito: cuando Windows cambia de claro a
    oscuro, la pantalla vuelve a pedir sus iconos y salen del color nuevo.
    """
    marca = QIcon()
    for escala in (1, 2):      # nítido también en pantallas de alta densidad
        marca.addPixmap(pixmap(nombre, medida, color, escala))
    return marca


def medida(px=18):
    return QSize(px, px)
