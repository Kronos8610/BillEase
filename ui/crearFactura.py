from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QFrame, QScrollArea, QLineEdit,
    QGroupBox, QMessageBox, QComboBox, QTextEdit, QCalendarWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import datetime
from utils.globals import (
    TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND,
    TITLE_FONT, SUBTITLE_FONT, BODY_FONT
)
class CrearFactura(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        
        # Primero, definir los atributos de la clase que se usarán después
        # Lista para guardar las filas de conceptos
        self.filas_conceptos = []
        
        # Scroll area principal
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # Scroll area para conceptos
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(120)
        self.scroll_area.setMaximumHeight(350)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {ALMOND};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {BYZANTIUM};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # Scroll area para todo el contenido
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(20)
        
        # Título 
        page_title = QLabel("Crear Nueva Factura")
        page_title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        page_title.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 15px;")
        scroll_layout.addWidget(page_title)

        # --- Selector de Cliente ---
        cliente_selector_box = self.create_section_box("Seleccionar Cliente Existente")
        cliente_selector_layout = QVBoxLayout()
        
        # Crear el ComboBox para seleccionar cliente
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
            QComboBox:focus {{
                border: 1px solid {BYZANTIUM};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 25px;
            }}
        """)
        self.cliente_combo.setMaximumWidth(400)
        self.cliente_combo.currentIndexChanged.connect(self.cliente_seleccionado)
        
        # Botón de actualizar lista
        refresh_btn = QPushButton("🔄 Actualizar lista")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BYZANTIUM};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
            }}
            QPushButton:hover {{
                background-color: {TYRIAN_PURPLE};
            }}
        """)
        refresh_btn.clicked.connect(self.cargar_clientes)
        
        # Layout horizontal para combo y botón
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("Cliente:"))
        combo_layout.addWidget(self.cliente_combo)
        combo_layout.addWidget(refresh_btn)
        combo_layout.addStretch()
        
        cliente_selector_layout.addLayout(combo_layout)
        
        # Obtener el layout existente del QGroupBox y agregar nuestro layout
        box_layout = cliente_selector_box.layout()
        box_layout.addLayout(cliente_selector_layout)
        
        scroll_layout.addWidget(cliente_selector_box)

        # --- Datos del Cliente ---
        cliente_box = self.create_section_box("Datos del Cliente")
        cliente_layout = QVBoxLayout()
        
        fila1 = QHBoxLayout()
        self.nombre = self.create_styled_input("Nombre o Razón Social")
        self.direccion = self.create_styled_input("Dirección")
        self.cp = self.create_styled_input("CP y Ciudad")
        fila1.addWidget(self.nombre)
        fila1.addWidget(self.direccion)
        fila1.addWidget(self.cp)
        cliente_layout.addLayout(fila1)

        fila2 = QHBoxLayout()
        self.nif = self.create_styled_input("NIF / CIF")
        self.telefono = self.create_styled_input("Teléfono")
        self.email = self.create_styled_input("Email")
        fila2.addWidget(self.nif)
        fila2.addWidget(self.telefono)
        fila2.addWidget(self.email)
        cliente_layout.addLayout(fila2)

        # Obtener el layout existente del QGroupBox y agregar nuestro layout
        box_layout = cliente_box.layout()
        box_layout.addLayout(cliente_layout)
        
        scroll_layout.addWidget(cliente_box)

        # --- Datos de Factura ---
        factura_box = self.create_section_box("Datos de Factura")
        factura_layout = QVBoxLayout()

        fila3 = QHBoxLayout()
        
        # Modificar el campo de fecha para incluir calendario
        fecha_container = QWidget()
        fecha_layout = QVBoxLayout(fecha_container)
        fecha_layout.setContentsMargins(0, 0, 0, 0)
        fecha_layout.setSpacing(0)
        
        self.fecha = self.create_styled_input("Fecha")
        # Obtener la fecha actual formateada
        fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
        self.fecha.setText(fecha_actual)
        
        # Crear el calendario (oculto inicialmente)
        self.calendario = QCalendarWidget()
        self.calendario.setMaximumSize(300, 250)
        self.calendario.setStyleSheet(f"""
            QCalendarWidget {{
                background-color: white;
                border: 1px solid {ALMOND};
            }}
            QCalendarWidget QToolButton {{
                color: {TYRIAN_PURPLE};
                background-color: white;
                padding: 5px;
                border-radius: 3px;
            }}
            QCalendarWidget QMenu {{
                color: {TYRIAN_PURPLE};
                background-color: white;
            }}
            QCalendarWidget QSpinBox {{
                color: {TYRIAN_PURPLE};
                background-color: white;
                selection-background-color: {BYZANTIUM};
                selection-color: white;
            }}
            QCalendarWidget QTableView {{
                alternate-background-color: {CHAMPAGNE_PINK};
            }}
        """)
        self.calendario.setGridVisible(True)
        self.calendario.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendario.clicked.connect(self.fecha_seleccionada)
        self.calendario.setVisible(False)  # Oculto inicialmente
        
        fecha_layout.addWidget(self.fecha)
        fecha_layout.addWidget(self.calendario)
        
        # Conectar el evento de clic en el campo de fecha
        self.fecha.mousePressEvent = self.mostrar_calendario

        # Añadir el widget de fecha al layout de la fila
        fila3.addWidget(QLabel("Fecha:"))  # Añadir etiqueta para claridad
        fila3.addWidget(fecha_container)
        fila3.addStretch(1)  

        # Añadir la fila al layout principal de la sección
        factura_layout.addLayout(fila3)

        # Añadir el layout de la factura al box
        box_layout = factura_box.layout()
        box_layout.addLayout(factura_layout)

        # Añadir el box al layout principal
        scroll_layout.addWidget(factura_box)

        # --- Conceptos ---
        conceptos_box = self.create_section_box("Detalle de Conceptos")
        conceptos_layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        for title, width in [("Servicio", 3), ("Cantidad", 1), ("Precio Ud.", 1), ("Total", 1)]:
            header = QLabel(title)
            header.setFont(SUBTITLE_FONT)
            header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            header.setStyleSheet(f"color: {TYRIAN_PURPLE}; padding: 5px 0;")
            header_layout.addWidget(header, width)
        
        conceptos_layout.addLayout(header_layout)
        
        # Línea separadora
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
        conceptos_layout.addWidget(separator)

        # Widget y layout para las filas de conceptos + botón
        self.conceptos_widget = QWidget()
        self.conceptos_widget.setStyleSheet(f"background-color: white; border-radius: 5px;")
        self.conceptos_filas_layout = QVBoxLayout(self.conceptos_widget)
        self.conceptos_filas_layout.setContentsMargins(10, 10, 10, 10)
        self.conceptos_filas_layout.setSpacing(8)

        # Botón para añadir filas
        self.btn_add_fila = QPushButton("+ Añadir línea")
        self.btn_add_fila.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_fila.setStyleSheet(f"""
            QPushButton {{
                background-color: {LAVENDER_PINK};
                color: {TYRIAN_PURPLE};
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FF8CB6;
            }}
            QPushButton:pressed {{
                background-color: #FF74A8;
            }}
        """)
        self.btn_add_fila.setMinimumWidth(120)
        self.btn_add_fila.clicked.connect(self.add_fila_concepto)

        # Añadir la primera fila y el botón
        self.setup_conceptos_area()

        # Asignar widget al scroll area
        self.scroll_area.setWidget(self.conceptos_widget)

        conceptos_layout.addWidget(self.scroll_area)
        conceptos_layout.addWidget(self.btn_add_fila, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Obtener el layout existente del QGroupBox y agregar nuestro layout
        box_layout = conceptos_box.layout()
        box_layout.addLayout(conceptos_layout)
        
        scroll_layout.addWidget(conceptos_box)

        # --- Observaciones ---
        observaciones_box = self.create_section_box("Observaciones")
        observaciones_layout = QVBoxLayout()
        
        # Campo de texto para observaciones
        self.observaciones_input = QTextEdit()
        self.observaciones_input.setPlaceholderText("Añada aquí cualquier observación relevante para la factura")
        self.observaciones_input.setMinimumHeight(80)
        self.observaciones_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                border: 1px solid {ALMOND};
                border-radius: 4px;
                padding: 5px 10px;
            }}
            QTextEdit:focus {{
                border: 1px solid {BYZANTIUM};
            }}
        """)
        
        observaciones_layout.addWidget(self.observaciones_input)
    
        box_layout = observaciones_box.layout()
        box_layout.addLayout(observaciones_layout)
        
        scroll_layout.addWidget(observaciones_box)
        
        # Contenedor para botones 
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 20, 0, 0)
        
        # Botones 
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {TYRIAN_PURPLE};
                border: 1px solid {TYRIAN_PURPLE};
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #F8F8F8;
            }}
            QPushButton:pressed {{
                background-color: #EEEEEE;
            }}
        """)
        self.cancel_btn.clicked.connect(self.limpiar_formulario)
        
        self.guardar_datos_factura = QPushButton("Guardar")
        self.guardar_datos_factura.setCursor(Qt.CursorShape.PointingHandCursor)
        self.guardar_datos_factura.setStyleSheet(f"""
            QPushButton {{
                background-color: {TYRIAN_PURPLE};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 30px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {BYZANTIUM};
            }}
            QPushButton:pressed {{
                background-color: #84084A;
            }}
        """)
        self.guardar_datos_factura.clicked.connect(self.handle_guardar_factura)
        
        action_layout.addStretch()
        action_layout.addWidget(self.cancel_btn)
        action_layout.addSpacing(10)
        action_layout.addWidget(self.guardar_datos_factura)
        
        scroll_layout.addWidget(action_container)
        
        # Asignar widget al scroll area principal
        main_scroll.setWidget(scroll_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_scroll)
        
        # Cargar clientes al inicializar
        self.cargar_clientes()

    def cargar_clientes(self):
        """Cargar la lista de clientes en el ComboBox"""
        from database.db import obtener_clientes
        
        self.cliente_combo.clear()
        self.cliente_combo.addItem("-- Seleccione un cliente --", None)
        
        clientes = obtener_clientes()
        for cliente in clientes:
            # El formato será: "NombreCliente (CIF/NIF)"
            cod_cliente, tipo_cliente, nombre, direccion, telefono, cp, cifnif, observaciones, *_ = cliente
            texto_combo = f"{nombre} ({cifnif})"
            self.cliente_combo.addItem(texto_combo, cliente)  # Guardamos todos los datos como userData
    
    def cliente_seleccionado(self, index):
        """Cuando se selecciona un cliente del ComboBox"""
        if index <= 0:  # El índice 0 es "Seleccione un cliente"
            return
        
        # Obtener datos del cliente seleccionado
        cliente_datos = self.cliente_combo.currentData()
        if cliente_datos:
            cod_cliente, tipo_cliente, nombre, direccion, telefono, cp, cifnif, observaciones, email, *_ = cliente_datos

            # Llenar los campos automáticamente
            self.nombre.setText(nombre)
            self.direccion.setText(direccion or "")
            self.cp.setText(str(cp) if cp else "")
            self.nif.setText(cifnif)
            if telefono:
                try:
                    telefono_int = int(float(telefono))
                    self.telefono.setText(str(telefono_int))
                except (ValueError, TypeError):
                    self.telefono.setText(str(telefono))
            else:
                self.telefono.setText("")
            self.email.setText(email or "")

    def create_section_box(self, title):
        group_box = QGroupBox()
        group_box.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid {ALMOND};
                padding: 15px;
                margin-top: 10px;
            }}
        """)
        
        # Título de la sección
        label = QLabel(title)
        label.setFont(TITLE_FONT)
        label.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 10px;")
        
        # Añadir título al layout
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
            QLineEdit {{
                background-color: white;
                border: 1px solid {ALMOND};
                border-radius: 4px;
                padding: 5px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {BYZANTIUM};
            }}
        """)
        return input_field

    def setup_conceptos_area(self):
        # Limpiar layout
        while self.conceptos_filas_layout.count():
            item = self.conceptos_filas_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.filas_conceptos.clear()
        self.add_fila_concepto()  # Añadir primera fila

    def add_fila_concepto(self):
        fila_concepto = QHBoxLayout()
        fila_concepto.setSpacing(10)
        
        # Crear ComboBox para servicios en lugar de cuadro de texto
        servicio_combo = QComboBox()
        servicio_combo.setMinimumHeight(35)
        servicio_combo.setFont(BODY_FONT)
        servicio_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: white;
                border: 1px solid {ALMOND};
                border-radius: 4px;
                padding: 5px 10px;
            }}
            QComboBox:focus {{
                border: 1px solid {BYZANTIUM};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 25px;
            }}
        """)
        
        # Cargar los servicios desde la base de datos
        from database.db import obtener_todos_servicios
        servicios = obtener_todos_servicios()
        
        # Añadir opción por defecto
        servicio_combo.addItem("Seleccione un servicio", None)
        
        # Añadir servicios al combo
        for servicio in servicios:
            cod_servicio, descripcion, precio, observaciones = servicio
            servicio_combo.addItem(descripcion, servicio)  # Guardar todos los datos del servicio como userData
        
        # Crear los demás campos con estilo consistente
        cantidad = self.create_styled_input("1")
        precio_ud = self.create_styled_input("0.00")
        total = self.create_styled_input("0.00")
        
        # Función para actualizar precio y total cuando se selecciona un servicio
        def on_servicio_selected(index):
            if index <= 0:  # Si es la opción "Seleccione un servicio"
                precio_ud.setText("")
                total.setText("")
                return
                
            servicio_data = servicio_combo.currentData()
            if servicio_data:
                # El precio está en la posición 2 (Cod_servicio, descripcion, precio, observaciones)
                precio_servicio = servicio_data[2]
                precio_ud.setText(str(precio_servicio))
                
                # Actualizar total
                try:
                    cant_valor = float(cantidad.text() or "1")
                    total_valor = precio_servicio * cant_valor
                    total.setText(f"{total_valor:.2f}")
                except ValueError:
                    total.setText("")
        
        # Función para actualizar total cuando cambia la cantidad
        def on_cantidad_changed():
            if servicio_combo.currentIndex() <= 0:
                return
                
            servicio_data = servicio_combo.currentData()
            if servicio_data:
                try:
                    precio_servicio = float(precio_ud.text() or "0")
                    cant_valor = float(cantidad.text() or "0")
                    total_valor = precio_servicio * cant_valor
                    total.setText(f"{total_valor:.2f}")
                except ValueError:
                    total.setText("")
        
        # Conectar eventos
        servicio_combo.currentIndexChanged.connect(on_servicio_selected)
        cantidad.textChanged.connect(on_cantidad_changed)
        
        fila_concepto.addWidget(servicio_combo, 3)
        fila_concepto.addWidget(cantidad, 1)
        fila_concepto.addWidget(precio_ud, 1)
        fila_concepto.addWidget(total, 1)

        fila_widget = QWidget()
        fila_widget.setLayout(fila_concepto)
        self.conceptos_filas_layout.addWidget(fila_widget)
        self.filas_conceptos.append((servicio_combo, cantidad, precio_ud, total))

        # Ajustar altura del scroll_area dinámicamente
        filas = len(self.filas_conceptos)
        altura_filas = filas * 50  # Altura por fila con margen
        max_altura = 350
        
        if altura_filas < max_altura:
            self.scroll_area.setFixedHeight(min(altura_filas + 30, max_altura))
        else:
            self.scroll_area.setFixedHeight(max_altura)
    
    def mostrar_calendario(self, event):
        """Muestra u oculta el calendario al hacer clic en el campo de fecha"""
        if self.calendario.isVisible():
            self.calendario.setVisible(False)
        else:
            # Establecer la fecha actual en el calendario
            fecha_texto = self.fecha.text()
            if fecha_texto:
                try:
                    dia, mes, anio = map(int, fecha_texto.split('/'))
                    fecha = QDate(anio, mes, dia)
                    self.calendario.setSelectedDate(fecha)
                except (ValueError, AttributeError):
                    # Si hay error en el formato, usar fecha actual
                    self.calendario.setSelectedDate(QDate.currentDate())
            else:
                self.calendario.setSelectedDate(QDate.currentDate())
            
            self.calendario.setVisible(True)

    def fecha_seleccionada(self, date):
        """Establece la fecha seleccionada en el campo de texto y oculta el calendario"""
        # Formatear como DD/MM/YYYY
        fecha_formateada = date.toString("dd/MM/yyyy")
        self.fecha.setText(fecha_formateada)
        self.calendario.setVisible(False)

    def handle_guardar_factura(self):
        """Guarda los datos de la factura en la base de datos"""
        # Verificar que se ha seleccionado un cliente
        if self.cliente_combo.currentIndex() <= 0:
            QMessageBox.warning(self, "Cliente no seleccionado", 
                "Debe seleccionar un cliente existente para crear una factura.")
            return
            
        # Verificar campos obligatorios
        if not self.nombre.text().strip() or not self.nif.text().strip() or not self.fecha.text().strip():
            QMessageBox.warning(self, "Datos incompletos", 
                "Por favor complete al menos el nombre del cliente, NIF y fecha.")
            return
            
        # Recoger los datos del cliente
        cliente_datos = self.cliente_combo.currentData()
        if not cliente_datos:
            QMessageBox.warning(self, "Cliente no válido", 
                "El cliente seleccionado no es válido. Por favor seleccione otro cliente.")
            return
                    
        cod_cliente = cliente_datos[0]  # El ID del cliente está en la posición 0
            
        # Recoger los conceptos para calcular el total
        conceptos = []
        total_factura = 0
            
        for servicio_combo, cant, precio, total in self.filas_conceptos:
            # Verificar que se haya seleccionado un servicio
            if servicio_combo.currentIndex() <= 0:
                continue
                    
            # Obtener datos del servicio seleccionado
            servicio_data = servicio_combo.currentData()
            if not servicio_data:
                continue
                
            # El ID del servicio está en la posición 0
            cod_servicio = servicio_data[0]
                    
            try:
                cantidad = float(cant.text() or "0")
                precio_unitario = float(precio.text() or "0")
                total_linea = float(total.text() or "0")
                    
                # Validar que los datos sean consistentes
                if total_linea == 0 and (cantidad > 0 and precio_unitario > 0):
                    total_linea = cantidad * precio_unitario
                        
                if total_linea > 0:
                    total_factura += total_linea
                        
                    conceptos.append({
                        "cod_servicio": cod_servicio,
                        "cantidad": cantidad,
                        "precio_ud": precio_unitario,
                        "total": total_linea
                    })
                        
            except ValueError:
                continue
        
        # Si no hay conceptos válidos, mostrar mensaje
        if not conceptos:
            QMessageBox.warning(self, "Datos incompletos", 
                "Debe añadir al menos una línea de concepto válida con un servicio seleccionado.")
            return
        
        try:
            # Importar funciones necesarias
            from database.db import insertar_factura, insertar_detalle_linea
            
            # Obtener observaciones
            observaciones = self.observaciones_input.toPlainText().strip()
            
            # Insertar directamente la factura con el código de cliente seleccionado
            factura_id = insertar_factura(
                self.fecha.text().strip(),
                total_factura,
                cod_cliente,
                observaciones
            )
            
            if not factura_id:
                raise Exception("No se pudo crear la factura")
                
            # Insertar detalles de línea usando los servicios seleccionados
            for i, concepto in enumerate(conceptos, 1):
                # Insertar detalle de línea
                insertar_detalle_linea(
                    factura_id,
                    i,  # Número de línea
                    concepto["cantidad"],
                    concepto["precio_ud"],
                    concepto["cod_servicio"]
                )
            
            # Mostrar mensaje de éxito
            QMessageBox.information(
                self,
                "Factura guardada",
                f"La factura #{factura_id} se ha guardado correctamente en la base de datos."
            )
                
            # Limpiar el formulario después de guardar
            self.limpiar_formulario()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la factura: {str(e)}")

    def limpiar_formulario(self):
        """Limpia todos los campos del formulario"""
        # Reiniciar selector de cliente
        self.cliente_combo.setCurrentIndex(0)
        
        # Limpiar campos del cliente
        self.nombre.clear()
        self.direccion.clear()
        self.cp.clear()
        self.nif.clear()
        self.telefono.clear()
        self.email.clear()

        # Establecer fecha actual
        fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
        self.fecha.setText(fecha_actual)
        
        # Limpiar conceptos
        self.setup_conceptos_area()

        # Limpiar observaciones
        self.observaciones_input.clear()
        
