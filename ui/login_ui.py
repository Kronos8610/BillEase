from PyQt6 import QtCore, QtGui, QtWidgets
import sys
from ui.aplication import MainWindow
from validators.Validator import (
    RequiredValidator, EmailValidator, PhoneValidator, 
    NIFValidator, PostalCodeValidator, PasswordValidator, 
    validate_form_data
)
from database.db import crear_base_de_datos, register_autonomo

class RegisterWindow(QtWidgets.QWidget):
    def __init__(self, parent=None, initial_setup=False):
        super().__init__(parent)
        # Modo de configuración inicial
        self.initial_setup = initial_setup
        # Diccionario para mantener las etiquetas de error
        self.error_labels = {}
        self.setupUi()
    
    def setupUi(self):
        self.setObjectName("RegisterWindow")
        self.resize(600, 650) 
        self.setMinimumSize(500, 600) 
        self.setStyleSheet("QLabel.error {\n"
                         "    color: red;\n"
                         "    font-size: 10px;\n"
                         "    min-height: 15px;\n"
                         "}")
        
        # Contenedor principal con margen dinámico
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Contenedor centrado para todo el contenido
        self.centered_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.centered_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Agrupar con spacers para centrado vertical
        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.centered_widget)
        self.main_layout.addStretch(1)
        
        # Titulo - modificado según el contexto
        if self.initial_setup:
            title_text = "Configuración inicial de BillEase"
            button_text = "Comenzar a usar BillEase"
        else:
            title_text = "Registro de Usuario"
            button_text = "Guardar e Iniciar Sesión"
            
        self.title_label = QtWidgets.QLabel(title_text)
        font = QtGui.QFont()
        font.setFamily("Sitka Text Semibold")
        font.setPointSize(19)
        self.title_label.setFont(font)
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title_label)
        
        # Explicación adicional para configuración inicial
        if self.initial_setup:
            self.subtitle_label = QtWidgets.QLabel(
                "Introduce tus datos para comenzar a usar la aplicación. Esta información aparecerá en tus facturas."
            )
            self.subtitle_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.subtitle_label.setWordWrap(True)
            self.layout.addWidget(self.subtitle_label)
        
        spacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.layout.addItem(spacer)
        
        # Creamos directamente el form_widget sin usar ScrollArea
        self.form_widget = QtWidgets.QWidget()
        self.form_widget.setMaximumWidth(600)  # Ancho suficiente para dos columnas
        
        # Usar grid layout para columnas
        self.form_layout = QtWidgets.QGridLayout(self.form_widget)
        self.form_layout.setVerticalSpacing(10)  # Aumentar espaciado vertical
        
        self.email_input = QtWidgets.QLineEdit()
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.name_input = QtWidgets.QLineEdit()
        self.surname_input = QtWidgets.QLineEdit()
        self.address_input = QtWidgets.QLineEdit()
        self.nif_input = QtWidgets.QLineEdit()
        self.phone_input = QtWidgets.QLineEdit()
        self.postal_code_input = QtWidgets.QLineEdit()
        
        # Primera columna - 4 campos con etiquetas y espacios para errores
        self.add_form_row("Correo:", self.email_input, "email", 0, 0)
        self.add_form_row("Contraseña:", self.password_input, "password", 2, 0)
        self.add_form_row("Nombre:", self.name_input, "name", 4, 0)
        self.add_form_row("Apellido:", self.surname_input, "surname", 6, 0)
        
        # Segunda columna - 4 campos con etiquetas y espacios para errores
        self.add_form_row("Dirección:", self.address_input, "address", 0, 2)
        self.add_form_row("NIF:", self.nif_input, "nif", 2, 2)
        self.add_form_row("Teléfono:", self.phone_input, "phone", 4, 2)
        self.add_form_row("Código Postal:", self.postal_code_input, "postal_code", 6, 2)
        
        # Centrar el formulario
        self.form_container = QtWidgets.QHBoxLayout()
        self.form_container.addStretch()
        self.form_container.addWidget(self.form_widget)  # Añadimos directamente el form_widget
        self.form_container.addStretch()
        
        self.layout.addLayout(self.form_container)
        
        # Botones - ajustados según el contexto
        self.button_layout = QtWidgets.QHBoxLayout()
        self.register_button = QtWidgets.QPushButton(button_text)
        
        # Solo añadimos el botón de volver si no estamos en configuración inicial
        if not self.initial_setup:
            self.back_button = QtWidgets.QPushButton("Volver")
            self.button_layout.addWidget(self.back_button)
            self.back_button.clicked.connect(self.close)
        
        # Estilizar el botón principal
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: #6A0572;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #84084A;
            }
        """)
        
        self.button_layout.addWidget(self.register_button)
        self.layout.addLayout(self.button_layout)
        
        self.register_button.clicked.connect(self.validate_and_register)
    
    def add_form_row(self, label_text, input_widget, field_name, row, col):
        # Añadir espaciador antes del label (margen superior)
        top_spacer = QtWidgets.QSpacerItem(20, 10, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.form_layout.addItem(top_spacer, row, col)
        row += 1
        
        # Añadir etiqueta en la columna especificada
        label = QtWidgets.QLabel(label_text)
        self.form_layout.addWidget(label, row, col)
        
        # Añadir widget de entrada en columna + 1
        self.form_layout.addWidget(input_widget, row, col + 1)
        row += 1
        
        # Crear etiqueta de error debajo del input
        error_label = QtWidgets.QLabel("")
        error_label.setProperty("class", "error")
        error_label.setVisible(False)
        
        # Añadir etiqueta de error en la siguiente fila
        self.form_layout.addWidget(error_label, row, col + 1)
        
        # Guardar referencia a la etiqueta de error
        self.error_labels[field_name] = error_label
        
    def validate_and_register(self):
        """Valida el formulario antes de registrar"""
        # Recoger todos los datos del formulario
        form_data = {
            "email": self.email_input.text(),
            "password": self.password_input.text(),
            "name": self.name_input.text(),
            "surname": self.surname_input.text(),
            "address": self.address_input.text(),
            "nif": self.nif_input.text(),
            "phone": self.phone_input.text(),
            "postal_code": self.postal_code_input.text()
        }
        
        # Definir validadores para cada campo
        validators = {
            "email": EmailValidator(),
            "password": PasswordValidator(),
            "name": RequiredValidator(),
            "surname": RequiredValidator(),
            "address": RequiredValidator(),
            "nif": NIFValidator(),
            "phone": PhoneValidator(),
            "postal_code": PostalCodeValidator()
        }
        
        # Realizar validación
        is_valid, errors = validate_form_data(form_data, validators)
        
        # Limpiar todas las etiquetas de error primero
        for error_label in self.error_labels.values():
            error_label.setText("")
            error_label.setVisible(False)
        
        # Si hay errores, mostrarlos
        if not is_valid:
            for field, error_msg in errors.items():
                if field in self.error_labels:
                    self.error_labels[field].setText(error_msg)
                    self.error_labels[field].setVisible(True)
            return
        
        # Si todo es válido, proceder con el registro
        self.register_and_start()
        
    def register_and_start(self):
        # Recoge los datos del formulario de registro
        email = self.email_input.text()
        contrasena = self.password_input.text()
        nombre = self.name_input.text()
        apellido = self.surname_input.text()
        direccion = self.address_input.text()
        nif = self.nif_input.text()
        telefono = self.phone_input.text()
        cod_postal = self.postal_code_input.text()
        
        # Si estamos en configuración inicial, crear la base de datos primero
        if self.initial_setup:
            try:
                # Mostrar diálogo de progreso
                progress_dialog = QtWidgets.QProgressDialog("Configurando BillEase...", None, 0, 2, self)
                progress_dialog.setWindowTitle("Configuración inicial")
                progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                progress_dialog.setValue(0)
                progress_dialog.show()
                QtWidgets.QApplication.processEvents()
                
                # Paso 1: Crear base de datos
                print("Creando base de datos...")
                crear_base_de_datos()
                progress_dialog.setValue(1)
                QtWidgets.QApplication.processEvents()
                
                # Paso 2: Registrar usuario
                print("Registrando usuario...")
                success = register_autonomo(
                    nif, nombre, apellido, direccion, 
                    cod_postal, telefono, email, contrasena
                )
                progress_dialog.setValue(2)
                
                # Cerrar diálogo de progreso
                progress_dialog.close()
                
                if success:
                    # Mostrar mensaje de éxito
                    QtWidgets.QMessageBox.information(
                        self, 
                        "Configuración completada", 
                        "¡Bienvenido a BillEase! La configuración inicial se ha completado correctamente."
                    )
                    # Iniciar aplicación principal
                    self.open_main_window()
                else:
                    # Error al registrar usuario
                    QtWidgets.QMessageBox.critical(
                        self, 
                        "Error de configuración", 
                        "No se pudo completar la configuración. Por favor, inténtalo de nuevo."
                    )
            except Exception as e:
                # Capturar excepciones durante la configuración
                QtWidgets.QMessageBox.critical(
                    self, 
                    "Error de configuración", 
                    f"Error durante la configuración inicial: {str(e)}"
                )
        else:
            # Modo normal de registro (no estamos en configuración inicial)
            success = register_autonomo(
                nif, nombre, apellido, direccion, 
                cod_postal, telefono, email, contrasena
            )
            
            if success:
                # Mostrar mensaje de éxito
                QtWidgets.QMessageBox.information(
                    self, 
                    "Registro exitoso", 
                    "Te has registrado correctamente. Ahora puedes iniciar sesión."
                )
                self.close()
            else:
                # Mostrar mensaje de error
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Error de registro", 
                    "No se pudo completar el registro. Por favor, inténtalo de nuevo."
                )
        
    def open_main_window(self):
        """Abre la ventana principal de la aplicación"""
        self.main_window = MainWindow()
        self.main_window.show()
        self.close()
        
    # Evento para mantener la ventana responsive
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Ajustar márgenes según el tamaño de la ventana
        margin = min(int(self.width() * 0.1), 50)
        self.main_layout.setContentsMargins(margin, margin, margin, margin)


# Código para iniciar la aplicación directamente (solo para pruebas)
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    register_window = RegisterWindow(initial_setup=True)
    register_window.show()
    sys.exit(app.exec())