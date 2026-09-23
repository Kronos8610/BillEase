from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QFrame, QScrollArea, QLineEdit, QGroupBox, QMessageBox,
    QComboBox, QTextEdit, QCalendarWidget, QDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont
from core.models import Linea
from core.money import a_decimal, formatear
from utils.globals import TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND, TITLE_FONT, SUBTITLE_FONT, BODY_FONT

class EditarFactura(QDialog):
    saved = pyqtSignal()  # para notificar a HomePage que recargue

    def __init__(self, num_factura, parent=None):
        super().__init__(parent)
        self.num_factura = num_factura
        self.setWindowTitle(f"Editar Factura #{num_factura}")
        self.setModal(True)
        self.setMinimumSize(900, 600)       # tamaño mínimo
        self.setSizeGripEnabled(True)       # “tirador” en la esquina
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        self.filas_conceptos = []

        # --- Scroll principal ---
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(20)

        # Título
        page_title = QLabel(f"Editar Factura #{num_factura}")
        page_title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        page_title.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 15px;")
        scroll_layout.addWidget(page_title)

        # --- Selector de Cliente ---
        cliente_selector_box = self.create_section_box("Seleccionar Cliente")
        cliente_selector_layout = QVBoxLayout()
        self.cliente_combo = QComboBox()
        self.cliente_combo.setMinimumHeight(35)
        self.cliente_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: white;
                border: 1px solid {ALMOND};
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 200px;
            }}
            QComboBox:focus {{ border: 1px solid {BYZANTIUM}; }}
            QComboBox::drop-down {{ border: none; width: 25px; }}
        """)
        self.cliente_combo.setMaximumWidth(400)
        refresh_btn = QPushButton("🔄 Actualizar lista")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BYZANTIUM};
                color: white; border: none; border-radius: 4px; padding: 8px 15px;
            }}
            QPushButton:hover {{ background-color: {TYRIAN_PURPLE}; }}
        """)
        refresh_btn.clicked.connect(self.cargar_clientes)

        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("Cliente:"))
        combo_layout.addWidget(self.cliente_combo)
        combo_layout.addWidget(refresh_btn)
        combo_layout.addStretch()
        cliente_selector_layout.addLayout(combo_layout)
        cliente_selector_box.layout().addLayout(cliente_selector_layout)
        scroll_layout.addWidget(cliente_selector_box)

        # --- Datos del Cliente (solo visuales) ---
        cliente_box = self.create_section_box("Datos del Cliente")
        cliente_layout = QVBoxLayout()
        fila1 = QHBoxLayout()
        self.nombre = self.create_styled_input("Nombre o Razón Social")
        self.direccion = self.create_styled_input("Dirección")
        self.cp = self.create_styled_input("CP y Ciudad")
        fila1.addWidget(self.nombre); fila1.addWidget(self.direccion); fila1.addWidget(self.cp)
        cliente_layout.addLayout(fila1)
        fila2 = QHBoxLayout()
        self.nif = self.create_styled_input("NIF / CIF")
        self.telefono = self.create_styled_input("Teléfono")
        self.email = self.create_styled_input("Email")
        fila2.addWidget(self.nif); fila2.addWidget(self.telefono); fila2.addWidget(self.email)
        cliente_layout.addLayout(fila2)
        cliente_box.layout().addLayout(cliente_layout)
        scroll_layout.addWidget(cliente_box)

        # --- Datos de Factura ---
        factura_box = self.create_section_box("Datos de Factura")
        factura_layout = QVBoxLayout()
        fila3 = QHBoxLayout()

        fecha_container = QWidget()
        fecha_layout = QVBoxLayout(fecha_container)
        fecha_layout.setContentsMargins(0, 0, 0, 0)
        fecha_layout.setSpacing(0)

        self.fecha = self.create_styled_input("Fecha")
        self.calendario = QCalendarWidget()
        self.calendario.setMaximumSize(300, 250)
        self.calendario.setGridVisible(True)
        self.calendario.setVisible(False)
        self.calendario.clicked.connect(self.fecha_seleccionada)
        self.fecha.mousePressEvent = self.mostrar_calendario  # toggle calendario

        fecha_layout.addWidget(self.fecha)
        fecha_layout.addWidget(self.calendario)
        fila3.addWidget(QLabel("Fecha:"))
        fila3.addWidget(fecha_container)
        fila3.addStretch(1)
        factura_layout.addLayout(fila3)
        factura_box.layout().addLayout(factura_layout)
        scroll_layout.addWidget(factura_box)

        # --- Conceptos ---
        conceptos_box = self.create_section_box("Detalle de Conceptos")
        conceptos_layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        for title, width in [("Servicio", 3), ("Cantidad", 1), ("Precio Ud.", 1), ("Total", 1), ("", 1)]:
            header = QLabel(title)
            header.setFont(SUBTITLE_FONT)
            header.setStyleSheet(f"color: {TYRIAN_PURPLE}; padding: 5px 0;")
            header_layout.addWidget(header, width)
        conceptos_layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
        conceptos_layout.addWidget(separator)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(200)
        self.conceptos_widget = QWidget()
        self.conceptos_filas_layout = QVBoxLayout(self.conceptos_widget)
        self.conceptos_filas_layout.setContentsMargins(10, 10, 10, 10)
        self.conceptos_filas_layout.setSpacing(8)
        self.scroll_area.setWidget(self.conceptos_widget)

        self.btn_add_fila = QPushButton("+ Añadir línea")
        self.btn_add_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_fila.setStyleSheet(f"""
            QPushButton {{
                background-color: {LAVENDER_PINK}; color: {TYRIAN_PURPLE};
                border: none; border-radius: 4px; padding: 8px 15px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #FF8CB6; }}
        """)
        self.btn_add_fila.clicked.connect(self.add_fila_concepto)

        conceptos_layout.addWidget(self.scroll_area)
        conceptos_layout.addWidget(self.btn_add_fila, alignment=Qt.AlignmentFlag.AlignLeft)
        conceptos_box.layout().addLayout(conceptos_layout)
        scroll_layout.addWidget(conceptos_box)

        # --- Observaciones ---
        observaciones_box = self.create_section_box("Observaciones")
        self.observaciones_input = QTextEdit()
        self.observaciones_input.setPlaceholderText("Observaciones...")
        self.observaciones_input.setMinimumHeight(80)
        self.observaciones_input.setStyleSheet(f"""
            QTextEdit {{ background-color: white; border: 1px solid {ALMOND}; border-radius: 4px; padding: 5px 10px; }}
            QTextEdit:focus {{ border: 1px solid {BYZANTIUM}; }}
        """)
        observaciones_box.layout().addWidget(self.observaciones_input)
        scroll_layout.addWidget(observaciones_box)

        # --- Botones ---
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton { background-color: white; color: #66023C; border: 1px solid #66023C; border-radius: 5px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background-color: #F8F8F8; }
        """)
        self.cancel_btn.clicked.connect(self.reject)  # al ser QDialog

        self.save_btn = QPushButton("Guardar cambios")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TYRIAN_PURPLE}; color: white; border: none;
                border-radius: 5px; padding: 10px 30px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {BYZANTIUM}; }}
        """)
        self.save_btn.clicked.connect(self.guardar_cambios)

        action_layout.addStretch()
        action_layout.addWidget(self.cancel_btn)
        action_layout.addSpacing(10)
        action_layout.addWidget(self.save_btn)
        scroll_layout.addWidget(action_container)

        # Montar scroll principal y layout raíz
        self.main_scroll.setWidget(scroll_widget)
        self.main_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_scroll)

        # Cargar data
        self.cargar_clientes()
        self.precargar_factura()

    # ------- Utilidades UI -------
    def create_section_box(self, title):
        group_box = QGroupBox()
        group_box.setStyleSheet(f"""
            QGroupBox {{
                background-color: white; border-radius: 8px; border: 1px solid {ALMOND}; padding: 15px; margin-top: 10px;
            }}
        """)
        label = QLabel(title)
        label.setFont(TITLE_FONT)
        label.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 10px;")
        layout = QVBoxLayout(group_box)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.addWidget(label)
        return group_box

    def create_styled_input(self, placeholder):
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(35)
        input_field.setFont(BODY_FONT)
        input_field.setStyleSheet(f"""
            QLineEdit {{ background-color: white; border: 1px solid {ALMOND}; border-radius: 4px; padding: 5px 10px; }}
            QLineEdit:focus {{ border: 1px solid {BYZANTIUM}; }}
        """)
        return input_field

    # ------- Carga de datos -------
    def cargar_clientes(self):
        from data.repositories import clientes as repo_clientes
        self.cliente_combo.clear()
        self.cliente_combo.addItem("-- Seleccione un cliente --", None)
        for cliente in repo_clientes.listar():
            self.cliente_combo.addItem(f"{cliente.nombre} ({cliente.nif})", cliente)

    def precargar_factura(self):
        from core.fechas import a_espanol
        from data.repositories import facturas as repo_facturas

        factura = repo_facturas.obtener(self.num_factura)
        if factura is None:
            QMessageBox.warning(self, "Error", "No se encontró la factura.")
            self.reject()
            return

        self.setWindowTitle(f"Editar factura {factura.referencia}")

        # Seleccionar el cliente y enseñar sus datos (solo de lectura: lo que
        # se escriba aquí no se guarda, así que no debe parecer editable).
        for i in range(self.cliente_combo.count()):
            cliente = self.cliente_combo.itemData(i)
            if cliente and cliente.id == factura.cliente_id:
                self.cliente_combo.setCurrentIndex(i)
                self.nombre.setText(cliente.nombre)
                self.direccion.setText(cliente.direccion)
                self.cp.setText(cliente.codigo_postal)
                self.nif.setText(cliente.nif)
                self.telefono.setText(cliente.telefono)
                self.email.setText(cliente.email)
                break

        self.fecha.setText(a_espanol(factura.fecha))
        self.observaciones_input.setPlainText(factura.observaciones)

        # Cargar los conceptos existentes como filas
        self.filas_conceptos.clear()
        while self.conceptos_filas_layout.count():
            item = self.conceptos_filas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for linea in factura.lineas:
            self.add_fila_concepto(prefill={
                "cod_servicio": linea.cod_servicio,
                "descripcion": linea.descripcion,
                "cantidad": str(linea.cantidad),
                "precio_ud": formatear(linea.precio_ud),
                "total": formatear(linea.importe),
            })

    def add_fila_concepto(self, prefill=None):
        fila = QHBoxLayout(); fila.setSpacing(10)
        from data.repositories import servicios as repo_servicios
        servicios = repo_servicios.listar()

        servicio_combo = QComboBox()
        servicio_combo.setMinimumHeight(35)
        servicio_combo.setFont(BODY_FONT)
        servicio_combo.setStyleSheet(f"""
            QComboBox {{ background-color: white; border: 1px solid {ALMOND}; border-radius: 4px; padding: 5px 10px; }}
            QComboBox:focus {{ border: 1px solid {BYZANTIUM}; }}
            QComboBox::drop-down {{ border: none; width: 25px; }}
        """)
        servicio_combo.addItem("Seleccione un servicio", None)
        for servicio in servicios:
            servicio_combo.addItem(servicio.descripcion, servicio)

        cantidad = self.create_styled_input("1")
        precio_ud = self.create_styled_input("0.00")
        total = self.create_styled_input("0.00")
        total.setReadOnly(True)

        remove_btn = QPushButton("✖")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton { background-color: #dc3545; color: white; border: none; border-radius: 4px; padding: 6px 10px; font-weight: bold; }
            QPushButton:hover { background-color: #c82333; }
        """)

        def refrescar_importe():
            if not servicio_combo.currentData():
                total.setText("")
                return
            try:
                fila = Linea(
                    descripcion="",
                    cantidad=cantidad.text() or "0",
                    precio_ud=precio_ud.text() or "0",
                )
                total.setText(formatear(fila.importe))
            except (ArithmeticError, ValueError):
                total.setText("")

        def on_servicio_selected(index):
            if index <= 0:
                precio_ud.setText(""); total.setText(""); return
            servicio = servicio_combo.currentData()
            if servicio:
                precio_ud.setText(formatear(servicio.precio))
                if not cantidad.text().strip():
                    cantidad.setText("1")
                refrescar_importe()

        def on_cantidad_changed():
            refrescar_importe()

        def on_precio_changed():
            refrescar_importe()

        servicio_combo.currentIndexChanged.connect(on_servicio_selected)
        cantidad.textChanged.connect(on_cantidad_changed)
        precio_ud.textChanged.connect(on_precio_changed)

        fila.addWidget(servicio_combo, 3)
        fila.addWidget(cantidad, 1)
        fila.addWidget(precio_ud, 1)
        fila.addWidget(total, 1)
        fila.addWidget(remove_btn, 1)

        fila_widget = QWidget()
        fila_widget.setLayout(fila)
        self.conceptos_filas_layout.addWidget(fila_widget)
        self.filas_conceptos.append((fila_widget, servicio_combo, cantidad, precio_ud, total))
        remove_btn.clicked.connect(lambda: self.remove_linea(fila_widget))

        if prefill:
            objetivo_id = prefill.get("cod_servicio")
            for i in range(servicio_combo.count()):
                servicio = servicio_combo.itemData(i)
                if servicio and servicio.id == objetivo_id:
                    servicio_combo.setCurrentIndex(i)
                    break
            cantidad.setText(prefill.get("cantidad", "1"))
            precio_ud.setText(prefill.get("precio_ud", "0.00"))
            total.setText(prefill.get("total", "0.00"))

    def remove_linea(self, fila_widget):
        for i, (w, *_rest) in enumerate(self.filas_conceptos):
            if w is fila_widget:
                self.filas_conceptos.pop(i)
                break
        fila_widget.setParent(None)
        fila_widget.deleteLater()

    # ------- Fecha -------
    def mostrar_calendario(self, event):
        self.calendario.setVisible(not self.calendario.isVisible())

    def fecha_seleccionada(self, date: QDate):
        self.fecha.setText(date.toString("dd/MM/yyyy"))
        self.calendario.setVisible(False)

    # ------- Guardado -------
    def guardar_cambios(self):
        from core.taxes import calcular
        from data.repositories import facturas as repo_facturas

        if self.cliente_combo.currentIndex() <= 0:
            QMessageBox.warning(self, "Cliente no seleccionado", "Seleccione un cliente.")
            return
        if not self.fecha.text().strip():
            QMessageBox.warning(self, "Fecha requerida", "Indique una fecha.")
            return

        cliente = self.cliente_combo.currentData()

        lineas = []
        for (_w, servicio_combo, cantidad, precio_ud, _total) in self.filas_conceptos:
            servicio = servicio_combo.currentData()
            if not servicio:
                continue
            try:
                unidades = a_decimal(cantidad.text())
                pu = a_decimal(precio_ud.text())
            except ArithmeticError:
                continue
            if unidades > 0 and pu > 0:
                lineas.append(Linea(
                    descripcion=servicio.descripcion,
                    cantidad=unidades,
                    precio_ud=pu,
                    cod_servicio=servicio.id,
                ))

        if not lineas:
            QMessageBox.warning(self, "Sin líneas válidas", "Añada al menos una línea válida.")
            return

        observaciones = self.observaciones_input.toPlainText().strip()
        # Cabecera y líneas se cambian en una sola transacción.
        guardado = repo_facturas.actualizar(
            self.num_factura, self.fecha.text().strip(), cliente.id, lineas, observaciones
        )

        if not guardado:
            QMessageBox.critical(self, "No se pudo guardar",
                "Los cambios no se han guardado. Revisa que el cliente siga "
                "existiendo y que la fecha sea correcta.")
            return

        totales = calcular(lineas)
        factura = repo_facturas.obtener(self.num_factura, con_lineas=False)
        QMessageBox.information(self, "Factura actualizada",
            f"Factura {factura.referencia} · {formatear(totales.total)} €")
        self.saved.emit()
        self.accept()
