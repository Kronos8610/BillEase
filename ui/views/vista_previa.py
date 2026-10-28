"""
La factura en pantalla antes de salir por la impresora.

Hasta ahora el único modo de ver cómo quedaba una factura era generarla,
buscar el fichero y abrirlo con el lector de PDF. Si había una errata —un
concepto cortado, el logotipo torcido, un IVA que no era— había que volver al
editor, corregir, generar otra vez y repetir el paseo.

Lo que se enseña aquí **es** el PDF, no un dibujo parecido: se genera el
fichero de verdad y se pinta con el motor de PDF de Qt. Así no hay dos
maquetadores que puedan discrepar, que es como se acaba enseñando en pantalla
algo distinto de lo que se imprime.

El PDF se maqueta **en memoria** y no toca el disco. La primera versión lo
escribía en la carpeta temporal y lo borraba al cerrar, y en Windows el
borrado fallaba: el motor de PDF no suelta el fichero mientras el documento
está abierto, y `rmtree(ignore_errors=True)` se tragaba el fallo sin decir
nada. Cada vistazo dejaba en %TEMP% una factura con el NIF del cliente y lo
que se le cobra. Sin fichero no hay nada que borrar ni nada que se quede.

Al guardar se escriben esos mismos bytes: no se vuelve a maquetar, porque
entonces lo guardado podría no ser lo que se acaba de mirar.
"""

import io
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QPointF, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from documents.invoice_pdf import generar_documento_pdf
from ui import iconos
from ui.widgets.ventana import agrandable

# Los saltos del zoom. Se sube y se baja por esta escalera en vez de
# multiplicar por 1,25: así el 100 % siempre está, que es el tamaño al que se
# comprueba si una letra se va a leer en el papel.
ZOOMS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)


class ErrorDePrevia(Exception):
    """No se ha podido preparar la vista previa."""


def boton(texto, nombre="", icono="", pista=""):
    control = QPushButton(texto)
    if nombre:
        control.setObjectName(nombre)
    if icono:
        control.setIcon(iconos.icono(icono))
        control.setIconSize(iconos.medida())
    if pista:
        control.setToolTip(pista)
    control.setCursor(Qt.CursorShape.PointingHandCursor)
    control.setMinimumHeight(34)
    return control


