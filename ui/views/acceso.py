"""
La pantalla de acceso: la contraseña que abre la caja.

Hasta ahora el programa pedía una contraseña al darse de alta y no la volvía a
pedir nunca: `verificar_acceso()` estaba escrita, probada… y no la llamaba
nadie. Cualquiera que se sentara delante del ordenador abría la facturación.

Ahora la contraseña hace dos cosas a la vez:

- **Acredita**, que es lo que se veía venir.
- **Descifra**, que es lo que de verdad protege: la clave de los datos está
  envuelta con ella (`core/cifrado.py`). Sin la contraseña no hay manera de
  leer el fichero, ni desde aquí ni desde ningún otro programa.

Si la base todavía está en claro —una instalación anterior que no se ha
cifrado— la pantalla lo dice tal cual, porque entonces la contraseña es un
cerrojo de cortesía y conviene no confundirse sobre lo que protege.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme
from data import caja, connection
from ui import iconos

# A partir del tercer intento se espera, y cada vez un poco más. Argon2id ya
# hace lento probar contraseñas; esto lo hace además incómodo.
INTENTOS_LIBRES = 3
ESPERA_BASE = 5          # segundos


class VentanaAcceso(QWidget):
    """
    Pide la contraseña y, si es la buena, abre la base.

    `al_entrar` se llama con la conexión ya puesta: quien la reciba abre la
    ventana principal.
    """

    def __init__(self, ruta, al_entrar, parent=None):
        super().__init__(parent)
        self.setObjectName("Ventana")
        self.ruta = ruta
        self.al_entrar = al_entrar
        self.cifrada = caja.es_caja(ruta)
        self.intentos = 0
        self._espera = QTimer(self)
        self._espera.setSingleShot(True)
        self._espera.timeout.connect(self._volver_a_permitir)

        self.setWindowTitle("BillEase")
        self.setMinimumSize(520, 460)
        self.resize(560, 500)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(40, 36, 40, 32)
        raiz.addStretch(1)

        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        tarjeta.setMaximumWidth(440)
        dentro = QVBoxLayout(tarjeta)
        dentro.setContentsMargins(32, 28, 32, 28)
        dentro.setSpacing(10)

        candado = QLabel()
        candado.setPixmap(iconos.pixmap("candado", 40, theme.color("acento")))
        candado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dentro.addWidget(candado)

        titulo = QLabel("BillEase")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dentro.addWidget(titulo)

        self.explicacion = QLabel(
            "Tus datos están cifrados. Escribe tu contraseña para abrirlos."
            if self.cifrada else
            "Escribe tu contraseña para entrar.\nTus datos todavía NO están "
            "cifrados: puedes cifrarlos desde Ajustes."
        )
        self.explicacion.setObjectName("Apunte")
        self.explicacion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.explicacion.setWordWrap(True)
        dentro.addWidget(self.explicacion)
        dentro.addSpacing(10)

        self.contrasena = QLineEdit()
        self.contrasena.setEchoMode(QLineEdit.EchoMode.Password)
        self.contrasena.setPlaceholderText("Contraseña")
        self.contrasena.setMinimumHeight(36)
        self.contrasena.returnPressed.connect(self.entrar)
        self.contrasena.textChanged.connect(lambda: self.error.setText(""))
        dentro.addWidget(self.contrasena)

        self.error = QLabel("")
        self.error.setObjectName("Error")
        self.error.setWordWrap(True)
        self.error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dentro.addWidget(self.error)

        self.boton = QPushButton("Entrar")
        self.boton.setObjectName("Primario")
        self.boton.setMinimumHeight(38)
        self.boton.setDefault(True)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self.entrar)
        dentro.addWidget(self.boton)

        if self.cifrada:
            olvidada = QPushButton("He olvidado la contraseña")
            olvidada.setObjectName("Enlace")
            olvidada.setCursor(Qt.CursorShape.PointingHandCursor)
            olvidada.clicked.connect(self.recuperar)
            dentro.addWidget(olvidada, alignment=Qt.AlignmentFlag.AlignCenter)

        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(tarjeta)
        fila.addStretch()
        raiz.addLayout(fila)
        raiz.addStretch(1)

        self.contrasena.setFocus()

    # ───────────────────────────── entrar ─────────────────────────────

    def entrar(self):
        contrasena = self.contrasena.text()
        if not contrasena:
            self.error.setText("Escribe tu contraseña.")
            return

        self.boton.setEnabled(False)
        self.error.setText("Comprobando…")
        # Que la etiqueta se pinte antes de los 200 ms de Argon2.
        QTimer.singleShot(0, lambda: self._comprobar(contrasena))

    def _comprobar(self, contrasena):
        try:
            correcta = self._abrir(contrasena)
        except caja.CajaCorrupta as e:
            self.error.setText(
                f"El fichero de datos está dañado. {e}\n"
                "Prueba a restaurar una copia de seguridad."
            )
            self.boton.setEnabled(True)
            return

        if correcta:
            self.error.setText("")
            self.al_entrar()
            self.close()
            return

        self.intentos += 1
        self.contrasena.selectAll()
        if self.intentos >= INTENTOS_LIBRES:
            segundos = ESPERA_BASE * (self.intentos - INTENTOS_LIBRES + 1)
            self.error.setText(
                f"Contraseña incorrecta. Espera {segundos} segundos antes de "
                f"volver a probar."
            )
            # El cerrojo no depende de quién haya llamado: se echa aquí.
            self.boton.setEnabled(False)
            self._espera.start(segundos * 1000)
        else:
            self.error.setText("Contraseña incorrecta.")
            self.boton.setEnabled(True)
            self.contrasena.setFocus()

    def _abrir(self, contrasena):
        """True si la contraseña vale. Deja la conexión abierta si es que sí."""
        if self.cifrada:
            try:
                connection.abrir_caja(self.ruta, contrasena=contrasena)
                return True
            except caja.ClaveIncorrecta:
                return False

        from data.repositories import autonomo as repo_autonomo

        connection.cerrar()
        if not repo_autonomo.hay_autonomo():
            return True            # base sin dar de alta: no hay nada que comprobar
        return repo_autonomo.verificar_contrasena(contrasena)

    def _volver_a_permitir(self):
        self.boton.setEnabled(True)
        self.error.setText("Puedes volver a probar.")
        self.contrasena.setFocus()

    # ───────────────────────────── recuperar ─────────────────────────────

    def recuperar(self):
        dialogo = DialogoRecuperacion(self.ruta, self)
        if dialogo.exec():
            self.al_entrar()
            self.close()


class DialogoRecuperacion(QDialog):
    """
    El código de recuperación: la única puerta cuando se olvida la contraseña.

    Abre la caja y obliga a poner una contraseña nueva en el mismo paso,
    porque entrar sin dejar una contraseña usable solo aplaza el problema.
    """

    def __init__(self, ruta, parent=None):
        super().__init__(parent)
        self.ruta = ruta
        self.setWindowTitle("Recuperar el acceso")
        self.setModal(True)
        self.setMinimumWidth(520)

        columna = QVBoxLayout(self)
        columna.setContentsMargins(28, 24, 28, 20)
        columna.setSpacing(10)

        titulo = QLabel("Recuperar el acceso")
        titulo.setObjectName("Subtitulo")
        columna.addWidget(titulo)

        explicacion = QLabel(
            "Escribe el código de recuperación que te enseñó el programa cuando "
            "cifraste tus datos. Da igual si lo copias con guiones o sin ellos, "
            "en mayúsculas o en minúsculas."
        )
        explicacion.setObjectName("Apunte")
        explicacion.setWordWrap(True)
        columna.addWidget(explicacion)

        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.codigo.setMinimumHeight(34)
        columna.addWidget(self.codigo)

        columna.addWidget(self._etiqueta("Contraseña nueva"))
        self.nueva = QLineEdit()
        self.nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.nueva.setMinimumHeight(34)
        columna.addWidget(self.nueva)

        columna.addWidget(self._etiqueta("Repítela"))
        self.repetida = QLineEdit()
        self.repetida.setEchoMode(QLineEdit.EchoMode.Password)
        self.repetida.setMinimumHeight(34)
        self.repetida.returnPressed.connect(self.recuperar)
        columna.addWidget(self.repetida)

        self.error = QLabel("")
        self.error.setObjectName("Error")
        self.error.setWordWrap(True)
        columna.addWidget(self.error)

        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        aceptar = QPushButton("Recuperar y entrar")
        aceptar.setObjectName("Primario")
        aceptar.setDefault(True)
        aceptar.clicked.connect(self.recuperar)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(cancelar)
        botones.addWidget(aceptar)
        columna.addLayout(botones)

    def _etiqueta(self, texto):
        marca = QLabel(texto)
        marca.setObjectName("Etiqueta")
        return marca

    def recuperar(self):
        from core.validators import CONTRASENA

        self.error.setText("")       # lo de antes ya no vale
        codigo = self.codigo.text().strip()
        nueva = self.nueva.text()

        if not codigo:
            self.error.setText("Escribe el código de recuperación.")
            return
        if nueva != self.repetida.text():
            self.error.setText("Las dos contraseñas no coinciden.")
            return
        fallo = CONTRASENA.evaluar(nueva)
        if fallo:
            self.error.setText(fallo)
            return

        try:
            # Nada abierto mientras se toca el fichero: una conexión viva
            # volvería a escribir la cabecera de antes al cerrarse.
            connection.cerrar()
            caja.cambiar_contrasena(self.ruta, None, nueva, codigo=codigo)
            connection.abrir_caja(self.ruta, contrasena=nueva)
        except caja.ClaveIncorrecta:
            self.error.setText("Ese código no abre esta base. Míralo otra vez.")
            return
        except caja.ErrorDeCifrado as e:
            self.error.setText(str(e))
            return

        from data.repositories import autonomo as repo_autonomo

        repo_autonomo.cambiar_contrasena(nueva)
        self.accept()
