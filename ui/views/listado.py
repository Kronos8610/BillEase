"""
El listado: facturas, presupuestos o clientes, según de dónde se abra.

Sustituye a `homePage.py`, que construía cada fila con widgets —hasta once por
factura— y los destruía y rehacía enteros en cada recarga. Aquí hay una
`QTableView` sobre un modelo (`ui/models/`): la vista pinta solo las filas que
caben en la pantalla, y con mil facturas cuesta lo mismo que con siete.

Lo que antes no había y ahora sí:

- **Buscar** por cualquier columna, sin tildes ni mayúsculas (`Ctrl+F`).
- **Ordenar** pulsando en el título de una columna; los importes ordenan como
  importes y las fechas como fechas, no como texto.
- **Una barra de acciones** que sabe qué se puede hacer con lo seleccionado, en
  lugar de seis botones repetidos en cada fila.
- **Estados vacíos con una salida**: en lugar de una línea en cursiva, lo que
  hay que hacer y el botón para hacerlo.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)

import theme
from core.cobros import TRANSICIONES as TRANSICIONES_COBRO
from core.models import (
    ACEPTADO,
    COBRADA,
    EMITIDA,
    ENVIADO,
    FACTURA,
    PRESUPUESTO,
    RECHAZADO,
)
from core.money import formatear
from core.quotes import TRANSICIONES
from core.taxes import calcular
from data.repositories import autonomo as repo_autonomo
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from documents.armado import datos_de
from documents.invoice_pdf import generar_documento_pdf
from ui import iconos
from ui.models import (
    ROL_OBJETO,
    FiltroTexto,
    modelo_clientes,
    modelo_facturas,
    modelo_presupuestos,
    repartir,
)
from ui.views.vista_previa import ErrorDePrevia, VistaPrevia
from ui.widgets.pildora import PildoraEstado

FACTURAS = "Facturas"
PRESUPUESTOS = "Presupuestos"
CLIENTES = "Clientes"

TITULOS = {FACTURAS: "Facturas", PRESUPUESTOS: "Presupuestos", CLIENTES: "Clientes"}

VACIOS = {
    FACTURAS: ("Todavía no has emitido ninguna factura",
               "La primera llevará el número 1 de la serie de este ejercicio.",
               "Nueva factura"),
    PRESUPUESTOS: ("Todavía no has hecho ningún presupuesto",
                   "Un presupuesto aceptado se convierte en factura de un clic.",
                   "Nuevo presupuesto"),
    CLIENTES: ("Todavía no tienes clientes",
               "Un documento necesita a quién va dirigido.",
               "Nuevo cliente"),
}

ETIQUETAS_NUEVO = {
    FACTURAS: "Nueva factura",
    PRESUPUESTOS: "Nuevo presupuesto",
    CLIENTES: "Nuevo cliente",
}

NOMBRES_ESTADO = {
    ENVIADO: "Marcar como enviado",
    ACEPTADO: "Marcar como aceptado",
    RECHAZADO: "Marcar como rechazado",
    COBRADA: "Marcar como cobrada",
    EMITIDA: "Volver a pendiente de cobro",
}

ICONOS_ESTADO = {
    ENVIADO: "enviar",
    ACEPTADO: "aceptar",
    RECHAZADO: "rechazar",
    COBRADA: "cobrado",
    EMITIDA: "restaurar",
}

SINGULAR = {FACTURAS: "factura", PRESUPUESTOS: "presupuesto", CLIENTES: "cliente"}


def boton(texto, nombre="Sutil", icono=None, pista=""):
    b = QPushButton(texto)
    b.setObjectName(nombre)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if icono:
        b.setIcon(iconos.icono(icono))
        b.setIconSize(iconos.medida())
    if pista:
        b.setToolTip(pista)
    return b


class Listado(QWidget):
    """Una de las tres listas. La categoría decide columnas, acciones y textos."""

    def __init__(self, categoria=FACTURAS, parent=None):
        super().__init__(parent)
        self.categoria = categoria
        self.es_documento = categoria in (FACTURAS, PRESUPUESTOS)
        self.tipo = PRESUPUESTO if categoria == PRESUPUESTOS else FACTURA
        self._iconos_de_accion = {}

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        # El contenido no se estira sin fin: en una pantalla ancha una línea de
        # tabla de 2.000 píxeles es ilegible (defecto 14).
        centrado = QHBoxLayout()
        centrado.setContentsMargins(0, 0, 0, 0)
        contenido = QWidget()
        contenido.setMaximumWidth(theme.ancho_maximo())
        centrado.addStretch(1)
        centrado.addWidget(contenido, 100)
        centrado.addStretch(1)
        raiz.addLayout(centrado)

        columna = QVBoxLayout(contenido)
        columna.setContentsMargins(32, 28, 32, 28)
        columna.setSpacing(16)

        columna.addLayout(self._cabecera())
        columna.addLayout(self._barra_acciones())

        self._pila = QStackedLayout()
        self._pila.addWidget(self._tabla())
        self._pila.addWidget(self._vacio())
        columna.addLayout(self._pila, 1)

        QShortcut(QKeySequence("Ctrl+F"), self, self.buscador.setFocus)
        QShortcut(QKeySequence("F5"), self, self.cargar)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._limpiar_busqueda)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.vista, self._eliminar)
        if self.es_documento:
            QShortcut(QKeySequence("Ctrl+P"), self, self._previsualizar)

        self.cargar()

    # ───────────────────────────── montaje ─────────────────────────────

    def _cabecera(self):
        self.titulo = QLabel(TITULOS[self.categoria])
        self.titulo.setObjectName("Titulo")

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(self.titulo)

        self.buscador = QLineEdit()
        self.buscador.setObjectName("Buscador")
        self.buscador.setPlaceholderText("Buscar…    Ctrl+F")
        self.buscador.setClearButtonEnabled(True)
        self.buscador.setMinimumHeight(32)
        self._lupa = self.buscador.addAction(
            iconos.icono("buscar", color=theme.color("texto_suave")),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.buscador.textChanged.connect(self._buscar)

        self.nuevo = boton(ETIQUETAS_NUEVO[self.categoria], "Primario", "mas", "Ctrl+N")
        self._iconos_de_accion[self.nuevo] = "mas"
        self.nuevo.setMinimumHeight(32)
        self.nuevo.clicked.connect(self.nuevo_elemento)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addLayout(textos)
        fila.addStretch()
        fila.addWidget(self.buscador)
        fila.addWidget(self.nuevo)
        return fila

    def _barra_acciones(self):
        self.acciones = []
        fila = QHBoxLayout()
        fila.setSpacing(6)

        def anadir(texto, icono, funcion, pista=""):
            b = boton(texto, "Sutil", icono, pista)
            self._iconos_de_accion[b] = icono
            b.clicked.connect(funcion)
            b.setEnabled(False)
            fila.addWidget(b)
            self.acciones.append(b)
            return b

        if self.es_documento:
            self.boton_previa = anadir("Vista previa", "ojo", self._previsualizar,
                                       "Ver cómo queda antes de guardarlo (Ctrl+P)")
            self.boton_pdf = anadir("Generar PDF", "pdf", self._generar_pdf,
                                    "Guarda el documento en PDF")
            self.boton_editar = anadir("Editar", "editar", self._editar,
                                       "También con doble clic en la fila")
        if self.categoria == FACTURAS:
            self.boton_estado = anadir("Cobro", "cobrado", self._menu_estado,
                                       "Marcar la factura como cobrada")
        if self.categoria == PRESUPUESTOS:
            self.boton_estado = anadir("Cambiar estado", "enviar", self._menu_estado)
            self.boton_facturar = anadir("Facturar", "facturar", self._facturar,
                                         "Emite la factura de este presupuesto")
        self.boton_borrar = anadir("Eliminar", "borrar", self._eliminar, "Supr")
        self.boton_borrar.setObjectName("Peligro")

        fila.addStretch()
        self.resumen = QLabel()
        self.resumen.setObjectName("Apunte")
        fila.addWidget(self.resumen)

        actualizar = boton("", "Sutil", "actualizar", "Actualizar (F5)")
        self._iconos_de_accion[actualizar] = "actualizar"
        actualizar.clicked.connect(self.cargar)
        actualizar.setFixedWidth(38)
        fila.addWidget(actualizar)
        return fila

    def _tabla(self):
        constructor = {
            FACTURAS: modelo_facturas,
            PRESUPUESTOS: modelo_presupuestos,
            CLIENTES: modelo_clientes,
        }[self.categoria]
        self.modelo = constructor((), self)
        self.filtro = FiltroTexto(self)
        self.filtro.setSourceModel(self.modelo)

        self.vista = QTableView()
        self.vista.setModel(self.filtro)
        self.vista.setAlternatingRowColors(True)
        self.vista.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.vista.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vista.setSortingEnabled(True)
        # Con seis columnas de números, la rejilla ayuda a seguir la fila:
        # una línea fina entre columnas y entre filas.
        self.vista.setShowGrid(True)
        self.vista.setWordWrap(False)
        self.vista.verticalHeader().setVisible(False)
        self.vista.verticalHeader().setDefaultSectionSize(38)
        self.vista.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.vista.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.vista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.vista.customContextMenuRequested.connect(self._menu_contextual)
        self.vista.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        cabecera = self.vista.horizontalHeader()
        cabecera.setHighlightSections(False)
        cabecera.setSectionsMovable(True)
        cabecera.setStretchLastSection(True)
        cabecera.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for numero, columna in enumerate(self.modelo.columnas):
            if columna.estado:
                self.vista.setItemDelegateForColumn(numero, PildoraEstado(self.vista))

        self.vista.selectionModel().selectionChanged.connect(self._cambio_seleccion)
        self.vista.doubleClicked.connect(self._abrir)
        # El orden de partida: lo más reciente arriba, los clientes por nombre.
        self.vista.sortByColumn(
            0,
            Qt.SortOrder.AscendingOrder if self.categoria == CLIENTES
            else Qt.SortOrder.DescendingOrder,
        )
        return self.vista

    def _vacio(self):
        caja = QFrame()
        caja.setObjectName("Tarjeta")
        columna = QVBoxLayout(caja)
        columna.setSpacing(6)
        columna.addStretch()

        titulo, explicacion, accion = VACIOS[self.categoria]

        self.dibujo_vacio = QLabel()
        self.dibujo_vacio.setPixmap(
            iconos.pixmap("vacio", 56, theme.color("borde_fuerte"))
        )
        self.dibujo_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.vacio_titulo = QLabel(titulo)
        self.vacio_titulo.setObjectName("Subtitulo")
        self.vacio_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.vacio_texto = QLabel(explicacion)
        self.vacio_texto.setObjectName("Apunte")
        self.vacio_texto.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.vacio_boton = boton(accion, "Primario", "mas")
        self._iconos_de_accion[self.vacio_boton] = "mas"
        self.vacio_boton.clicked.connect(self.nuevo_elemento)

        columna.addWidget(self.dibujo_vacio)
        columna.addWidget(self.vacio_titulo)
        columna.addWidget(self.vacio_texto)
        columna.addSpacing(10)
        columna.addWidget(self.vacio_boton, alignment=Qt.AlignmentFlag.AlignCenter)
        columna.addStretch()
        return caja

    def resizeEvent(self, evento):
        """Al cambiar el tamaño, las columnas se reparten según su peso."""
        super().resizeEvent(evento)
        repartir(self.vista)

    def repintar_iconos(self):
        """Al cambiar de tema los iconos se piden otra vez, del color nuevo."""
        for control, nombre in self._iconos_de_accion.items():
            control.setIcon(iconos.icono(nombre))
        self._lupa.setIcon(iconos.icono("buscar", color=theme.color("texto_suave")))
        self.dibujo_vacio.setPixmap(
            iconos.pixmap("vacio", 56, theme.color("borde_fuerte"))
        )

    # ───────────────────────────── datos ─────────────────────────────

    def cargar(self):
        """Relee la lista. Una consulta, un `beginResetModel`, un repintado."""
        if self.categoria == CLIENTES:
            elementos = repo_clientes.listar()
        else:
            elementos = repo_documentos.listar(self.tipo)

        self.modelo.poner(elementos)
        repartir(self.vista)
        self._buscar(self.buscador.text())
        self._cambio_seleccion()

    def _buscar(self, texto):
        self.filtro.buscar(texto)
        self._resumir()

    def _limpiar_busqueda(self):
        if self.buscador.text():
            self.buscador.clear()

    def _resumir(self):
        """El recuento, y qué se enseña cuando no hay nada que enseñar."""
        visibles = self.filtro.rowCount()
        total = self.modelo.rowCount()
        nombre = SINGULAR[self.categoria]

        if visibles == total:
            plural = "s" if total != 1 else ""
            self.resumen.setText(f"{total} {nombre}{plural}")
        else:
            self.resumen.setText(f"{visibles} de {total} {nombre}s")

        if total and visibles:
            self._pila.setCurrentIndex(0)
            return

        if total and not visibles:
            self.vacio_titulo.setText("Ningún resultado")
            self.vacio_texto.setText(
                f"Nada coincide con «{self.buscador.text().strip()}»."
            )
            self.vacio_boton.setVisible(False)
        else:
            titulo, explicacion, _ = VACIOS[self.categoria]
            self.vacio_titulo.setText(titulo)
            self.vacio_texto.setText(explicacion)
            self.vacio_boton.setVisible(True)
        self._pila.setCurrentIndex(1)

    # ───────────────────────────── selección ─────────────────────────────

    def seleccionado(self):
        indices = self.vista.selectionModel().selectedRows()
        if not indices:
            return None
        return self.filtro.data(indices[0], ROL_OBJETO)

    def _transiciones(self, documento):
        """A qué estados puede pasar lo seleccionado, según lo que sea."""
        if documento is None:
            return ()
        if documento.es_presupuesto:
            return TRANSICIONES.get(documento.estado, ())
        return TRANSICIONES_COBRO.get(documento.estado, ())

    def _cambio_seleccion(self, *_):
        elemento = self.seleccionado()
        for accion in self.acciones:
            accion.setEnabled(elemento is not None)

        if self.categoria == CLIENTES or elemento is None:
            return

        self.boton_estado.setEnabled(bool(self._transiciones(elemento)))
        if self.categoria == PRESUPUESTOS:
            # Un presupuesto solo se factura si está aceptado y no se ha
            # facturado ya: facturarlo dos veces es cobrar dos veces.
            self.boton_facturar.setEnabled(
                elemento.estado == ACEPTADO
                and not repo_documentos.factura_de(elemento.id)
            )

    def _menu_contextual(self, punto):
        if self.seleccionado() is None:
            return
        menu = QMenu(self)
        for accion in self.acciones:
            if accion.isEnabled() and accion.text():
                menu.addAction(accion.icon(), accion.text(), accion.click)
        menu.exec(self.vista.viewport().mapToGlobal(punto))

    def _abrir(self):
        """Doble clic: el documento se edita, el cliente enseña su ficha."""
        if self.es_documento:
            self._editar()
            return
        cliente = self.seleccionado()
        if cliente is not None:
            from ui.views.cliente_editor import FichaCliente

            FichaCliente(cliente, self).exec()

    # ───────────────────────────── acciones ─────────────────────────────

    def nuevo_elemento(self):
        if self.categoria == CLIENTES:
            from ui.views.cliente_editor import EditorCliente

            if EditorCliente(self).exec():
                self.cargar()
            return

        from ui.views.documento_editor import DocumentoEditor

        if DocumentoEditor(tipo=self.tipo, parent=self).exec():
            self.cargar()

    def _editar(self):
        documento = self.seleccionado()
        if documento is None:
            return
        from ui.views.documento_editor import DocumentoEditor

        if DocumentoEditor(documento_id=documento.id, parent=self).exec():
            self.cargar()

    def _menu_estado(self):
        documento = self.seleccionado()
        if documento is None:
            return
        menu = QMenu(self)
        for estado in self._transiciones(documento):
            menu.addAction(
                iconos.icono(ICONOS_ESTADO[estado]),
                NOMBRES_ESTADO[estado],
                lambda _=False, e=estado: self._cambiar_estado(documento.id, e),
            )
        menu.exec(self.boton_estado.mapToGlobal(self.boton_estado.rect().bottomLeft()))

    def _cambiar_estado(self, documento_id, estado):
        if repo_documentos.cambiar_estado(documento_id, estado):
            self.cargar()
        else:
            self._avisar(
                "No se puede",
                "Ese cambio de estado no es posible desde la situación actual "
                "del presupuesto.",
            )

    def _facturar(self):
        presupuesto = self.seleccionado()
        if presupuesto is None:
            return
        if not self._preguntar(
            "Convertir en factura",
            f"Se emitirá una factura con las líneas del presupuesto "
            f"{presupuesto.referencia}.\n\nEl presupuesto se conserva, y la factura "
            f"entrará en la serie de facturación con su número.",
        ):
            return

        factura_id = repo_documentos.facturar_presupuesto(presupuesto.id)
        if not factura_id:
            self._avisar("No se pudo facturar",
                         "Solo se factura un presupuesto aceptado, y solo una vez.")
            return

        factura = repo_documentos.obtener(factura_id, con_lineas=False)
        self._informar(
            "Factura emitida",
            f"Factura {factura.referencia} · {formatear(factura.importe_total)} €",
        )
        self.cargar()
        ventana = self.window()
        if hasattr(ventana, "ir_a"):
            ventana.ir_a(FACTURAS)

    def _para_el_pdf(self):
        """
        El documento seleccionado, listo para maquetar.

        Devuelve `(documento, datos, totales)`, o None si falta algo —y
        entonces ya ha avisado de qué—. Lo usan la vista previa y el botón de
        guardar: las dos tienen que enseñar lo mismo.
        """
        seleccionado = self.seleccionado()
        if seleccionado is None:
            return None
        documento = repo_documentos.obtener(seleccionado.id)
        if documento is None:
            self._avisar("No encontrado", "Ese documento ya no existe.")
            return None
        if not documento.lineas:
            self._avisar(
                "Sin conceptos",
                f"{documento.referencia} no tiene ninguna línea, así que no hay nada "
                "que imprimir. Ábrelo y escribe al menos un concepto.",
            )
            return None

        cliente = repo_clientes.obtener(documento.cliente_id)
        emisor = repo_autonomo.obtener()
        if cliente is None or emisor is None:
            self._avisar(
                "Faltan datos",
                "No se han podido leer los datos del cliente o los tuyos, y sin "
                "ellos el documento no es válido.",
            )
            return None

        return documento, datos_de(documento, cliente, emisor), calcular(documento.lineas)

    def _previsualizar(self):
        """
        Enseña el documento como va a salir impreso, sin guardarlo.

        Lo que se ve es el PDF de verdad, generado en una carpeta temporal que
        se borra al cerrar. Desde la propia ventana se puede guardar.
        """
        preparado = self._para_el_pdf()
        if preparado is None:
            return
        documento, datos, totales = preparado

        try:
            previa = VistaPrevia(datos, totales=totales, parent=self)
        except ErrorDePrevia as e:
            QMessageBox.critical(
                self, "No se pudo enseñar el documento",
                f"{documento.referencia} no se ha podido maquetar.\n\nMotivo: {e}",
            )
            return
        previa.exec()

    def _generar_pdf(self):
        preparado = self._para_el_pdf()
        if preparado is None:
            return
        documento, datos, totales = preparado

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", f"{documento.referencia}.pdf", "PDF (*.pdf)"
        )
        if not ruta:
            return

        try:
            resultado = generar_documento_pdf(datos, ruta, totales=totales)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(
                self, "No se pudo generar el PDF",
                f"{documento.referencia} no se ha podido escribir en {ruta}.\n\n"
                f"Motivo: {e}",
            )
            return

        paginas = resultado["paginas"]
        self._informar(
            "PDF generado",
            f"{documento.rotulo.capitalize()} {documento.referencia} · "
            f"{formatear(totales.total)} €\n"
            f"{paginas} página{'s' if paginas != 1 else ''} en {ruta}",
        )

    def _eliminar(self):
        elemento = self.seleccionado()
        if elemento is None:
            return
        if self.categoria == CLIENTES:
            self._eliminar_cliente(elemento)
        else:
            self._eliminar_documento(elemento)

    def _eliminar_documento(self, documento):
        if documento.es_presupuesto:
            aviso = f"¿Borrar el presupuesto {documento.referencia}?"
        else:
            # Borrar una factura deja un hueco permanente en la serie, y la
            # numeración tiene que ser correlativa.
            aviso = (
                f"¿Borrar la factura {documento.referencia}?\n\n"
                f"Su número quedará como un hueco en la serie de {documento.ejercicio}, "
                f"y una numeración con saltos es un problema ante Hacienda."
            )
        if not self._preguntar(
            "Confirmar", aviso + "\n\nEsta acción no se puede deshacer."
        ):
            return

        if repo_documentos.eliminar(documento.id):
            self.cargar()
        else:
            self._avisar("Error", "No se pudo borrar.")

    def _eliminar_cliente(self, cliente):
        cuantas = repo_clientes.cuantas_facturas(cliente.id)
        if cuantas:
            self._avisar(
                "No se puede eliminar",
                f"{cliente.nombre} tiene {cuantas} documento(s) emitido(s).\n"
                "Una factura emitida no puede quedarse sin destinatario.",
            )
            return
        if not self._preguntar(
            "Confirmar eliminación",
            f"¿Borrar a {cliente.nombre}?\n\nEsta acción no se puede deshacer.",
        ):
            return
        if repo_clientes.eliminar(cliente.id):
            self.cargar()
        else:
            self._avisar("Error", "No se pudo borrar el cliente.")

    # ───────────────────────────── avisos ─────────────────────────────

    def _avisar(self, titulo, mensaje):
        QMessageBox.warning(self, titulo, mensaje)

    def _informar(self, titulo, mensaje):
        QMessageBox.information(self, titulo, mensaje)

    def _preguntar(self, titulo, mensaje):
        return QMessageBox.question(
            self, titulo, mensaje,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes
