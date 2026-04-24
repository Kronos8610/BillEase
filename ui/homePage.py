from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QFrame, QApplication, QFileDialog, QScrollArea,
    QGroupBox, QMessageBox, QComboBox
)
import database.db as db
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from utils.globals import (
    TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND,
    TITLE_FONT, SUBTITLE_FONT, BODY_FONT
)
class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        
        # Crear el layout principal
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Contenedor principal para las facturas/clientes/servicios
        container = QGroupBox()
        container.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 10px;
                border: 1px solid {ALMOND};
            }}
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        
        # Encabezado con título y selector
        header = QHBoxLayout()
        
        # Título dinámico según selección
        self.title = QLabel("Facturas")
        self.title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.title.setStyleSheet(f"color: {TYRIAN_PURPLE}; margin-bottom: 10px;")
        
        # Añadir desplegable para seleccionar categoría
        self.categoria_combo = QComboBox()
        self.categoria_combo.addItems(["Facturas", "Clientes", "Servicios"])
        self.categoria_combo.setMinimumWidth(150)
        self.categoria_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: white;
                border: 1px solid {BYZANTIUM};
                border-radius: 4px;
                padding: 5px;
                color: {BYZANTIUM};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                border: 1px solid {BYZANTIUM};
                selection-background-color: {LAVENDER_PINK};
                selection-color: {TYRIAN_PURPLE};
            }}
        """)
        self.categoria_combo.currentIndexChanged.connect(self.cambiar_categoria)
        
        # Botón de actualizar
        self.refresh_btn = QPushButton("🔄 Actualizar")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(f"""
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
        self.refresh_btn.clicked.connect(self.cargar_datos)
        
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.categoria_combo)
        header.addSpacing(10)
        header.addWidget(self.refresh_btn)
        
        container_layout.addLayout(header)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
        container_layout.addWidget(separator)
        
        # Scroll area para la lista de elementos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 5px;
            }
        """)
        
        # Widget para contener la lista de elementos
        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout(self.items_widget)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(10)
        
        scroll.setWidget(self.items_widget)
        container_layout.addWidget(scroll)
        
        # Mensaje cuando no hay elementos (con contenedor)
        self.no_items_container = QWidget()
        no_items_layout = QVBoxLayout(self.no_items_container)
        no_items_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.no_items_label = QLabel("No se encontraron elementos")
        self.no_items_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_items_label.setStyleSheet(f"color: {BYZANTIUM}; font-style: italic; margin: 20px 0;")
        no_items_layout.addWidget(self.no_items_label)
        
        # Añadir contenedor al layout
        self.items_layout.addWidget(self.no_items_container)
        
        # Añadir contenedor al layout principal
        self.main_layout.addWidget(container)
        
        # Cargar datos iniciales (facturas por defecto)
        self.cargar_datos()
    
    def cambiar_categoria(self):
        """Actualiza la interfaz según la categoría seleccionada"""
        categoria = self.categoria_combo.currentText()
        self.title.setText(categoria)
        self.cargar_datos()
    
    def cargar_datos(self):
        """Carga los datos según la categoría seleccionada"""
        categoria = self.categoria_combo.currentText()
        
        if categoria == "Facturas":
            self.cargar_facturas()
        elif categoria == "Clientes":
            self.cargar_clientes()
        elif categoria == "Servicios":
            self.cargar_servicios()
    
    def cargar_facturas(self):
        """Carga las facturas desde la base de datos y las muestra en la interfaz"""
        # Primero, limpiar la lista actual
        self.limpiar_items()
        
        # Obtener facturas de la base de datos
        from database.db import obtener_todas_facturas
        facturas = obtener_todas_facturas()
        
        if facturas:
            self.no_items_container.hide()

            # Crear el encabezado de la tabla
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 5, 10, 5)
            
            headers = [
                ("Nº Factura", 1),
                ("Fecha", 2),
                ("Cliente", 4),
                ("", 1),  # Columna para acción PDF
                ("", 1),  # Columna para acción Editar
                ("", 1)   # Columna para acción Eliminar
            ]
            
            for title, stretch in headers:
                label = QLabel(title)
                label.setFont(SUBTITLE_FONT)
                label.setStyleSheet(f"color: {TYRIAN_PURPLE};")
                header_layout.addWidget(label, stretch)
            
            self.items_layout.addWidget(header)
            
            # Separador después del encabezado
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
            self.items_layout.addWidget(separator)
            
            # Añadir cada factura
            for i, factura in enumerate(facturas):
                fila = self.crear_factura_item(factura, i % 2 == 0)
                self.items_layout.addWidget(fila)
            
            # Añadir espacio al final
            self.items_layout.addStretch()
            
            # Ocultar el mensaje de "No hay elementos"
            self.no_items_label.hide()
        else:
            # Mostrar mensaje cuando no hay facturas
            self.no_items_label.setText("No se encontraron facturas en la base de datos")
            self.no_items_container.show()
    
    def cargar_clientes(self):
        """Carga los clientes desde la base de datos y los muestra en la interfaz"""
        # Primero, limpiar la lista actual
        self.limpiar_items()
        
        # Obtener clientes de la base de datos
        from database.db import obtener_clientes
        clientes = obtener_clientes()
        
        if clientes:

            self.no_items_container.hide()
            # Crear el encabezado de la tabla
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 5, 10, 5)
            
            headers = [
                ("ID", 1),
                ("NIF/CIF", 2),
                ("Nombre", 4),
                ("Teléfono", 2),
                ("", 1)   # Columna para acción Eliminar
            ]
            
            for title, stretch in headers:
                label = QLabel(title)
                label.setFont(SUBTITLE_FONT)
                label.setStyleSheet(f"color: {TYRIAN_PURPLE};")
                header_layout.addWidget(label, stretch)
            
            self.items_layout.addWidget(header)
            
            # Separador después del encabezado
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
            self.items_layout.addWidget(separator)
            
            # Añadir cada cliente
            for i, cliente in enumerate(clientes):
                fila = self.crear_cliente_item(cliente, i % 2 == 0)
                self.items_layout.addWidget(fila)
            
            # Añadir espacio al final
            self.items_layout.addStretch()
            
            # Ocultar el mensaje de "No hay elementos"
            self.no_items_label.hide()
        else:
            # Mostrar mensaje cuando no hay clientes
            self.no_items_label.setText("No se encontraron clientes en la base de datos")
            self.no_items_container.show()
    
    def cargar_servicios(self):
        """Carga los servicios desde la base de datos y los muestra en la interfaz"""
        # Primero, limpiar la lista actual
        self.limpiar_items()
        
        # Obtener servicios de la base de datos
        from database.db import obtener_todos_servicios
        servicios = obtener_todos_servicios()
        
        if servicios:
            self.no_items_container.hide()
            # Crear el encabezado de la tabla
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 5, 10, 5)
            
            headers = [
                ("ID", 1),
                ("Descripción", 4),
                ("Precio", 2),
                ("", 1)   # Columna para acción Eliminar
            ]
            
            for title, stretch in headers:
                label = QLabel(title)
                label.setFont(SUBTITLE_FONT)
                label.setStyleSheet(f"color: {TYRIAN_PURPLE};")
                header_layout.addWidget(label, stretch)
            
            self.items_layout.addWidget(header)
            
            # Separador después del encabezado
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px;")
            self.items_layout.addWidget(separator)
            
            # Añadir cada servicio
            for i, servicio in enumerate(servicios):
                fila = self.crear_servicio_item(servicio, i % 2 == 0)
                self.items_layout.addWidget(fila)
            
            # Añadir espacio al final
            self.items_layout.addStretch()
            
            # Ocultar el mensaje de "No hay elementos"
            self.no_items_label.hide()
        else:
            # Mostrar mensaje cuando no hay servicios
            self.no_items_label.setText("No se encontraron servicios en la base de datos")
            self.no_items_container.show()
    
    def limpiar_items(self):
        """Limpia todos los elementos de la lista actual"""
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.no_items_container:  
                widget.deleteLater()
        
        if self.no_items_container.parent() is None:
            self.items_layout.addWidget(self.no_items_container)
    
    def crear_factura_item(self, factura, alternate_color=False):
        """Crea un elemento de lista para una factura"""
        # Desempaquetar datos de la factura
        num_factura, fecha, total, cod_cliente, observaciones = factura
        
        # Obtener el nombre del cliente
        from database.db import obtener_cliente_por_id
        cliente = obtener_cliente_por_id(cod_cliente)
        nombre_cliente = cliente[2] if cliente else "Cliente desconocido"  # Índice 2 = nombre_o_razon_social
        
        # Crear widget para la fila
        item = QWidget()
        if alternate_color:
            item.setStyleSheet(f"background-color: {CHAMPAGNE_PINK}; border-radius: 5px;")
        else:
            item.setStyleSheet("background-color: #F8F8F8; border-radius: 5px;")
        
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(10, 10, 10, 10)
        
        # Datos de la factura
        num_label = QLabel(str(num_factura))
        fecha_label = QLabel(fecha)
        cliente_label = QLabel(nombre_cliente)
        
        # Botón de crear PDF
        pdf_btn = QPushButton("Crear PDF")
        pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pdf_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BYZANTIUM};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
            }}
            QPushButton:hover {{
                background-color: {TYRIAN_PURPLE};
            }}
        """)
        pdf_btn.clicked.connect(lambda: self.crear_pdf_factura(num_factura))
        
        # Botón de editar  (NUEVO)
        edit_btn = QPushButton("Editar")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LAVENDER_PINK};
                color: {TYRIAN_PURPLE};
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FF8CB6;
            }}
        """)
        edit_btn.clicked.connect(lambda: self.abrir_editar_factura(num_factura))  # NUEVO


        # NUEVO: Botón de eliminar
        delete_btn = QPushButton("🗑️")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.eliminar_factura(num_factura))
        
        # Añadir elementos al layout
        item_layout.addWidget(num_label, 1)
        item_layout.addWidget(fecha_label, 2)
        item_layout.addWidget(cliente_label, 4)
        item_layout.addWidget(pdf_btn, 1)
        item_layout.addWidget(edit_btn, 1)
        item_layout.addWidget(delete_btn, 1)
        
        return item
    
    def crear_cliente_item(self, cliente, alternate_color=False):
        """Crea un elemento de lista para un cliente"""
        # Desempaquetar datos del cliente
        cod_cliente, tipo_cliente, nombre, direccion, telefono, cod_postal, cifnif, observaciones, *_ = cliente
        
        # Crear widget para la fila
        item = QWidget()
        if alternate_color:
            item.setStyleSheet(f"background-color: {CHAMPAGNE_PINK}; border-radius: 5px;")
        else:
            item.setStyleSheet("background-color: #F8F8F8; border-radius: 5px;")
        
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(10, 10, 10, 10)
        
        # Datos del cliente
        id_label = QLabel(str(cod_cliente))
        cifnif_label = QLabel(cifnif)
        nombre_label = QLabel(nombre)
        telefono_label = QLabel(str(telefono) if telefono else "-")
        
        # Botón de eliminar
        delete_btn = QPushButton("🗑️")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.eliminar_cliente(cod_cliente))
        
        # Añadir elementos al layout
        item_layout.addWidget(id_label, 1)
        item_layout.addWidget(cifnif_label, 2)
        item_layout.addWidget(nombre_label, 4)
        item_layout.addWidget(telefono_label, 2)
        item_layout.addWidget(delete_btn, 1)
        
        return item
    
    def crear_servicio_item(self, servicio, alternate_color=False):
        """Crea un elemento de lista para un servicio"""
        # Desempaquetar datos del servicio
        cod_servicio, descripcion, precio, observaciones = servicio
        
        # Crear widget para la fila
        item = QWidget()
        if alternate_color:
            item.setStyleSheet(f"background-color: {CHAMPAGNE_PINK}; border-radius: 5px;")
        else:
            item.setStyleSheet("background-color: #F8F8F8; border-radius: 5px;")
        
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(10, 10, 10, 10)
        
        # Datos del servicio
        id_label = QLabel(str(cod_servicio))
        descripcion_label = QLabel(descripcion)
        precio_label = QLabel(f"{precio:.2f} €")
        
        # Botón de eliminar
        delete_btn = QPushButton("🗑️")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.eliminar_servicio(cod_servicio))
        
        # Añadir elementos al layout
        item_layout.addWidget(id_label, 1)
        item_layout.addWidget(descripcion_label, 4)
        item_layout.addWidget(precio_label, 2)
        item_layout.addWidget(delete_btn, 1)
        
        return item

    def crear_pdf_factura(self, num_factura):
        """Genera un PDF para la factura seleccionada"""
        # El código existente sin cambios
        # Obtener datos de la factura desde la base de datos
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Guardar PDF", 
            f"factura_{num_factura}.pdf", 
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                # Importar funciones necesarias
                from database.db import obtener_factura_por_id, obtener_cliente_por_id, obtener_detalles_factura
                
                # 1. Obtener la factura por ID
                factura = obtener_factura_por_id(num_factura)
                if not factura:
                    QMessageBox.warning(self, "Error", "No se encontró la factura")
                    return
                
                fecha = factura[1]
                total = factura[2]
                cod_cliente = factura[3]
                ref_obra = factura[4] or ""  # Observaciones como ref_obra
                
                # 2. Obtener detalles de la factura
                detalles = obtener_detalles_factura(num_factura)
                if not detalles:
                    QMessageBox.warning(self, "Error", "No se encontraron detalles para esta factura")
                    return
                
                # 3. Obtener datos del cliente
                cliente = obtener_cliente_por_id(cod_cliente)
                if not cliente:
                    QMessageBox.warning(self, "Error", "No se encontró el cliente asociado")
                    return
                    
                # 4. Preparar conceptos
                conceptos = []
                for detalle in detalles:
                    num_factura, num_linea, cantidad, precio_ud, cod_servicio, descripcion = detalle
                    total_linea = float(cantidad) * float(precio_ud)
                    
                    conceptos.append({
                        "descripcion": descripcion,
                        "cantidad": str(cantidad),
                        "precio_ud": str(precio_ud),
                        "total": str(total_linea)
                    })
                
                # 5. Preparar datos para el PDF
                datos = {
                    "nombre": cliente[2],  # nombre_o_razon_social
                    "direccion": cliente[3] or "",  # direccion
                    "cp": cliente[5] or "",  # cod_postal
                    "nif": cliente[6] or "",  # CIFNIF
                    "telefono": str(cliente[4]) if cliente[4] else "",  # telefono
                    "email": "",  # No disponible en la estructura actual
                    "ref_obra": ref_obra,
                    "fecha": fecha,
                    "num_factura": str(num_factura),
                    "conceptos": conceptos,
                    "vencimiento": "",  # No disponible en la estructura actual
                    "domiciliacion": "",  # No disponible en la estructura actual
                    "cuenta": ""  # No disponible en la estructura actual
                }
                
                # 6. Generar el PDF
                generar_factura_pdf(datos, file_path)
                
                # 7. Mostrar mensaje de éxito
                QMessageBox.information(self, "PDF Generado", 
                    f"El PDF de la factura #{num_factura} se ha generado correctamente.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo generar el PDF: {str(e)}")

    def eliminar_factura(self, num_factura):
        """Elimina una factura de la base de datos"""
        confirmacion = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar la factura #{num_factura}?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirmacion == QMessageBox.StandardButton.Yes:
            try:
                if db.eliminar_factura(num_factura):
                    QMessageBox.information(self, "Éxito", f"Factura #{num_factura} eliminada correctamente.")
                    self.cargar_facturas()  # Actualizar la lista
                else:
                    QMessageBox.warning(self, "Error", "No se pudo eliminar la factura.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar la factura: {str(e)}")

    def eliminar_cliente(self, cod_cliente):
        """Elimina un cliente de la base de datos"""
        # Verificar primero si el cliente tiene facturas asociadas
        facturas = db.obtener_facturas_cliente(cod_cliente)
        
        if facturas:
            QMessageBox.warning(
                self, 
                "No se puede eliminar", 
                f"El cliente #{cod_cliente} tiene {len(facturas)} factura(s) asociada(s).\n"
                f"Elimine primero las facturas antes de eliminar este cliente."
            )
            return
            
        confirmacion = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar el cliente #{cod_cliente}?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirmacion == QMessageBox.StandardButton.Yes:
            try:
                if db.eliminar_cliente(cod_cliente):
                    QMessageBox.information(self, "Éxito", f"Cliente #{cod_cliente} eliminado correctamente.")
                    self.cargar_clientes()  # Actualizar la lista
                else:
                    QMessageBox.warning(self, "Error", "No se pudo eliminar el cliente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar el cliente: {str(e)}")

    def eliminar_servicio(self, cod_servicio):
        """Elimina un servicio de la base de datos"""
        # Verificar si el servicio está en uso en alguna factura
        from database.db import verificar_servicio_en_uso
        en_uso = verificar_servicio_en_uso(cod_servicio)
        
        if en_uso:
            QMessageBox.warning(
                self, 
                "No se puede eliminar", 
                f"El servicio #{cod_servicio} está siendo utilizado en facturas.\n"
                f"No es posible eliminarlo."
            )
            return
            
        confirmacion = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar el servicio #{cod_servicio}?\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirmacion == QMessageBox.StandardButton.Yes:
            try:
                if db.eliminar_servicio(cod_servicio):
                    QMessageBox.information(self, "Éxito", f"Servicio #{cod_servicio} eliminado correctamente.")
                    self.cargar_servicios()  # Actualizar la lista
                else:
                    QMessageBox.warning(self, "Error", "No se pudo eliminar el servicio.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar el servicio: {str(e)}")
    
    def abrir_editar_factura(self, num_factura):
        try:
            from ui.editarFactura import EditarFactura
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el editor:\n{e}")
            return

        # Normaliza el id de factura por si viene con texto tipo "Nº 001"
        try:
            num = int(num_factura)
        except Exception:
            numeros = re.sub(r"\D", "", str(num_factura))
            if not numeros:
                QMessageBox.warning(self, "Factura inválida", f"ID de factura no válido: {num_factura}")
                return
            num = int(numeros)

        dlg = EditarFactura(num, parent=self)
        try:
            dlg.saved.connect(self.cargar_facturas)
        except Exception:
            pass

        dlg.exec()  # <- muestra la ventana modal de edición


def generar_factura_pdf(datos, file_path):
    import sqlite3
    
    # Obtener datos del autónomo directamente desde la base de datos
    conn = None
    autonomo = None
    try:
        conn = sqlite3.connect("BillEase.db")
        cursor = conn.cursor()
        
        # Consultar estructura de tabla para confirmar nombres de columnas
        cursor.execute("PRAGMA table_info(Autonomo)")
        columnas = [col[1] for col in cursor.fetchall()]
        print(f"Columnas en tabla Autonomo: {columnas}")
        
        # Consulta usando los nombres reales de las columnas
        cursor.execute("SELECT DNI, nombre, apellido, direccion, codigo_postal, telefono, email FROM Autonomo LIMIT 1")
        autonomo = cursor.fetchone()
        print(f"Datos del autónomo obtenidos: {autonomo}")
    except Exception as e:
        print(f"Error al obtener datos del autónomo: {e}")
    finally:
        if conn:
            conn.close()
    
    # Extraer datos del autónomo de forma segura
    dni = autonomo[0] if len(autonomo) > 0 else "N/A"
    nombre = autonomo[1] if len(autonomo) > 1 else "N/A"
    apellido = autonomo[2] if len(autonomo) > 2 else "N/A" 
    direccion = autonomo[3] if len(autonomo) > 3 else "N/A"
    codigo_postal = autonomo[4] if len(autonomo) > 4 else "N/A"
    telefono = autonomo[5] if len(autonomo) > 5 else "N/A"
    email = autonomo[6] if len(autonomo) > 6 else "N/A"
    
    # Comenzar a generar el PDF
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from utils.globals import TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND
    
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    
    # Color de fondo del encabezado
    c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
    c.rect(0, height-120, width, 120, fill=True, stroke=False)
    
    # Línea decorativa
    c.setStrokeColor(colors.HexColor(LAVENDER_PINK))
    c.setLineWidth(5)
    c.line(0, height-120, width, height-120)
    
    # Título de factura
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
    c.drawCentredString(width/2, height - 50, "FACTURA")
    
    # Información de factura en encabezado
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(BYZANTIUM))
    c.drawString(width/2, height - 75, f"Nº Factura: {datos['num_factura']}")
    c.drawString(width/2, height - 90, f"Fecha: {datos['fecha']}")
    
    # Sección 1: Datos del autónomo (izquierda)
    y = height - 140
    
    # Fondo y borde
    c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
    c.rect(30, y-90, 250, 90, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor(ALMOND))
    c.setLineWidth(1)
    c.rect(30, y-90, 250, 90, fill=False, stroke=True)
    
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
    c.drawString(40, y, "DATOS DEL EMISOR")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(40, y - 20, f"{nombre} {apellido}")  # Nombre y apellido
    c.drawString(40, y - 35, f"NIF: {dni}")  # DNI/NIF
    c.drawString(40, y - 50, f"Dirección: {direccion}")  # Dirección
    c.drawString(40, y - 65, f"CP: {codigo_postal}")  # Código postal
    c.drawString(40, y - 80, f"Teléfono: {telefono}")  # Teléfono
    
    # Sección 2: Datos del cliente (derecha)
    c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
    c.rect(width-280, y-90, 250, 90, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor(ALMOND))
    c.rect(width-280, y-90, 250, 90, fill=False, stroke=True)
    
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
    c.drawString(width-270, y, "CLIENTE")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(width-270, y - 20, f"{datos['nombre']}")
    c.drawString(width-270, y - 35, f"NIF/CIF: {datos['nif']}")
    c.drawString(width-270, y - 50, f"Dirección: {datos['direccion']}")
    c.drawString(width-270, y - 65, f"CP: {datos['cp']}")
    c.drawString(width-270, y - 80, f"Teléfono: {datos['telefono']}")
    
    # Sección 3: Detalles de la factura
    y = y - 120
    
    # Si hay una referencia de obra, mostrarla
    if datos['ref_obra']:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor(BYZANTIUM))
        c.drawString(40, y, f"Referencia: {datos['ref_obra']}")
        y -= 20
    
    # Encabezado de la tabla de conceptos
    y -= 10
    c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
    c.rect(30, y, width-60, 20, fill=True, stroke=False)
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.white)
    c.drawString(40, y+5, "DETALLE DE CONCEPTOS")
    
    # Encabezado de columnas
    y -= 25
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(BYZANTIUM))
    c.drawString(40, y, "Descripción")
    c.drawString(300, y, "Cantidad")
    c.drawString(360, y, "Precio Ud.")
    c.drawString(450, y, "Total")
    
    # Línea bajo el encabezado
    c.setStrokeColor(colors.HexColor(ALMOND))
    c.line(40, y-5, width-40, y-5)
    
    # Contenido de la tabla
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    y -= 20
    
    # Para calcular el subtotal
    subtotal = 0
    
    # Alternar fondo de filas
    row = 0
    for concepto in datos.get("conceptos", []):
        # Fondo alternante
        if row % 2 == 0:
            c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
            c.rect(30, y-5, width-60, 20, fill=True, stroke=False)
        
        c.setFillColor(colors.black)
        
        # Descripción con límite de longitud
        descripcion = concepto.get("descripcion", "")
        if len(descripcion) > 40:
            descripcion = descripcion[:37] + "..."
        
        c.drawString(40, y, descripcion)
        
        cantidad = concepto.get("cantidad", "")
        precio_ud = concepto.get("precio_ud", "")
        total_linea = concepto.get("total", "")
        
        c.drawString(300, y, cantidad)
        c.drawString(360, y, f"{float(precio_ud):.2f} €")
        c.drawString(450, y, f"{float(total_linea):.2f} €")
        
        # Sumar al subtotal
        subtotal += float(total_linea)
        
        y -= 20
        row += 1
    
    # Calcular importes
    iva = subtotal * 0.21
    total = subtotal + iva
    
    # Línea separadora
    y -= 10
    c.setStrokeColor(colors.HexColor(ALMOND))
    c.line(40, y, width-40, y)
    
    # Resumen económico
    y -= 30
    c.setFillColor(colors.HexColor(LAVENDER_PINK))
    c.rect(width-250, y-60, 210, 60, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor(ALMOND))
    c.rect(width-250, y-60, 210, 60, fill=False, stroke=True)
    
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
    c.drawString(width-240, y, "Subtotal:")
    c.drawString(width-240, y-20, "IVA (21%):")
    c.drawString(width-240, y-40, "TOTAL:")
    
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawRightString(width-50, y, f"{subtotal:.2f} €")
    c.drawRightString(width-50, y-20, f"{iva:.2f} €")
    c.drawRightString(width-50, y-40, f"{total:.2f} €")
    
    # Observaciones si existen
    y -= 90
    if datos.get('ref_obra'):
        c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
        c.rect(30, y-40, width-60, 40, fill=True, stroke=False)
        c.setStrokeColor(colors.HexColor(ALMOND))
        c.rect(30, y-40, width-60, 40, fill=False, stroke=True)
        
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
        c.drawString(40, y, "OBSERVACIONES")
        
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        c.drawString(40, y-20, datos['ref_obra'])
    
    # Datos bancarios si existen
    y -= 60
    if datos.get('cuenta') or datos.get('vencimiento'):
        c.setFillColor(colors.HexColor(CHAMPAGNE_PINK))
        c.rect(30, y-40, width-60, 40, fill=True, stroke=False)
        c.setStrokeColor(colors.HexColor(ALMOND))
        c.rect(30, y-40, width-60, 40, fill=False, stroke=True)
        
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor(TYRIAN_PURPLE))
        c.drawString(40, y, "DATOS BANCARIOS")
        
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        texto_bancario = []
        if datos.get('vencimiento'):
            texto_bancario.append(f"Vencimiento: {datos['vencimiento']}")
        if datos.get('cuenta'):
            texto_bancario.append(f"Cuenta: {datos['cuenta']}")
            
        c.drawString(40, y-20, " | ".join(texto_bancario))

    c.showPage()
    c.save()

