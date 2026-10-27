"""
El alta de un cliente y su ficha.

Antes era una pantalla entera del menú (`crearCliente.py`) que se creaba al
arrancar aunque nadie la abriera, con nueve `setStyleSheet` repartidos por el
formulario. Ahora es un diálogo que se abre desde el listado de clientes, con
el mismo aspecto que el editor de documentos porque los dos visten la misma
hoja de estilos.

Lo que no ha cambiado es lo importante: la validación. Un NIF, un NIE o un CIF
se comprueban con su dígito de control antes de guardar (`core/validators/`).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import theme
from core.models import Cliente
from core.validators import (
    CIF,
    CODIGO_POSTAL_OPCIONAL,
    EMAIL_OPCIONAL,
    NIF_O_NIE,
    OBLIGATORIO,
    TELEFONO_OPCIONAL,
    validar_formulario,
)
from data.repositories import clientes as repo_clientes
from ui.widgets.ventana import agrandable, centrado

NOMBRES = {
    "nombre": "Nombre o razón social",
    "cifnif": "NIF/CIF",
    "telefono": "Teléfono",
    "cod_postal": "Código postal",
    "email": "Correo",
}


def campo(marcador=""):
    control = QLineEdit()
    control.setPlaceholderText(marcador)
    control.setMinimumHeight(32)
    return control


def etiqueta(texto, nombre="Etiqueta"):
    marca = QLabel(texto)
    marca.setObjectName(nombre)
    return marca


class EditorCliente(QDialog):
    """Da de alta un cliente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo cliente")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.cliente_id = None
        agrandable(self, 760, 720)

        # El formulario se desplaza y los botones se quedan abajo: al
        # agrandar la ventana «Guardar cliente» no se va de viaje.
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        interior, contenido = centrado(theme.ancho_formulario())
        raiz.addWidget(desplazable)
        desplazable.setWidget(interior)

        columna = QVBoxLayout(contenido)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(14)

        columna.addWidget(etiqueta("Nuevo cliente", "Subtitulo"))
        columna.addWidget(etiqueta(
            "Sus datos fiscales son los que saldrán impresos en cada documento.",
            "Apunte",
        ))

        self.radio_fisica = QRadioButton("Persona física")
        self.radio_juridica = QRadioButton("Persona jurídica")
        self.radio_fisica.setChecked(True)
        self.radio_fisica.toggled.connect(self._cambiar_tipo)

        tipo = QWidget()
        # Alto fijo: si no, al agrandar la ventana esta fila se estira y abre
        # un hueco que las demás no tienen.
        tipo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        fila_tipo = QHBoxLayout(tipo)
        fila_tipo.setContentsMargins(0, 0, 0, 0)
        fila_tipo.addWidget(self.radio_fisica)
        fila_tipo.addWidget(self.radio_juridica)
        fila_tipo.addStretch()

        self.nombre = campo("Nombre y apellidos, o razón social")
        self.documento = campo("NIF")
        self.direccion = campo("Calle, número y piso")
        self.codigo_postal = campo("28001")
        self.telefono = campo("612345678")
        self.email = campo("cliente@correo.es")
        self.observaciones = QTextEdit()
        self.observaciones.setPlaceholderText("Forma de pago habitual, avisos…")
        self.observaciones.setMaximumHeight(80)

        self.etiqueta_documento = etiqueta("NIF *")

        formulario = QFormLayout()
        formulario.setSpacing(10)
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        formulario.addRow(etiqueta("Tipo"), tipo)
        formulario.addRow(etiqueta("Nombre *"), self.nombre)
        formulario.addRow(self.etiqueta_documento, self.documento)
        formulario.addRow(etiqueta("Dirección"), self.direccion)
        formulario.addRow(etiqueta("Código postal"), self.codigo_postal)
        formulario.addRow(etiqueta("Teléfono"), self.telefono)
        formulario.addRow(etiqueta("Correo"), self.email)
        formulario.addRow(etiqueta("Observaciones"), self.observaciones)
        columna.addLayout(formulario)

        self.error = etiqueta("", "Error")
        self.error.setWordWrap(True)
        columna.addWidget(self.error)

        cancelar = QPushButton("Cancelar")
        cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar cliente")
        guardar.setObjectName("Primario")
        guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        guardar.setDefault(True)
        guardar.clicked.connect(self.guardar)

        columna.addStretch()

        pie = QWidget()
        botones = QHBoxLayout(pie)
        botones.setContentsMargins(28, 14, 28, 16)
        botones.addStretch()
        botones.addWidget(cancelar)
        botones.addWidget(guardar)
        raiz.addWidget(pie)

    def _cambiar_tipo(self):
        fisica = self.radio_fisica.isChecked()
        self.etiqueta_documento.setText("NIF *" if fisica else "CIF *")
        self.documento.setPlaceholderText("NIF" if fisica else "CIF")

    @property
    def datos(self):
        return {
            "nombre": self.nombre.text().strip(),
            "cifnif": self.documento.text().strip(),
            "direccion": self.direccion.text().strip(),
            "cod_postal": self.codigo_postal.text().strip(),
            "telefono": self.telefono.text().strip(),
            "email": self.email.text().strip(),
            "observaciones": self.observaciones.toPlainText().strip(),
        }

    def guardar(self):
        es_fisica = self.radio_fisica.isChecked()
        datos = self.datos

        # Una persona física puede tener NIF o NIE: un residente extranjero
        # también es cliente (defecto 12).
        correcto, errores = validar_formulario(datos, {
            "nombre": OBLIGATORIO,
            "cifnif": NIF_O_NIE if es_fisica else CIF,
            "telefono": TELEFONO_OPCIONAL,
            "cod_postal": CODIGO_POSTAL_OPCIONAL,
            "email": EMAIL_OPCIONAL,
        })

        if not correcto:
            self.error.setText("\n".join(
                f"· {NOMBRES.get(nombre, nombre)}: {fallo}"
                for nombre, fallo in errores.items()
            ))
            return

        self.cliente_id = repo_clientes.crear(Cliente(
            nombre=datos["nombre"],
            nif=datos["cifnif"],
            es_persona_fisica=es_fisica,
            direccion=datos["direccion"],
            codigo_postal=datos["cod_postal"],
            telefono=datos["telefono"],
            email=datos["email"],
            observaciones=datos["observaciones"],
        ))

        if not self.cliente_id:
            self.error.setText(
                f"· Ya hay un cliente con el documento {datos['cifnif'].upper()}. "
                "Búscalo en la lista en lugar de crearlo otra vez."
            )
            return
        self.accept()


