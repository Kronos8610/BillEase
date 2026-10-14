"""
La ventana: navegación a la izquierda, contenido a la derecha.

Sustituye a `aplication.py`. Los cambios que se ven:

- **Iconos propios en lugar de emojis.** Un emoji lo dibuja la fuente del
  sistema y sale distinto en cada máquina; estos son trazos SVG del color del
  tema (`ui/iconos.py`).
- **Se lee.** El menú anterior escribía en morado sobre morado: 1,49:1 de
  contraste, cuando lo legible empieza en 4,5:1 (defecto 13).
- **Las pantallas se crean cuando se abren**, no las cuatro al arrancar.
- **Atajos**: `Ctrl+N` crea lo de la pantalla en la que estás, `Ctrl+F` busca,
  `Esc` limpia la búsqueda, `Ctrl+1/2/3` salta de sección.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import theme
from core.models import PRESUPUESTO
from ui import iconos
from ui.views.listado import CLIENTES, FACTURAS, PRESUPUESTOS

# (sección, icono, atajo)
SECCIONES = (
    (FACTURAS, "factura", "Ctrl+1"),
    (PRESUPUESTOS, "presupuesto", "Ctrl+2"),
    (CLIENTES, "clientes", "Ctrl+3"),
)


class Navegacion(QWidget):
    """La columna de la izquierda: marca, secciones y tema."""

    def __init__(self, al_elegir, al_cambiar_tema, parent=None):
        super().__init__(parent)
        self.setObjectName("Lateral")
        self.botones = {}

        columna = QVBoxLayout(self)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(0)

        marca = QLabel("BillEase")
        marca.setObjectName("Marca")
        columna.addWidget(marca)

        columna.addWidget(self._rotulo("DOCUMENTOS"))

        for nombre, icono, atajo in SECCIONES:
            if nombre == CLIENTES:
                columna.addWidget(self._rotulo("DIRECTORIO"))

            boton = QPushButton(f"  {nombre}")
            boton.setObjectName("Navegacion")
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setIcon(iconos.icono(icono))
            boton.setIconSize(iconos.medida())
            boton.setMinimumHeight(38)
            boton.setToolTip(f"{nombre}  ({atajo})")
            boton.setProperty("activo", "false")
            boton.clicked.connect(lambda _=False, n=nombre: al_elegir(n))
            columna.addWidget(boton)
            self.botones[nombre] = boton

        columna.addStretch()

        linea = QFrame()
        linea.setObjectName("Separador")
        columna.addWidget(linea)

        self.tema = QPushButton("  Cambiar tema")
        self.tema.setObjectName("Navegacion")
        self.tema.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tema.setIcon(iconos.icono("ajustes"))
        self.tema.setIconSize(iconos.medida())
        self.tema.setMinimumHeight(38)
        self.tema.setToolTip("Claro u oscuro. Al arrancar sigue al de Windows.")
        self.tema.clicked.connect(al_cambiar_tema)
        columna.addWidget(self.tema)

        pie = QLabel("Facturación para autónomos")
        pie.setObjectName("MarcaPie")
        columna.addWidget(pie)

    def _rotulo(self, texto):
        marca = QLabel(texto)
        marca.setObjectName("SeccionLateral")
        return marca

    def marcar(self, nombre):
        """Señala la sección abierta. El color lo pone la hoja de estilos."""
        for seccion, boton in self.botones.items():
            boton.setProperty("activo", "true" if seccion == nombre else "false")
            # Qt no vuelve a aplicar la hoja al cambiar una propiedad si no se
            # le pide: sin esto el realce se quedaría en la primera sección.
            boton.style().unpolish(boton)
            boton.style().polish(boton)

    def repintar_iconos(self):
        """Tras cambiar de tema, los iconos se piden otra vez con el color nuevo."""
        for nombre, icono, _ in SECCIONES:
            self.botones[nombre].setIcon(iconos.icono(icono))
        self.tema.setIcon(iconos.icono("ajustes"))


class VentanaPrincipal(QWidget):
    """La ventana de la aplicación."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Ventana")
        self.setWindowTitle("BillEase")
        self.setMinimumSize(1060, 680)
        self.resize(1280, 800)

        self.paginas = QStackedWidget()
        self._creadas = {}

        self.navegacion = Navegacion(self.ir_a, self.cambiar_tema, self)

        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        fila.addWidget(self.navegacion)
        fila.addWidget(self.paginas, 1)

        for nombre, _, atajo in SECCIONES:
            QShortcut(QKeySequence(atajo), self, lambda n=nombre: self.ir_a(n))
        QShortcut(QKeySequence.StandardKey.New, self, self.nuevo)

        self.ir_a(FACTURAS)
        theme.activar_mica(self)

    # ───────────────────────────── navegación ─────────────────────────────

    def pagina(self, nombre):
        """
        Crea la pantalla la primera vez que se abre.

        Antes se construían las cuatro al arrancar, con sus consultas, aunque
        el usuario no llegara a abrirlas.
        """
        if nombre not in self._creadas:
            from ui.views.listado import Listado

            pantalla = Listado(nombre, self)
            self._creadas[nombre] = pantalla
            self.paginas.addWidget(pantalla)
        return self._creadas[nombre]

    def ir_a(self, nombre, nuevo=False):
        pantalla = self.pagina(nombre)
        self.paginas.setCurrentWidget(pantalla)
        self.navegacion.marcar(nombre)
        pantalla.cargar()
        if nuevo:
            pantalla.nuevo_elemento()
        return pantalla

    @property
    def seccion(self):
        for nombre, pantalla in self._creadas.items():
            if pantalla is self.paginas.currentWidget():
                return nombre
        return FACTURAS

    def nuevo(self):
        """`Ctrl+N`: lo que toque según dónde estés."""
        pantalla = self.paginas.currentWidget()
        if hasattr(pantalla, "nuevo_elemento"):
            pantalla.nuevo_elemento()

    def nuevo_documento(self, tipo):
        """Crear un documento desde fuera, por ejemplo al terminar el alta."""
        return self.ir_a(PRESUPUESTOS if tipo == PRESUPUESTO else FACTURAS, nuevo=True)

    # ───────────────────────────── tema ─────────────────────────────

    def cambiar_tema(self):
        from PyQt6.QtWidgets import QApplication

        theme.alternar(QApplication.instance())
        self.navegacion.repintar_iconos()
        self.navegacion.marcar(self.seccion)
        for pantalla in self._creadas.values():
            pantalla.repintar_iconos()
        theme.activar_mica(self)
        return theme.modo_actual()
