from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QFrame, QApplication, QFileDialog, QScrollArea,
    QGroupBox, QMessageBox, QComboBox
)
import database.db as db
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from core.taxes import calcular, desde_base, desde_detalles, formatear
from documents.invoice_pdf import generar_documento_pdf
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
                ("Base", 2),    # importe sin IVA
                ("Total", 2),   # el que paga el cliente, IVA incluido
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
        # La columna `total` de la tabla guarda en realidad la base imponible
        # (defecto 01). Se calcula el total con la MISMA función que usa el PDF,
        # así no pueden discrepar. La fase 2 separa las columnas en la base.
        num_factura, fecha, base_guardada, cod_cliente, observaciones = factura
        totales = desde_base(base_guardada)
        
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

        base_label = QLabel(f"{formatear(totales.base)} €")
        base_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        base_label.setStyleSheet(f"color: {BYZANTIUM};")

        total_label = QLabel(f"{formatear(totales.total)} €")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_label.setFont(SUBTITLE_FONT)
        total_label.setStyleSheet(f"color: {TYRIAN_PURPLE};")
        total_label.setToolTip(
            f"Base {formatear(totales.base)} € + IVA {formatear(totales.cuota_iva)} €"
        )
        
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
        item_layout.addWidget(base_label, 2)
        item_layout.addWidget(total_label, 2)
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
        """Genera el PDF de una factura y lo guarda donde elija el usuario."""
        from database.db import (
            obtener_cliente_por_id,
            obtener_datos_autonomo,
            obtener_detalles_factura,
            obtener_factura_por_id,
        )

        factura = obtener_factura_por_id(num_factura)
        if not factura:
            QMessageBox.warning(self, "Factura no encontrada",
                f"No se encontró la factura #{num_factura}.")
            return

        detalles = obtener_detalles_factura(num_factura)
        if not detalles:
            QMessageBox.warning(self, "Factura sin conceptos",
                f"La factura #{num_factura} no tiene ninguna línea, así que no "
                "hay nada que imprimir. Ábrela y añade al menos un concepto.")
            return

        cliente = obtener_cliente_por_id(factura[3])
        if not cliente:
            QMessageBox.warning(self, "Cliente no encontrado",
                f"La factura #{num_factura} apunta a un cliente que ya no existe.")
            return

        autonomo = obtener_datos_autonomo()
        if not autonomo:
            QMessageBox.warning(self, "Faltan tus datos",
                "No se han podido leer tus datos de autónomo, y sin ellos la "
                "factura no es válida. Revísalos antes de emitirla.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", f"factura_{num_factura}.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        # Las líneas y los totales se calculan una sola vez, con la misma
        # función que alimenta el listado: el papel y la pantalla no pueden
        # decir cifras distintas (defecto 01).
        lineas = desde_detalles(detalles)
        totales = calcular(lineas)

        datos = {
            "tipo": "factura",
            "numero": str(num_factura),
            "fecha": factura[1],
            "emisor": {
                "nombre": f"{autonomo[1]} {autonomo[2]}".strip(),
                "nif": autonomo[0],
                "direccion": autonomo[3],
                "poblacion": autonomo[4],
                "telefono": autonomo[5],
                "email": autonomo[6],
            },
            "cliente": {
                "nombre": cliente[2],
                "nif": cliente[6],
                "direccion": cliente[3],
                "poblacion": cliente[5],
                "telefono": cliente[4],
                "email": cliente[8] if len(cliente) > 8 else "",
            },
            "lineas": lineas,
            "nota": factura[4] or "",
        }

        try:
            resultado = generar_documento_pdf(datos, file_path, totales=totales)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo generar el PDF",
                f"La factura #{num_factura} no se ha podido escribir en "
                f"{file_path}.\n\nMotivo: {e}")
            return

        paginas = resultado["paginas"]
        QMessageBox.information(self, "PDF generado",
            f"Factura #{num_factura} · {formatear(totales.total)} €\n"
            f"{paginas} página{'s' if paginas != 1 else ''} en {file_path}")

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