class FichaCliente(QDialog):
    """Los datos de un cliente, de un vistazo. Solo lectura."""

    def __init__(self, cliente, parent=None):
        super().__init__(parent)
        self.setWindowTitle(cliente.nombre)
        self.setModal(True)
        self.setMinimumWidth(460)

        columna = QVBoxLayout(self)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(10)

        titulo = etiqueta(cliente.nombre, "Subtitulo")
        titulo.setWordWrap(True)
        columna.addWidget(titulo)
        columna.addWidget(etiqueta(f"{cliente.etiqueta_fiscal} {cliente.nif}", "Apunte"))

        datos = (
            ("Dirección", cliente.direccion),
            ("Código postal", cliente.codigo_postal),
            ("Teléfono", cliente.telefono),
            ("Correo", cliente.email),
            ("Observaciones", cliente.observaciones),
            ("Documentos emitidos", str(repo_clientes.cuantas_facturas(cliente.id))),
        )

        formulario = QFormLayout()
        formulario.setSpacing(8)
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for nombre, valor in datos:
            texto = QLabel(valor or "—")
            texto.setWordWrap(True)
            texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            formulario.addRow(etiqueta(nombre), texto)
        columna.addLayout(formulario)

        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("Primario")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(cerrar)
        columna.addLayout(botones)
