"""
El listado: facturas, presupuestos y clientes.

Antes eran tres constructores de lista casi iguales, uno por categoría, cada
uno con su cabecera y sus botones copiados. Aquí hay uno solo al que se le
dice qué columnas tiene cada categoría y cómo se pinta cada fila.

La pantalla de servicios ha desaparecido: los conceptos se escriben en el
propio documento.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.fechas import a_espanol
from core.models import ACEPTADO, ENVIADO, FACTURA, PRESUPUESTO, RECHAZADO
from core.money import formatear
from core.quotes import esta_caducado
from core.taxes import calcular, desde_base
from data.repositories import autonomo as repo_autonomo
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from documents.invoice_pdf import generar_documento_pdf
from ui.views.documento_editor import DocumentoEditor
from utils.globals import (
    ALMOND,
    BYZANTIUM,
    CHAMPAGNE_PINK,
    LAVENDER_PINK,
    SUBTITLE_FONT,
    TYRIAN_PURPLE,
)

FACTURAS = "Facturas"
PRESUPUESTOS = "Presupuestos"
CLIENTES = "Clientes"

# Cómo se enseña cada estado de un presupuesto.
COLOR_ESTADO = {
    "borrador": "#8A8A8A",
    ENVIADO: "#9D5D00",
    ACEPTADO: "#0F7B0F",
    RECHAZADO: "#C42B1C",
}


def boton(texto, fondo, color="white", ancho_minimo=0):
    b = QPushButton(texto)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ background-color: {fondo}; color: {color}; border: none;"
        f" border-radius: 4px; padding: 5px 12px; }}"
        f"QPushButton:hover {{ background-color: {TYRIAN_PURPLE}; color: white; }}"
    )
    if ancho_minimo:
        b.setMinimumWidth(ancho_minimo)
    return b


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(40, 40, 40, 40)

        contenedor = QGroupBox()
        contenedor.setStyleSheet(
            f"QGroupBox {{ background-color: white; border-radius: 10px;"
            f" border: 1px solid {ALMOND}; }}"
        )
        dentro = QVBoxLayout(contenedor)
        dentro.setContentsMargins(30, 30, 30, 30)

        cabecera = QHBoxLayout()
        self.title = QLabel(FACTURAS)
        self.title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.title.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 10px;")

        self.categoria_combo = QComboBox()
        self.categoria_combo.addItems([FACTURAS, PRESUPUESTOS, CLIENTES])
        self.categoria_combo.setMinimumWidth(150)
        self.categoria_combo.setStyleSheet(
            f"QComboBox {{ background-color: white; border: 1px solid {BYZANTIUM};"
            f" border-radius: 4px; padding: 5px; color: {BYZANTIUM}; }}"
        )
        self.categoria_combo.currentIndexChanged.connect(self.cambiar_categoria)

        self.nuevo_btn = boton("+  Nueva factura", TYRIAN_PURPLE)
        self.nuevo_btn.clicked.connect(self.nuevo_documento)
        self.refresh_btn = boton("Actualizar", BYZANTIUM)
        self.refresh_btn.clicked.connect(self.cargar_datos)

        cabecera.addWidget(self.title)
        cabecera.addStretch()
        cabecera.addWidget(self.categoria_combo)
        cabecera.addSpacing(8)
        cabecera.addWidget(self.nuevo_btn)
        cabecera.addSpacing(8)
        cabecera.addWidget(self.refresh_btn)
        dentro.addLayout(cabecera)

        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.HLine)
        separador.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
        dentro.addWidget(separador)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout(self.items_widget)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        scroll.setWidget(self.items_widget)
        dentro.addWidget(scroll)

        raiz.addWidget(contenedor)
        self.cargar_datos()

    # ───────────────────────────── listado ─────────────────────────────

    @property
    def categoria(self):
        return self.categoria_combo.currentText()

    def cambiar_categoria(self):
        self.title.setText(self.categoria)
        etiquetas = {
            FACTURAS: "+  Nueva factura",
            PRESUPUESTOS: "+  Nuevo presupuesto",
            CLIENTES: "+  Nuevo cliente",
        }
        self.nuevo_btn.setText(etiquetas[self.categoria])
        self.cargar_datos()

    def cargar_datos(self):
        self.limpiar()
        if self.categoria == FACTURAS:
            self.pintar(
                [("Número", 2), ("Fecha", 2), ("Cliente", 4), ("Base", 2),
                 ("Total", 2), ("", 3)],
                repo_documentos.listar(FACTURA),
                self.fila_documento,
                "Todavía no has emitido ninguna factura.",
            )
        elif self.categoria == PRESUPUESTOS:
            self.pintar(
                [("Número", 2), ("Fecha", 2), ("Cliente", 4), ("Estado", 2),
                 ("Total", 2), ("", 4)],
                repo_documentos.listar(PRESUPUESTO),
                self.fila_documento,
                "Todavía no has hecho ningún presupuesto.",
            )
        else:
            self.pintar(
                [("NIF/CIF", 2), ("Nombre", 5), ("Teléfono", 2), ("", 1)],
                repo_clientes.listar(),
                self.fila_cliente,
                "Todavía no tienes clientes dados de alta.",
            )

    def pintar(self, columnas, elementos, constructor, mensaje_vacio):
        if not elementos:
            vacio = QLabel(mensaje_vacio)
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vacio.setStyleSheet(f"color: {BYZANTIUM}; font-style: italic; margin: 30px 0;")
            self.items_layout.addWidget(vacio)
            self.items_layout.addStretch()
            return

        cabecera = QWidget()
        fila = QHBoxLayout(cabecera)
        fila.setContentsMargins(10, 5, 10, 5)
        for titulo, ancho in columnas:
            etiqueta = QLabel(titulo)
            etiqueta.setFont(SUBTITLE_FONT)
            etiqueta.setStyleSheet(f"color: {TYRIAN_PURPLE};")
            fila.addWidget(etiqueta, ancho)
        self.items_layout.addWidget(cabecera)

        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.HLine)
        separador.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
        self.items_layout.addWidget(separador)

        for indice, elemento in enumerate(elementos):
            self.items_layout.addWidget(constructor(elemento, columnas, indice % 2 == 0))
        self.items_layout.addStretch()

    def limpiar(self):
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _fila_base(self, alterna):
        contenedor = QWidget()
        contenedor.setStyleSheet(
            f"background-color: {CHAMPAGNE_PINK if alterna else '#F8F8F8'};"
            f" border-radius: 5px;"
        )
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(10, 8, 10, 8)
        return contenedor, fila

    # ───────────────────────────── filas ─────────────────────────────

    def fila_documento(self, documento, columnas, alterna):
        contenedor, fila = self._fila_base(alterna)
        totales = desde_base(documento.base, documento.tipo_iva)

        numero = QLabel(documento.referencia)
        numero.setFont(SUBTITLE_FONT)
        fila.addWidget(numero, 2)
        fila.addWidget(QLabel(a_espanol(documento.fecha)), 2)
        fila.addWidget(QLabel(documento.cliente_nombre or "Cliente desconocido"), 4)

        if documento.es_presupuesto:
            estado = documento.estado
            texto = estado.capitalize()
            if esta_caducado(documento):
                texto, estado = "Caducado", RECHAZADO
            etiqueta = QLabel(texto)
            etiqueta.setStyleSheet(f"color: {COLOR_ESTADO.get(estado, BYZANTIUM)};")
            fila.addWidget(etiqueta, 2)
        else:
            base = QLabel(f"{formatear(totales.base)} €")
            base.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            base.setStyleSheet(f"color: {BYZANTIUM};")
            fila.addWidget(base, 2)

        total = QLabel(f"{formatear(totales.total)} €")
        total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total.setFont(SUBTITLE_FONT)
        total.setStyleSheet(f"color: {TYRIAN_PURPLE};")
        total.setToolTip(
            f"Base {formatear(totales.base)} € + IVA {formatear(totales.cuota_iva)} €"
        )
        fila.addWidget(total, 2)

        acciones = QHBoxLayout()
        acciones.setSpacing(5)

        pdf = boton("PDF", BYZANTIUM)
        pdf.clicked.connect(lambda _, d=documento.id: self.generar_pdf(d))
        acciones.addWidget(pdf)

        editar = boton("Editar", LAVENDER_PINK, TYRIAN_PURPLE)
        editar.clicked.connect(lambda _, d=documento.id: self.editar(d))
        acciones.addWidget(editar)

        if documento.es_presupuesto:
            for etiqueta, estado in self._acciones_presupuesto(documento):
                b = boton(etiqueta, BYZANTIUM)
                b.clicked.connect(
                    lambda _, d=documento.id, e=estado: self.cambiar_estado(d, e)
                )
                acciones.addWidget(b)
            if documento.estado == ACEPTADO and not repo_documentos.factura_de(documento.id):
                facturar = boton("Facturar", "#0F7B0F")
                facturar.clicked.connect(lambda _, d=documento.id: self.facturar(d))
                acciones.addWidget(facturar)

        borrar = boton("🗑", "#dc3545")
        borrar.clicked.connect(lambda _, d=documento.id: self.eliminar_documento(d))
        acciones.addWidget(borrar)

        envoltorio = QWidget()
        envoltorio.setLayout(acciones)
        fila.addWidget(envoltorio, columnas[-1][1])
        return contenedor

    def _acciones_presupuesto(self, documento):
        """Los pasos que puede dar un presupuesto desde donde está."""
        from core.quotes import TRANSICIONES

        nombres = {ENVIADO: "Enviar", ACEPTADO: "Aceptado", RECHAZADO: "Rechazado"}
        return [
            (nombres[estado], estado)
            for estado in TRANSICIONES.get(documento.estado, ())
        ]

    def fila_cliente(self, cliente, columnas, alterna):
        contenedor, fila = self._fila_base(alterna)
        fila.addWidget(QLabel(cliente.nif), 2)
        fila.addWidget(QLabel(cliente.nombre), 5)
        fila.addWidget(QLabel(cliente.telefono or "—"), 2)

        borrar = boton("🗑", "#dc3545")
        borrar.clicked.connect(lambda _, c=cliente.id: self.eliminar_cliente(c))
        fila.addWidget(borrar, 1)
        return contenedor

    # ───────────────────────────── acciones ─────────────────────────────

    def nuevo_documento(self):
        if self.categoria == CLIENTES:
            ventana = self.window()
            if hasattr(ventana, "ir_a_crear_cliente"):
                ventana.ir_a_crear_cliente()
            return

        tipo = PRESUPUESTO if self.categoria == PRESUPUESTOS else FACTURA
        if DocumentoEditor(tipo=tipo, parent=self).exec():
            self.cargar_datos()

    def editar(self, documento_id):
        if DocumentoEditor(documento_id=documento_id, parent=self).exec():
            self.cargar_datos()

    def cambiar_estado(self, documento_id, estado):
        if repo_documentos.cambiar_estado(documento_id, estado):
            self.cargar_datos()
        else:
            QMessageBox.warning(
                self, "No se puede",
                "Ese cambio de estado no es posible desde la situación actual "
                "del presupuesto."
            )

    def facturar(self, presupuesto_id):
        presupuesto = repo_documentos.obtener(presupuesto_id, con_lineas=False)
        confirmar = QMessageBox.question(
            self, "Convertir en factura",
            f"Se emitirá una factura con las líneas del presupuesto "
            f"{presupuesto.referencia}.\n\nEl presupuesto se conserva, y la factura "
            f"entrará en la serie de facturación con su número.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmar != QMessageBox.StandardButton.Yes:
            return

        factura_id = repo_documentos.facturar_presupuesto(presupuesto_id)
        if not factura_id:
            QMessageBox.warning(
                self, "No se pudo facturar",
                "Solo se factura un presupuesto aceptado, y solo una vez."
            )
            return

        factura = repo_documentos.obtener(factura_id, con_lineas=False)
        QMessageBox.information(
            self, "Factura emitida",
            f"Factura {factura.referencia} · {formatear(factura.importe_total)} €"
        )
        self.categoria_combo.setCurrentText(FACTURAS)

    def generar_pdf(self, documento_id):
        documento = repo_documentos.obtener(documento_id)
        if documento is None:
            QMessageBox.warning(self, "No encontrado", "Ese documento ya no existe.")
            return

        if not documento.lineas:
            QMessageBox.warning(
                self, "Sin conceptos",
                f"{documento.referencia} no tiene ninguna línea, así que no hay nada "
                "que imprimir. Ábrelo y escribe al menos un concepto."
            )
            return

        cliente = repo_clientes.obtener(documento.cliente_id)
        emisor = repo_autonomo.obtener()
        if cliente is None or emisor is None:
            QMessageBox.warning(
                self, "Faltan datos",
                "No se han podido leer los datos del cliente o los tuyos, y sin "
                "ellos el documento no es válido."
            )
            return

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", f"{documento.referencia}.pdf", "PDF Files (*.pdf)"
        )
        if not ruta:
            return

        totales = calcular(documento.lineas)
        datos = {
            "tipo": documento.tipo,
            "numero": documento.referencia,
            "fecha": a_espanol(documento.fecha),
            "vencimiento": a_espanol(documento.vencimiento),
            "validez": a_espanol(documento.validez),
            "emisor": {
                "nombre": emisor.nombre_completo,
                "nif": emisor.nif,
                "direccion": emisor.direccion,
                "poblacion": emisor.codigo_postal,
                "telefono": emisor.telefono,
                "email": emisor.email,
            },
            "cliente": {
                "nombre": cliente.nombre,
                "nif": cliente.nif,
                "direccion": cliente.direccion,
                "poblacion": cliente.codigo_postal,
                "telefono": cliente.telefono,
                "email": cliente.email,
            },
            "lineas": documento.lineas,
            "nota": documento.observaciones,
        }

        try:
            resultado = generar_documento_pdf(datos, ruta, totales=totales)
        except Exception as e:
            QMessageBox.critical(
                self, "No se pudo generar el PDF",
                f"{documento.referencia} no se ha podido escribir en {ruta}.\n\n"
                f"Motivo: {e}"
            )
            return

        paginas = resultado["paginas"]
        QMessageBox.information(
            self, "PDF generado",
            f"{documento.rotulo.capitalize()} {documento.referencia} · "
            f"{formatear(totales.total)} €\n"
            f"{paginas} página{'s' if paginas != 1 else ''} en {ruta}"
        )

    def eliminar_documento(self, documento_id):
        documento = repo_documentos.obtener(documento_id, con_lineas=False)
        if documento is None:
            return

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

        if QMessageBox.question(
            self, "Confirmar", aviso + "\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        if repo_documentos.eliminar(documento_id):
            self.cargar_datos()
        else:
            QMessageBox.warning(self, "Error", "No se pudo borrar.")

    def eliminar_cliente(self, cliente_id):
        cuantas = repo_clientes.cuantas_facturas(cliente_id)
        if cuantas:
            QMessageBox.warning(
                self, "No se puede eliminar",
                f"Este cliente tiene {cuantas} documento(s) emitido(s).\n"
                f"Una factura emitida no puede quedarse sin destinatario."
            )
            return

        if QMessageBox.question(
            self, "Confirmar eliminación",
            "¿Borrar este cliente?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        if repo_clientes.eliminar(cliente_id):
            self.cargar_datos()
        else:
            QMessageBox.warning(self, "Error", "No se pudo borrar el cliente.")
