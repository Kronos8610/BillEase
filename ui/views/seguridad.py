"""
Seguridad: cifrar la base, cambiar la contraseña y sacar los datos.

Tres cosas que tienen que estar a mano y explicadas sin eufemismos, porque
todas se pueden hacer mal una sola vez:

- **El código de recuperación se enseña una vez.** No se guarda en ninguna
  parte legible —en el fichero solo queda la clave envuelta con él—, así que
  si no se apunta no hay segunda oportunidad. La pantalla lo dice así.
- **Cifrar no es reversible sin la contraseña.** Antes de cifrar se guarda una
  copia de seguridad y se comprueba que la caja nueva se abre; solo entonces
  se da por buena.
- **Los datos son del usuario.** Por eso hay un botón para sacarlos sin
  cifrar: un programa que te encierra los datos dentro no protege, secuestra.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.validators import CONTRASENA
from data import backup, caja, connection
from data.repositories import autonomo as repo_autonomo


def etiqueta(texto, nombre="Etiqueta"):
    marca = QLabel(texto)
    marca.setObjectName(nombre)
    return marca


def campo_contrasena(marcador=""):
    campo = QLineEdit()
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    campo.setPlaceholderText(marcador)
    campo.setMinimumHeight(34)
    return campo


class DialogoCodigo(QDialog):
    """
    Enseña el código de recuperación. Una vez y nunca más.

    No deja cerrar hasta que el usuario dice que lo ha guardado. Es la única
    pantalla del programa que insiste, y lo hace porque perder la contraseña
    sin este código significa perder la facturación entera.
    """

    def __init__(self, codigo, parent=None):
        super().__init__(parent)
        self.codigo = codigo
        self.setWindowTitle("Código de recuperación")
        self.setModal(True)
        self.setMinimumWidth(560)

        columna = QVBoxLayout(self)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(12)

        columna.addWidget(etiqueta("Guarda este código", "Subtitulo"))
        aviso = etiqueta(
            "Es la única forma de recuperar tus datos si olvidas la contraseña. "
            "No se guarda en ninguna parte del programa ni se puede volver a "
            "enseñar: apúntalo en un papel y guárdalo lejos del ordenador.",
            "Apunte",
        )
        aviso.setWordWrap(True)
        columna.addWidget(aviso)

        self.texto = QLineEdit(codigo)
        self.texto.setReadOnly(True)
        self.texto.setMinimumHeight(42)
        self.texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto.setCursorPosition(0)
        columna.addWidget(self.texto)

        copiar = QPushButton("Copiar el código")
        copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        copiar.clicked.connect(self._copiar)

        guardar = QPushButton("Guardarlo en un fichero")
        guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        guardar.clicked.connect(self._guardar)

        fila = QHBoxLayout()
        fila.addWidget(copiar)
        fila.addWidget(guardar)
        fila.addStretch()
        columna.addLayout(fila)

        self.confirmado = QCheckBox("Lo he apuntado en un sitio seguro")
        self.confirmado.toggled.connect(lambda si: self.aceptar.setEnabled(si))
        columna.addWidget(self.confirmado)

        self.aceptar = QPushButton("Continuar")
        self.aceptar.setObjectName("Primario")
        self.aceptar.setEnabled(False)
        self.aceptar.clicked.connect(self.accept)

        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(self.aceptar)
        columna.addLayout(pie)

    def _copiar(self):
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.codigo)
        self.confirmado.setChecked(True)

    def _guardar(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar el código", "billease-codigo-de-recuperacion.txt",
            "Texto (*.txt)",
        )
        if not ruta:
            return
        try:
            Path(ruta).write_text(
                "Código de recuperación de BillEase\n"
                "=================================\n\n"
                f"{self.codigo}\n\n"
                "Con este código se abren tus datos aunque olvides la contraseña.\n"
                "Guárdalo donde no esté el ordenador. Sigue valiendo aunque\n"
                "cambies la contraseña más adelante.\n",
                encoding="utf-8",
            )
        except OSError as e:
            QMessageBox.critical(self, "No se pudo guardar", str(e))
            return
        self.confirmado.setChecked(True)

    def closeEvent(self, evento):
        """Cerrar con la X sin confirmar pregunta otra vez: es a propósito."""
        if self.confirmado.isChecked():
            evento.accept()
            return
        seguir = QMessageBox.question(
            self, "¿Seguro?",
            "Si cierras sin apuntar el código y algún día olvidas la contraseña, "
            "no habrá manera de recuperar tus facturas.\n\n¿Cerrar de todas formas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        evento.accept() if seguir == QMessageBox.StandardButton.Yes else evento.ignore()


class DialogoCambioContrasena(QDialog):
    """Cambia la contraseña: la de la caja y la que se guarda cifrada."""

    def __init__(self, ruta, parent=None):
        super().__init__(parent)
        self.ruta = Path(ruta)
        self.setWindowTitle("Cambiar la contraseña")
        self.setModal(True)
        self.setMinimumWidth(460)

        columna = QVBoxLayout(self)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(8)

        columna.addWidget(etiqueta("Cambiar la contraseña", "Subtitulo"))
        nota = etiqueta(
            "El cambio es instantáneo aunque tengas miles de facturas: los datos "
            "no se vuelven a cifrar, solo cambia la llave que los abre. Tu código "
            "de recuperación sigue siendo el mismo.",
            "Apunte",
        )
        nota.setWordWrap(True)
        columna.addWidget(nota)
        columna.addSpacing(6)

        columna.addWidget(etiqueta("Contraseña actual"))
        self.actual = campo_contrasena()
        columna.addWidget(self.actual)

        columna.addWidget(etiqueta("Contraseña nueva"))
        self.nueva = campo_contrasena("8 caracteres, con letra y número")
        columna.addWidget(self.nueva)

        columna.addWidget(etiqueta("Repítela"))
        self.repetida = campo_contrasena()
        self.repetida.returnPressed.connect(self.cambiar)
        columna.addWidget(self.repetida)

        self.error = etiqueta("", "Error")
        self.error.setWordWrap(True)
        columna.addWidget(self.error)

        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton("Cambiar")
        aceptar.setObjectName("Primario")
        aceptar.setDefault(True)
        aceptar.clicked.connect(self.cambiar)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        columna.addLayout(botones)

    def cambiar(self):
        self.error.setText("")       # un error de hace dos intentos despista
        actual, nueva = self.actual.text(), self.nueva.text()

        if nueva != self.repetida.text():
            self.error.setText("Las dos contraseñas nuevas no coinciden.")
            return
        fallo = CONTRASENA.evaluar(nueva)
        if fallo:
            self.error.setText(fallo)
            return
        if not repo_autonomo.verificar_contrasena(actual):
            self.error.setText("La contraseña actual no es correcta.")
            return

        if caja.es_caja(self.ruta):
            # Primero la caja: si esto falla, la contraseña guardada no se
            # toca y todo sigue como estaba. Se hace sobre la conexión abierta,
            # no sobre el fichero: una conexión viva guarda su propia cabecera
            # y al cerrarse devolvería la contraseña vieja.
            try:
                if not connection.cambiar_contrasena(nueva):
                    caja.cambiar_contrasena(self.ruta, actual, nueva)
            except caja.ErrorDeCifrado as e:
                self.error.setText(f"No se pudo cambiar en la caja: {e}")
                return

        repo_autonomo.cambiar_contrasena(nueva)
        QMessageBox.information(
            self, "Contraseña cambiada",
            "A partir de ahora entra con la contraseña nueva.\n\n"
            "Tu código de recuperación no cambia: sigue abriendo también las "
            "copias de seguridad antiguas.",
        )
        self.accept()


class DialogoCifrar(QDialog):
    """Pide la contraseña actual para cifrar una base que está en claro."""

    def __init__(self, ruta, parent=None):
        super().__init__(parent)
        self.ruta = Path(ruta)
        self.codigo = None
        self.setWindowTitle("Cifrar los datos")
        self.setModal(True)
        self.setMinimumWidth(500)

        columna = QVBoxLayout(self)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(8)

        columna.addWidget(etiqueta("Cifrar los datos", "Subtitulo"))
        explicacion = etiqueta(
            "A partir de ahora el fichero de datos no se podrá leer sin tu "
            "contraseña, ni aquí ni en ningún otro programa. Se guarda una copia "
            "de seguridad antes de empezar, y después se enseña un código de "
            "recuperación que hay que apuntar.",
            "Apunte",
        )
        explicacion.setWordWrap(True)
        columna.addWidget(explicacion)
        columna.addSpacing(6)

        columna.addWidget(etiqueta("Tu contraseña"))
        self.contrasena = campo_contrasena("La misma con la que entras")
        self.contrasena.returnPressed.connect(self.cifrar)
        columna.addWidget(self.contrasena)

        self.error = etiqueta("", "Error")
        self.error.setWordWrap(True)
        columna.addWidget(self.error)

        cancelar = QPushButton("Ahora no")
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton("Cifrar")
        aceptar.setObjectName("Primario")
        aceptar.setDefault(True)
        aceptar.clicked.connect(self.cifrar)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        columna.addLayout(botones)

    def cifrar(self):
        self.error.setText("")
        contrasena = self.contrasena.text()
        if not repo_autonomo.verificar_contrasena(contrasena):
            self.error.setText("Esa no es tu contraseña.")
            return

        try:
            # Una copia antes de tocar nada, y en claro: si algo saliera mal,
            # ahí están los datos.
            copia = backup.copiar(self.ruta)
            connection.cerrar()
            _, codigo = caja.cifrar(self.ruta, contrasena)

            # Y se comprueba que la caja nueva se abre ANTES de darla por buena.
            connection.abrir_caja(self.ruta, contrasena=contrasena)
        except Exception as e:  # noqa: BLE001
            self.error.setText(f"No se pudo cifrar: {e}")
            return

        self.codigo = codigo
        QMessageBox.information(
            self, "Datos cifrados",
            f"Listo. El fichero ya no se puede leer sin tu contraseña.\n\n"
            f"La copia de antes de cifrar, todavía en claro, está en:\n{copia}\n\n"
            f"Bórrala cuando compruebes que todo funciona.",
        )
        self.accept()


def exportar_sin_cifrar(ruta, parent=None):
    """
    Saca una copia legible de la base, previa contraseña.

    Está aquí a propósito: los datos son del usuario y tiene que poder
    llevárselos. Lo que no puede es hacerlo cualquiera que pase por delante.
    """
    from PyQt6.QtWidgets import QInputDialog

    ruta = Path(ruta)
    if not caja.es_caja(ruta):
        QMessageBox.information(
            parent, "No hace falta",
            "Tus datos todavía no están cifrados: el fichero se puede copiar "
            "tal cual.",
        )
        return None

    contrasena, aceptado = QInputDialog.getText(
        parent, "Confirma tu contraseña",
        "Vas a sacar una copia SIN CIFRAR de todos tus datos.\n"
        "Escribe tu contraseña para continuar:",
        QLineEdit.EchoMode.Password,
    )
    if not aceptado:
        return None

    destino, _ = QFileDialog.getSaveFileName(
        parent, "Guardar la copia sin cifrar", "billease-sin-cifrar.db",
        "Base de datos SQLite (*.db)",
    )
    if not destino:
        return None

    try:
        caja.descifrar(ruta, contrasena, destino)
    except caja.ClaveIncorrecta:
        QMessageBox.warning(parent, "Contraseña incorrecta",
                            "No se ha exportado nada.")
        return None
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(parent, "No se pudo exportar", str(e))
        return None

    QMessageBox.warning(
        parent, "Copia sin cifrar",
        f"La copia está en:\n{destino}\n\nCualquiera que la encuentre puede "
        f"leer tus clientes y tus facturas. Guárdala donde toque o bórrala "
        f"cuando termines.",
    )
    return destino
