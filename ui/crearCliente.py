from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit,
    QGroupBox, QMessageBox, QFormLayout, QRadioButton, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from reportlab.lib.pagesizes import A4
from utils.globals import (
    TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND,
    TITLE_FONT, SUBTITLE_FONT, BODY_FONT
)

class CrearCliente(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Caja contenedora
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
        
        title = QLabel("Agregar Nuevo Cliente")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            QLabel {{
            color: {TYRIAN_PURPLE}; 
            margin-bottom: 15px;
            background-color: transparent;  
            }}
        """)
        container_layout.addWidget(title)
        
        # Formulario de cliente
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Tipo de cliente (Persona física o jurídica)
        self.tipo_cliente_group = QWidget()
        self.tipo_cliente_group.setFixedHeight(40)
        tipo_layout = QHBoxLayout(self.tipo_cliente_group)
        tipo_layout.setContentsMargins(0, 0, 0, 0)
        self.radio_fisica = QRadioButton("Persona Física")
        self.radio_juridica = QRadioButton("Persona Jurídica")
        self.radio_fisica.setChecked(True)
        tipo_layout.addWidget(self.radio_fisica)
        tipo_layout.addWidget(self.radio_juridica)

        # Conectar los radio buttons al evento de cambio
        self.radio_fisica.toggled.connect(self.actualizar_etiqueta_fiscal)
        self.radio_juridica.toggled.connect(self.actualizar_etiqueta_fiscal)
        
        # Campos del formulario - ajustados a la estructura de la base de datos
        self.nombre_input = self.create_styled_input("Nombre o Razón Social")
        self.cifnif_input = self.create_styled_input("NIF")
        self.direccion_input = self.create_styled_input("Dirección")
        self.cod_postal_input = self.create_styled_input("Código Postal")
        self.telefono_input = self.create_styled_input("Teléfono")
        self.email_input = self.create_styled_input("Email")
        self.observaciones_input = QTextEdit()
        self.observaciones_input.setPlaceholderText("Observaciones adicionales...")
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
        self.observaciones_input.setMaximumHeight(100)

        # Crear la etiqueta fiscal con referencia para modificarla después
        self.cifnif_label = self.create_form_label("NIF:*")
        
        # Agregar campos al formulario
        form_layout.addRow(self.create_form_label("Tipo de cliente:"), self.tipo_cliente_group)
        form_layout.addRow(self.create_form_label("Nombre o Razón Social:*"), self.nombre_input)
        form_layout.addRow(self.cifnif_label, self.cifnif_input) 
        form_layout.addRow(self.create_form_label("Dirección:"), self.direccion_input)
        form_layout.addRow(self.create_form_label("Código Postal:"), self.cod_postal_input)
        form_layout.addRow(self.create_form_label("Teléfono:"), self.telefono_input)
        form_layout.addRow(self.create_form_label("Email:"), self.email_input)
        form_layout.addRow(self.create_form_label("Observaciones:"), self.observaciones_input)
        
        # Nota de campos obligatorios
        nota = QLabel("* Campos obligatorios")
        nota.setStyleSheet("color: gray; font-style: italic; margin-top: 5px;")
        
        container_layout.addLayout(form_layout)
        container_layout.addWidget(nota)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 20, 0, 0)
        
        self.clear_btn = QPushButton("Limpiar")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
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
        """)
        self.clear_btn.clicked.connect(self.clear_form)
        
        self.save_btn = QPushButton("Guardar Cliente")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
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
        """)
        self.save_btn.clicked.connect(self.save_client)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.save_btn)
        
        container_layout.addLayout(buttons_layout)
        
        layout.addWidget(container)
    
    def actualizar_etiqueta_fiscal(self):
        """Actualiza la etiqueta y placeholder según el tipo de cliente seleccionado"""
        if self.radio_fisica.isChecked():
            self.cifnif_label.setText("NIF:*")
            self.cifnif_input.setPlaceholderText("NIF")
        else:
            self.cifnif_label.setText("CIF:*")
            self.cifnif_input.setPlaceholderText("CIF")
    
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
        """Limpiar todos los campos del formulario"""
        self.nombre_input.clear()
        self.cifnif_input.clear()
        self.direccion_input.clear()
        self.cod_postal_input.clear()
        self.telefono_input.clear()
        self.email_input.clear()
        self.observaciones_input.clear()
        self.radio_fisica.setChecked(True)
    
    def save_client(self):
        """Guardar los datos del cliente en la base de datos"""
        # Recoger datos del formulario
        cliente = {
            'tipo_cliente': self.radio_fisica.isChecked(),  # True = física, False = jurídica
            'nombre': self.nombre_input.text().strip(),
            'cifnif': self.cifnif_input.text().strip(),
            'direccion': self.direccion_input.text().strip(),
            'cod_postal': self.cod_postal_input.text().strip(),
            'telefono': self.telefono_input.text().strip(),
            'email': self.email_input.text().strip(),
            'observaciones': self.observaciones_input.toPlainText().strip()
        }
        
        # Importar validadores
        from validators.Validator import (
            RequiredValidator, NIFValidator, CIFValidator, PhoneValidator, 
            PostalCodeValidator, validate_form_data
        )
        
        # Configurar validadores para cada campo
        validators = {
            'nombre': RequiredValidator(),
            # Seleccionar el validador según el tipo de cliente
            'cifnif': NIFValidator() if cliente['tipo_cliente'] else CIFValidator()
        }
        
        # Validar campos opcionales solo si no están vacíos
        if cliente['telefono']:
            validators['telefono'] = PhoneValidator()
        
        if cliente['cod_postal']:
            validators['cod_postal'] = PostalCodeValidator()
        
        # Ejecutar validación
        is_valid, errors = validate_form_data(cliente, validators)
        
        # Mostrar errores si hay alguno
        if not is_valid:
            error_message = "Por favor corrija los siguientes errores:\n"
            for field, message in errors.items():
                field_name = {
                    'nombre': "Nombre o Razón Social",
                    'cifnif': "CIF/NIF",
                    'telefono': "Teléfono",
                    'cod_postal': "Código Postal"
                }.get(field, field)
                error_message += f"• {field_name}: {message}\n"
            
            self.show_error_message(error_message)
            return
        
        try:
            # Importar función para agregar cliente
            from database.db import agregar_cliente
            
            # Intentar guardar el cliente
            cliente_id = agregar_cliente(
                cliente['cifnif'],
                cliente['nombre'],
                cliente['direccion'],
                cliente['cod_postal'],
                cliente['telefono'],
                cliente['observaciones'],
                cliente['tipo_cliente'],
                cliente['email']
            )
            
            if cliente_id:
                self.show_success_message(f"Cliente #{cliente_id} añadido correctamente.")
                self.clear_form()
            else:
                self.show_error_message("No se pudo guardar el cliente. Verifica los datos.")
        
        except Exception as e:
            self.show_error_message(f"Error al guardar: {str(e)}")
    
    def show_error_message(self, message):
        """Mostrar mensaje de error"""
        QMessageBox.critical(self, "Error", message)
    
    def show_success_message(self, message):
        """Mostrar mensaje de éxito"""
        QMessageBox.information(self, "Éxito", message)