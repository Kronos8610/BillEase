from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit,
    QGroupBox, QMessageBox, QFormLayout, QTextEdit, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDoubleValidator
from utils.globals import (
    TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND,
    TITLE_FONT, SUBTITLE_FONT, BODY_FONT
)

class CrearServicio(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Contenedor principal
        container = QGroupBox()
        container.setStyleSheet(f"""
            QGroupBox {{
                background-color: white;
                border-radius: 10px;
                border: 1px solid {ALMOND};
            }}
        """)
        
        # Establecer un ancho máximo para el contenedor
        container.setMaximumWidth(700)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Crear Nuevo Servicio")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            color: {TYRIAN_PURPLE};
            margin-bottom: 15px;
            background-color: transparent;
        """)
        container_layout.addWidget(title)
        
        # Formulario de servicio
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Campos del formulario
        self.descripcion_input = self.create_styled_input("Ej: Instalación de espejos")
        self.precio_input = self.create_styled_input("Ej: 75.50")
        self.observaciones_input = QTextEdit()
        
        # Aplicar validador numérico al campo de precio
        validator = QDoubleValidator()
        validator.setBottom(0.0)  # Precio mínimo: 0
        validator.setDecimals(2)  # Dos decimales
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.precio_input.setValidator(validator)
        
        # Estilo para el campo de observaciones
        self.observaciones_input.setMinimumHeight(100)
        self.observaciones_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                border: 1px solid {ALMOND};
                border-radius: 4px;
                padding: 5px;
            }}
            QTextEdit:focus {{
                border: 1px solid {BYZANTIUM};
            }}
        """)
        
        # Etiquetas de los campos
        descripcion_label = self.create_form_label("Descripción:*")
        precio_label = self.create_form_label("Precio:*")
        observaciones_label = self.create_form_label("Observaciones:")
        
        # Agregar campos al formulario
        form_layout.addRow(descripcion_label, self.descripcion_input)
        form_layout.addRow(precio_label, self.precio_input)
        form_layout.addRow(observaciones_label, self.observaciones_input)
        
        container_layout.addLayout(form_layout)
        
        # Nota sobre campos obligatorios
        nota = QLabel("* Campos obligatorios")
        nota.setStyleSheet("""
            color: gray; 
            font-style: italic; 
            margin-top: 5px;
            background-color: transparent;
        """)
        container_layout.addWidget(nota)
        
        # Espaciador para empujar los botones hacia abajo
        container_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("Limpiar")
        self.clear_btn.setFont(BODY_FONT)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {TYRIAN_PURPLE};
                border: 1px solid {TYRIAN_PURPLE};
                border-radius: 5px;
                padding: 8px 15px;
            }}
            QPushButton:hover {{
                background-color: #F8F8F8;
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_form)
        
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setFont(BODY_FONT)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TYRIAN_PURPLE};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }}
            QPushButton:hover {{
                background-color: {BYZANTIUM};
            }}
        """)
        self.save_btn.clicked.connect(self.save_service)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.save_btn)
        
        container_layout.addLayout(buttons_layout)
        
        layout.addWidget(container)
        layout.setAlignment(container, Qt.AlignmentFlag.AlignHCenter)
    
    def create_styled_input(self, placeholder):
        """Crear un campo de entrada"""
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
    
    def create_form_label(self, text):
        """Crear una etiqueta para el formulario"""
        label = QLabel(text)
        label.setFont(BODY_FONT)
        label.setStyleSheet(f"""
            QLabel {{
                color: {BYZANTIUM};
                background-color: transparent;
            }}
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label
    
    def clear_form(self):
        """Limpia todos los campos del formulario"""
        self.descripcion_input.clear()
        self.precio_input.clear()
        self.observaciones_input.clear()
        self.descripcion_input.setFocus()
    
    def show_error_message(self, message):
        """Muestra un mensaje de error"""
        QMessageBox.critical(self, "Error", message)
    
    def show_success_message(self, message):
        """Muestra un mensaje de éxito"""
        QMessageBox.information(self, "Éxito", message)
    
    def save_service(self):
        """Guardar los datos del servicio en la base de datos"""
        # Recoger datos del formulario
        servicio = {
            'descripcion': self.descripcion_input.text().strip(),
            'precio': self.precio_input.text().strip(),
            'observaciones': self.observaciones_input.toPlainText().strip()
        }
        
        # Verificar campos obligatorios
        if not servicio['descripcion']:
            self.show_error_message("La descripción del servicio es obligatoria.")
            return
        
        if not servicio['precio']:
            self.show_error_message("El precio del servicio es obligatorio.")
            return
        
        try:
            # Convertir precio a float y validar
            precio = float(servicio['precio'].replace(',', '.'))
            if precio <= 0:
                self.show_error_message("El precio debe ser mayor que cero.")
                return
                
            # Importar función para insertar servicio
            from database.db import insertar_servicio
            
            # Intentar guardar el servicio
            servicio_id = insertar_servicio(
                servicio['descripcion'],
                precio,
                servicio['observaciones']
            )
            
            if servicio_id:
                self.show_success_message(f"Servicio #{servicio_id} añadido correctamente.")
                self.clear_form()
            else:
                self.show_error_message("No se pudo guardar el servicio. Verifica los datos.")
        
        except ValueError:
            self.show_error_message("El formato del precio no es válido. Use solo números y punto decimal.")
        except Exception as e:
            self.show_error_message(f"Error al guardar: {str(e)}")