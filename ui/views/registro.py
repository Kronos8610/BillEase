"""
La configuración inicial: los datos del autónomo que emite.

Sustituye a `login_ui.py`. Es la primera pantalla que se ve, y la única vez
que se ve, así que dice claramente para qué sirve lo que se pide: estos datos
son los que saldrán impresos en cada factura.

Cambia el aspecto —lo viste la hoja de estilos, como el resto— y no cambia
nada de lo que ya funcionaba: las mismas reglas de validación, el mismo alta,
la misma contraseña cifrada con Argon2.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import Autonomo
from core.validators import (
    CODIGO_POSTAL,
    CONTRASENA,
    EMAIL,
    NIF_O_NIE,
    OBLIGATORIO,
    TELEFONO,
    validar_formulario,
)
from data.repositories import autonomo as repo_autonomo

# (clave, rótulo, marcador, columna)
CAMPOS = (
    ("nombre", "Nombre *", "Carlos", 0),
    ("apellido", "Apellidos *", "García López", 0),
    ("nif", "NIF o NIE *", "12345678Z", 0),
    ("direccion", "Dirección *", "Calle Mayor 12, 2ºA", 0),
    ("email", "Correo *", "tu@correo.es", 1),
    ("contrasena", "Contraseña *", "8 caracteres, con letra y número", 1),
    ("telefono", "Teléfono *", "612345678", 1),
    ("codigo_postal", "Código postal *", "28001", 1),
)

REGLAS = {
    "nombre": OBLIGATORIO,
    "apellido": OBLIGATORIO,
    "direccion": OBLIGATORIO,
    # Un autónomo residente extranjero también factura (defecto 12).
    "nif": NIF_O_NIE,
    "email": EMAIL,
    "contrasena": CONTRASENA,
    "telefono": TELEFONO,
    "codigo_postal": CODIGO_POSTAL,
}


class VentanaRegistro(QWidget):
    """El alta del autónomo. `configuracion_inicial` cambia los textos."""

    def __init__(self, parent=None, configuracion_inicial=False):
        super().__init__(parent)
        self.setObjectName("Ventana")
        self.configuracion_inicial = configuracion_inicial
        self.campos = {}
        self.errores = {}
        self.ventana_principal = None

        self.setWindowTitle("BillEase")
        self.setMinimumSize(720, 620)
        self.resize(820, 680)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(48, 40, 48, 36)
        raiz.setSpacing(6)
        raiz.addStretch(1)

        titulo = QLabel(
            "Configura BillEase" if configuracion_inicial else "Alta de usuario"
        )
        titulo.setObjectName("Titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(titulo)

        explicacion = QLabel(
            "Estos son tus datos de emisor: aparecerán impresos en cada factura "
            "y en cada presupuesto. Podrás cambiarlos más adelante."
        )
        explicacion.setObjectName("Apunte")
        explicacion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        explicacion.setWordWrap(True)
        raiz.addWidget(explicacion)
        raiz.addSpacing(22)

        raiz.addLayout(self._formulario())
        raiz.addSpacing(10)

        self.boton = QPushButton(
            "Empezar a usar BillEase" if configuracion_inicial else "Guardar"
        )
        self.boton.setObjectName("Primario")
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.setMinimumHeight(38)
        self.boton.setDefault(True)
        self.boton.clicked.connect(self.registrar)

        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(self.boton)
        fila.addStretch()
        raiz.addLayout(fila)

        pie = QLabel("* Todos los campos son obligatorios en una factura válida.")
        pie.setObjectName("Apunte")
        pie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(pie)
        raiz.addStretch(1)

    # ───────────────────────────── montaje ─────────────────────────────

    def _formulario(self):
        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(28)
        rejilla.setVerticalSpacing(2)

        siguiente = {0: 0, 1: 0}
        for clave, rotulo, marcador, columna in CAMPOS:
            fila = siguiente[columna]

            rotulo_campo = QLabel(rotulo)
            rotulo_campo.setObjectName("Etiqueta")

            campo = QLineEdit()
            campo.setPlaceholderText(marcador)
            campo.setMinimumHeight(32)
            if clave == "contrasena":
                campo.setEchoMode(QLineEdit.EchoMode.Password)

            error = QLabel("")
            error.setObjectName("Error")
            error.setWordWrap(True)

            rejilla.addWidget(rotulo_campo, fila, columna)
            rejilla.addWidget(campo, fila + 1, columna)
            rejilla.addWidget(error, fila + 2, columna)

            self.campos[clave] = campo
            self.errores[clave] = error
            siguiente[columna] = fila + 3

        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)
        return rejilla

    # ───────────────────────────── alta ─────────────────────────────

    @property
    def datos(self):
        valores = {clave: campo.text().strip() for clave, campo in self.campos.items()}
        # La contraseña no se recorta: un espacio al final también cuenta.
        valores["contrasena"] = self.campos["contrasena"].text()
        return valores

    def registrar(self):
        datos = self.datos
        correcto, errores = validar_formulario(datos, REGLAS)
        for clave, etiqueta in self.errores.items():
            etiqueta.setText(errores.get(clave, ""))
        if not correcto:
            return

        if self.configuracion_inicial and not self._crear_base():
            return

        creado = repo_autonomo.registrar(
            Autonomo(
                nif=datos["nif"],
                nombre=datos["nombre"],
                apellido=datos["apellido"],
                direccion=datos["direccion"],
                codigo_postal=datos["codigo_postal"],
                telefono=datos["telefono"],
                email=datos["email"],
            ),
            datos["contrasena"],
        )

        if not creado:
            QMessageBox.critical(
                self, "No se pudo completar el alta",
                "Los datos no se han podido guardar. Comprueba que el NIF no esté "
                "ya dado de alta e inténtalo otra vez.",
            )
            return

        if self.configuracion_inicial:
            self.abrir_aplicacion()
        else:
            QMessageBox.information(self, "Listo", "Los datos se han guardado.")
            self.close()

    def _crear_base(self):
        """Crea la base la primera vez. Devuelve si ha ido bien."""
        from PyQt6.QtWidgets import QApplication

        aviso = QProgressDialog("Preparando BillEase…", None, 0, 2, self)
        aviso.setWindowTitle("Configuración inicial")
        aviso.setWindowModality(Qt.WindowModality.WindowModal)
        aviso.setValue(0)
        aviso.show()
        QApplication.processEvents()
        try:
            from data.schema import crear_esquema_y_migrar

            crear_esquema_y_migrar()
            aviso.setValue(2)
            return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(
                self, "Error de configuración",
                f"No se ha podido crear la base de datos.\n\n{e}",
            )
            return False
        finally:
            aviso.close()

    def abrir_aplicacion(self):
        from ui.shell import VentanaPrincipal

        self.ventana_principal = VentanaPrincipal()
        self.ventana_principal.show()
        self.close()