class VistaPrevia(QDialog):
    """
    El documento ya maquetado, con su zoom y sus páginas.

    `datos` y `totales` son los mismos que recibe `generar_documento_pdf`, así
    que lo que se ve aquí es exactamente lo que se guarda.
    """

    def __init__(self, datos, totales=None, carpeta="", parent=None):
        super().__init__(parent)
        self.datos = datos
        self.totales = totales
        # Dónde se abre el diálogo de guardar: la carpeta de Ajustes para
        # este tipo de documento, si la hay.
        self.carpeta = carpeta
        self.referencia = str(datos.get("numero", "documento")) or "documento"
        es_presupuesto = datos.get("tipo") == "presupuesto"
        self.rotulo = "Presupuesto" if es_presupuesto else "Factura"

        self.setWindowTitle(f"Vista previa · {self.rotulo} {self.referencia}")
        self.setModal(True)
        self.setMinimumSize(760, 620)
        agrandable(self, 1080, 960)

        self.pdf, self._paginas = self._generar()

        # El búfer se queda con una copia de los bytes —`setData`— y no con
        # un puntero a los de fuera: `QBuffer(QByteArray(...))` guarda la
        # dirección de un QByteArray temporal que Python destruye acto
        # seguido, y el documento se carga vacío sin decir nada. Además
        # tiene que seguir vivo mientras el documento lo use, de ahí que sea
        # hijo de la ventana.
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(self.pdf))
        self._buffer.open(QBuffer.OpenModeFlag.ReadOnly)

        # Se mira el estado y no lo que devuelve `load`: cargando desde un
        # dispositivo no devuelve nada, así que compararlo con un error da
        # siempre «ha fallado».
        self.documento = QPdfDocument(self)
        self.documento.load(self._buffer)
        if self.documento.status() != QPdfDocument.Status.Ready:
            raise ErrorDePrevia(
                "El PDF se ha maquetado pero no se ha podido abrir para enseñarlo."
            )

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._barra())
        raiz.addWidget(self._lienzo(), 1)
        raiz.addWidget(self._pie())

        QShortcut(QKeySequence.StandardKey.ZoomIn, self, self.acercar)
        QShortcut(QKeySequence.StandardKey.ZoomOut, self, self.alejar)
        QShortcut(QKeySequence("Ctrl+0"), self, self.ajustar)
        QShortcut(QKeySequence.StandardKey.Save, self, self.guardar)
        QShortcut(QKeySequence("Ctrl+S"), self, self.guardar)

    # ───────────────────────────── montaje ─────────────────────────────

    def _generar(self):
        """Maqueta el PDF en memoria. Devuelve `(bytes, páginas)`."""
        memoria = io.BytesIO()
        try:
            resultado = generar_documento_pdf(
                self.datos, memoria, totales=self.totales
            )
        except Exception as e:                                   # noqa: BLE001
            raise ErrorDePrevia(f"No se ha podido maquetar el documento: {e}") from e
        return memoria.getvalue(), resultado["paginas"]

    def _barra(self):
        barra = QWidget()
        fila = QHBoxLayout(barra)
        fila.setContentsMargins(16, 12, 16, 12)
        fila.setSpacing(8)

        self.titulo = QLabel(f"{self.rotulo} {self.referencia}")
        self.titulo.setObjectName("Subtitulo")
        fila.addWidget(self.titulo)
        fila.addStretch()

        self.boton_alejar = boton("", "Sutil", "menos", "Alejar (Ctrl+−)")
        self.boton_alejar.clicked.connect(self.alejar)
        self.boton_alejar.setFixedWidth(38)
        fila.addWidget(self.boton_alejar)

        self.etiqueta_zoom = QLabel("100 %")
        self.etiqueta_zoom.setObjectName("Etiqueta")
        self.etiqueta_zoom.setMinimumWidth(48)
        self.etiqueta_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fila.addWidget(self.etiqueta_zoom)

        self.boton_acercar = boton("", "Sutil", "mas", "Acercar (Ctrl++)")
        self.boton_acercar.clicked.connect(self.acercar)
        self.boton_acercar.setFixedWidth(38)
        fila.addWidget(self.boton_acercar)

        self.boton_ajustar = boton("Ajustar", "Sutil", "", "Toda la página (Ctrl+0)")
        self.boton_ajustar.clicked.connect(self.ajustar)
        fila.addWidget(self.boton_ajustar)

        self.boton_guardar = boton("Guardar PDF…", "Primario", "pdf", "Ctrl+G")
        self.boton_guardar.clicked.connect(self.guardar)
        fila.addWidget(self.boton_guardar)
        return barra

    def _lienzo(self):
        self.vista = QPdfView(self)
        self.vista.setDocument(self.documento)
        self.vista.setPageMode(QPdfView.PageMode.MultiPage)
        self.vista.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.vista.pageNavigator().currentPageChanged.connect(self._pintar_pie)
        self.vista.zoomFactorChanged.connect(lambda _: self._pintar_zoom())
        return self.vista

    def _pie(self):
        pie = QWidget()
        fila = QHBoxLayout(pie)
        fila.setContentsMargins(16, 10, 16, 12)
        fila.setSpacing(8)

        self.boton_anterior = boton("", "Sutil", "", "Página anterior")
        self.boton_anterior.setText("◀")
        self.boton_anterior.setFixedWidth(38)
        self.boton_anterior.clicked.connect(lambda: self.ir_a(self.pagina() - 1))
        self.boton_siguiente = boton("", "Sutil", "", "Página siguiente")
        self.boton_siguiente.setText("▶")
        self.boton_siguiente.setFixedWidth(38)
        self.boton_siguiente.clicked.connect(lambda: self.ir_a(self.pagina() + 1))

        self.etiqueta_pagina = QLabel("")
        self.etiqueta_pagina.setObjectName("Etiqueta")

        fila.addWidget(self.boton_anterior)
        fila.addWidget(self.boton_siguiente)
        fila.addWidget(self.etiqueta_pagina)
        fila.addStretch()

        cerrar = boton("Cerrar", "Sutil")
        cerrar.clicked.connect(self.reject)
        fila.addWidget(cerrar)

        self._pintar_pie()
        self._pintar_zoom()
        return pie

    # ───────────────────────────── páginas ─────────────────────────────

    def pagina(self):
        """La página que se está mirando, empezando en cero."""
        return self.vista.pageNavigator().currentPage()

    def ir_a(self, pagina):
        pagina = max(0, min(int(pagina), self._paginas - 1))
        self.vista.pageNavigator().jump(pagina, QPointF(), 0)

    def _pintar_pie(self, *_):
        self.etiqueta_pagina.setText(
            f"Página {self.pagina() + 1} de {self._paginas}"
        )
        self.boton_anterior.setEnabled(self.pagina() > 0)
        self.boton_siguiente.setEnabled(self.pagina() < self._paginas - 1)

    # ─────────────────────────────── zoom ───────────────────────────────

    def ajustada(self):
        return self.vista.zoomMode() == QPdfView.ZoomMode.FitInView

    def _pintar_zoom(self):
        """
        Qué poner donde iría el porcentaje.

        Mientras la página está ajustada no se enseña ninguno: con el modo
        «ajustar», Qt deja `zoomFactor()` en 1,0 aunque la página se esté
        viendo al 70 %, y un número que no es verdad es peor que ninguno.
        """
        self.etiqueta_zoom.setText(
            "Ajustada" if self.ajustada() else f"{round(self.vista.zoomFactor() * 100)} %"
        )

    def _mover_zoom(self, paso):
        # Desde «ajustada» el primer toque lleva al 100 %, se haya pulsado el
        # más o el menos: es el tamaño del papel de verdad, y desde ahí la
        # escalera ya sube y baja como es de esperar.
        if self.ajustada():
            self.vista.setZoomMode(QPdfView.ZoomMode.Custom)
            self.vista.setZoomFactor(1.0)
            self._pintar_zoom()
            return

        actual = self.vista.zoomFactor()
        escalera = ZOOMS if paso > 0 else tuple(reversed(ZOOMS))
        siguiente = next(
            (z for z in escalera if (z > actual + 0.01 if paso > 0 else z < actual - 0.01)),
            actual,
        )
        self.vista.setZoomFactor(siguiente)
        self._pintar_zoom()

    def acercar(self):
        self._mover_zoom(+1)

    def alejar(self):
        self._mover_zoom(-1)

    def ajustar(self):
        """La página entera dentro de la ventana."""
        self.vista.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._pintar_zoom()

    # ───────────────────────────── guardar ─────────────────────────────

    def guardar(self):
        """
        Escribe el PDF que se está mirando donde diga el usuario.

        Se escriben los bytes que ya están en memoria, no se vuelve a
        maquetar: lo que se guarda tiene que ser lo mismo que se acaba de
        ver, hasta la última coma.
        """
        nombre = f"{self.referencia}.pdf"
        if self.carpeta and Path(self.carpeta).is_dir():
            nombre = str(Path(self.carpeta) / nombre)
        destino, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", nombre, "PDF (*.pdf)"
        )
        if not destino:
            return None

        try:
            Path(destino).write_bytes(self.pdf)
        except OSError as e:
            QMessageBox.critical(
                self, "No se pudo guardar",
                f"{self.referencia} no se ha podido escribir en {destino}.\n\n"
                f"Motivo: {e}",
            )
            return None

        QMessageBox.information(
            self, "PDF guardado",
            f"{self.rotulo} {self.referencia} · "
            f"{self._paginas} página{'s' if self._paginas != 1 else ''}\n{destino}",
        )
        self.guardado = destino
        return destino

