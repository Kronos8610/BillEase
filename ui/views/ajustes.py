"""
Ajustes: seguridad, logotipo, copias de seguridad y exportación.

Las cosas que un programa que se instala tiene que ofrecer y que hasta ahora
no estaban en ninguna parte: cifrar los datos, poner la marca propia en el
papel, poder recuperarlos si algo va mal, y poder sacarlos para la gestoría
sin depender del programa.

También dice **dónde vive la base de datos**. Parece un detalle y no lo es:
la versión anterior la creaba en el directorio desde el que se arrancara, así
que los datos «desaparecían» al abrir el programa desde otro sitio.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import theme
from config import ruta_base_datos
from core.models import FACTURA, PRESUPUESTO, Autonomo
from core.validators import (
    CODIGO_POSTAL,
    EMAIL,
    IBAN_OPCIONAL,
    NIF_O_NIE,
    OBLIGATORIO,
    TELEFONO,
    formatear_iban,
    validar_formulario,
)
from data import backup, caja
from data.repositories import autonomo as repo_autonomo
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from documents.export_csv import exportar_todo
from ui import iconos
from ui.views.listado import boton

IMAGENES = "Imágenes (*.png *.jpg *.jpeg)"
ALTO_VISTA = 64


def etiqueta(texto, nombre="Etiqueta"):
    """Un rótulo. El color y el tamaño los pone la hoja de estilos."""
    marca = QLabel(texto)
    marca.setObjectName(nombre)
    return marca


def kilobytes(ruta):
    try:
        return f"{Path(ruta).stat().st_size / 1024:,.0f} KB".replace(",", ".")
    except OSError:
        return ""


class Ajustes(QWidget):
    """Las tres tarjetas de la pantalla de ajustes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.categoria = "Ajustes"
        self._iconos_de_accion = {}

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        # Cuatro tarjetas no caben en una pantalla pequeña, así que esto se
        # desplaza. Sin ello, la última quedaba cortada por abajo.
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        raiz.addWidget(desplazable)

        interior = QWidget()
        centrado = QHBoxLayout(interior)
        centrado.setContentsMargins(0, 0, 0, 0)
        contenido = QWidget()
        contenido.setMaximumWidth(theme.ancho_maximo())
        centrado.addStretch(1)
        centrado.addWidget(contenido, 100)
        centrado.addStretch(1)
        desplazable.setWidget(interior)

        self.columna = QVBoxLayout(contenido)
        self.columna.setContentsMargins(32, 28, 32, 28)
        self.columna.setSpacing(16)

        titulo = QLabel("Ajustes")
        titulo.setObjectName("Titulo")
        self.columna.addWidget(titulo)

        self._montar_mis_datos()
        self._montar_seguridad()
        self._montar_logotipo()
        self._montar_carpetas()
        self._montar_copias()
        self._montar_exportacion()
        self.columna.addStretch()

        self.cargar()

    # ───────────────────────────── montaje ─────────────────────────────

    def _tarjeta(self, titulo, explicacion):
        caja = QFrame()
        caja.setObjectName("Tarjeta")
        dentro = QVBoxLayout(caja)
        dentro.setContentsMargins(20, 16, 20, 18)
        dentro.setSpacing(10)

        rotulo = QLabel(titulo)
        rotulo.setObjectName("Subtitulo")
        texto = QLabel(explicacion)
        texto.setObjectName("Apunte")
        texto.setWordWrap(True)
        dentro.addWidget(rotulo)
        dentro.addWidget(texto)

        self.columna.addWidget(caja)
        return dentro

    def _accion(self, texto, icono, funcion, estilo="Sutil", pista=""):
        control = boton(texto, estilo, icono, pista)
        self._iconos_de_accion[control] = icono
        control.clicked.connect(funcion)
        return control

    def _montar_mis_datos(self):
        """
        Los datos del emisor, los mismos que encabezan cada documento.

        Hasta ahora se escribían una vez al instalar y no había forma de
        corregirlos: una errata en el NIF obligaba a empezar de cero. Aquí se
        cambian, y la cuenta bancaria se añade también, que es lo que hace
        falta para que a uno le paguen.
        """
        dentro = self._tarjeta(
            "Mis datos",
            "Son los que salen impresos como emisor en cada factura y en cada "
            "presupuesto. Lo que cambies aquí sale en los documentos que generes "
            "a partir de ahora.",
        )

        self.mis_campos = {}
        formulario = QFormLayout()
        formulario.setSpacing(9)
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for clave, rotulo, marcador in (
            ("nombre", "Nombre *", "Carlos"),
            ("apellido", "Apellidos *", "García López"),
            ("nif", "NIF o NIE *", "12345678Z"),
            ("direccion", "Dirección *", "Calle Mayor 12, 2ºA"),
            ("codigo_postal", "Código postal *", "28001"),
            ("telefono", "Teléfono *", "612345678"),
            ("email", "Correo *", "tu@correo.es"),
            ("entidad", "Entidad bancaria", "Banco Santander"),
            ("iban", "IBAN", "ES91 2100 0418 4502 0005 1332"),
        ):
            campo = QLineEdit()
            campo.setPlaceholderText(marcador)
            campo.setMinimumHeight(32)
            self.mis_campos[clave] = campo
            formulario.addRow(etiqueta(rotulo), campo)
        dentro.addLayout(formulario)

        dentro.addWidget(etiqueta(
            "La entidad y el IBAN salen impresos solo en las facturas, debajo "
            "del total: un presupuesto todavía no se cobra.",
            "Apunte",
        ))

        self.error_datos = etiqueta("", "Error")
        self.error_datos.setWordWrap(True)
        dentro.addWidget(self.error_datos)

        botones = QHBoxLayout()
        botones.setSpacing(8)
        botones.addWidget(self._accion("Guardar mis datos", "aceptar",
                                       self._guardar_datos, "Primario"))
        botones.addWidget(self._accion("Deshacer", "restaurar", self._pintar_mis_datos))
        botones.addStretch()
        dentro.addLayout(botones)

    def _montar_seguridad(self):
        dentro = self._tarjeta(
            "Seguridad",
            "Si tus datos están cifrados, el fichero no se puede leer sin tu "
            "contraseña: ni en este ordenador ni en otro. Lo que no protege es "
            "un virus que corra con tu sesión mientras BillEase está abierto.",
        )

        self.estado_cifrado = QLabel()
        self.estado_cifrado.setWordWrap(True)
        self.escudo = QLabel()

        fila = QHBoxLayout()
        fila.setSpacing(12)
        fila.addWidget(self.escudo)
        fila.addWidget(self.estado_cifrado, 1)
        dentro.addLayout(fila)

        botones = QHBoxLayout()
        botones.setSpacing(8)
        self.boton_cifrar = self._accion("Cifrar ahora", "candado", self._cifrar, "Primario")
        self.boton_clave = self._accion("Cambiar la contraseña", "llave", self._cambiar_clave)
        self.boton_exportar_claro = self._accion(
            "Sacar una copia sin cifrar", "exportar", self._exportar_sin_cifrar
        )
        botones.addWidget(self.boton_cifrar)
        botones.addWidget(self.boton_clave)
        botones.addWidget(self.boton_exportar_claro)
        botones.addStretch()
        dentro.addLayout(botones)

    def _montar_logotipo(self):
        dentro = self._tarjeta(
            "Logotipo",
            "Aparece arriba del todo en cada factura y en cada presupuesto. Se "
            "guarda la ruta de la imagen, no la imagen: si la mueves de sitio, "
            "vuelve a elegirla aquí.",
        )

        self.vista_logo = QLabel()
        self.vista_logo.setFixedHeight(ALTO_VISTA)
        self.vista_logo.setMinimumWidth(170)
        self.vista_logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.ruta_logo = QLabel()
        self.ruta_logo.setObjectName("Apunte")
        self.ruta_logo.setWordWrap(True)

        fila = QHBoxLayout()
        fila.setSpacing(14)
        fila.addWidget(self.vista_logo)
        fila.addWidget(self.ruta_logo, 1)
        dentro.addLayout(fila)

        botones = QHBoxLayout()
        botones.setSpacing(8)
        botones.addWidget(self._accion("Elegir imagen", "imagen", self._elegir_logotipo,
                                       "Primario"))
        self.quitar_logo = self._accion("Quitar", "menos", self._quitar_logotipo, "Peligro")
        botones.addWidget(self.quitar_logo)
        botones.addStretch()
        dentro.addLayout(botones)

    def _montar_carpetas(self):
        """
        Dónde va cada PDF al generarlo.

        Sin esto, cada «Generar PDF» abría el diálogo de guardar en la última
        carpeta que hubiera usado Windows, que casi nunca era la que tocaba:
        las facturas acababan repartidas entre el Escritorio, Descargas y la
        carpeta del último adjunto que se abrió.
        """
        dentro = self._tarjeta(
            "Dónde se guardan los PDF",
            "Una carpeta para las facturas y otra para los presupuestos. Al "
            "generar el PDF va a la suya, con su número de nombre y sin "
            "preguntar. Si dejas una en blanco, se sigue preguntando cada vez.",
        )

        self.carpetas = {}
        for tipo, rotulo in ((FACTURA, "Facturas"), (PRESUPUESTO, "Presupuestos")):
            dentro.addLayout(self._fila_de_carpeta(tipo, rotulo))

    def _fila_de_carpeta(self, tipo, rotulo):
        nombre = QLabel(rotulo)
        nombre.setObjectName("Etiqueta")
        nombre.setFixedWidth(110)

        donde = QLabel()
        donde.setObjectName("Apunte")
        donde.setWordWrap(True)
        donde.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        elegir = self._accion(
            "Elegir carpeta", "carpeta", lambda _=False, t=tipo: self._elegir_carpeta(t)
        )
        quitar = self._accion(
            "Quitar", "menos", lambda _=False, t=tipo: self._quitar_carpeta(t), "Peligro"
        )

        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addWidget(nombre)
        fila.addWidget(donde, 1)
        fila.addWidget(elegir)
        fila.addWidget(quitar)

        self.carpetas[tipo] = {"donde": donde, "quitar": quitar}
        return fila

    def _montar_copias(self):
        dentro = self._tarjeta(
            "Copias de seguridad",
            "Se guarda una copia al cerrar el programa, y aquí puedes hacer una "
            "cuando quieras. Restaurar guarda antes lo que haya ahora, para que "
            "equivocarse de copia no sea un camino de ida.",
        )

        self.donde = QLabel()
        self.donde.setObjectName("Etiqueta")
        self.donde.setWordWrap(True)
        self.donde.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dentro.addWidget(self.donde)

        self.lista_copias = QListWidget()
        self.lista_copias.setMinimumHeight(132)
        self.lista_copias.setMaximumHeight(190)
        self.lista_copias.itemSelectionChanged.connect(self._cambio_copia)
        dentro.addWidget(self.lista_copias)

        botones = QHBoxLayout()
        botones.setSpacing(8)
        botones.addWidget(self._accion("Copiar ahora", "copia", self._copiar, "Primario"))
        self.boton_restaurar = self._accion("Restaurar la elegida", "restaurar",
                                            self._restaurar)
        self.boton_restaurar.setEnabled(False)
        botones.addWidget(self.boton_restaurar)
        self.boton_carpeta = self._accion("Ver la carpeta", "carpeta", self._abrir_carpeta)
        botones.addWidget(self.boton_carpeta)
        botones.addStretch()
        dentro.addLayout(botones)

    def _montar_exportacion(self):
        dentro = self._tarjeta(
            "Exportar a CSV",
            "Documentos, conceptos y clientes en tres ficheros que abre Excel y "
            "entiende cualquier gestoría. Tus datos no se quedan encerrados aquí.",
        )
        botones = QHBoxLayout()
        botones.setSpacing(8)
        botones.addWidget(self._accion("Exportar todo", "exportar", self._exportar,
                                       "Primario"))
        botones.addStretch()
        dentro.addLayout(botones)

    def repintar_iconos(self):
        for control, nombre in self._iconos_de_accion.items():
            control.setIcon(iconos.icono(nombre))
        self._pintar_logotipo()

    # ───────────────────────────── datos ─────────────────────────────

    def cargar(self):
        self._pintar_mis_datos()
        self._pintar_seguridad()
        self._pintar_logotipo()
        self._pintar_carpetas()
        self._pintar_copias()

    def _pintar_mis_datos(self):
        emisor = repo_autonomo.obtener()
        self.error_datos.setText("")
        if emisor is None:
            return
        valores = {
            "nombre": emisor.nombre, "apellido": emisor.apellido, "nif": emisor.nif,
            "direccion": emisor.direccion, "codigo_postal": emisor.codigo_postal,
            "telefono": emisor.telefono, "email": emisor.email,
            "entidad": emisor.entidad, "iban": formatear_iban(emisor.iban),
        }
        for clave, campo in self.mis_campos.items():
            campo.setText(valores.get(clave, ""))

    def _guardar_datos(self):
        datos = {c: campo.text().strip() for c, campo in self.mis_campos.items()}
        correcto, errores = validar_formulario(datos, {
            "nombre": OBLIGATORIO,
            "apellido": OBLIGATORIO,
            "direccion": OBLIGATORIO,
            "nif": NIF_O_NIE,
            "codigo_postal": CODIGO_POSTAL,
            "telefono": TELEFONO,
            "email": EMAIL,
            "iban": IBAN_OPCIONAL,
        })
        if not correcto:
            nombres = {
                "nombre": "Nombre", "apellido": "Apellidos", "nif": "NIF",
                "direccion": "Dirección", "codigo_postal": "Código postal",
                "telefono": "Teléfono", "email": "Correo", "iban": "IBAN",
            }
            self.error_datos.setText("\n".join(
                f"· {nombres.get(campo, campo)}: {fallo}"
                for campo, fallo in errores.items()
            ))
            return

        guardado = repo_autonomo.actualizar(Autonomo(
            nif=datos["nif"], nombre=datos["nombre"], apellido=datos["apellido"],
            direccion=datos["direccion"], codigo_postal=datos["codigo_postal"],
            telefono=datos["telefono"], email=datos["email"],
            entidad=datos["entidad"], iban=datos["iban"],
        ))
        if not guardado:
            self.error_datos.setText(
                "· No se han podido guardar los datos. Comprueba el NIF."
            )
            return

        self._pintar_mis_datos()
        QMessageBox.information(
            self, "Datos guardados",
            "Los documentos que generes a partir de ahora salen con estos datos.",
        )

    def _pintar_seguridad(self):
        cifrada = caja.es_caja(ruta_base_datos())

        self.escudo.setPixmap(iconos.pixmap(
            "escudo" if cifrada else "candado", 34,
            theme.color("ok" if cifrada else "aviso"),
        ))
        if cifrada:
            datos = caja.información(ruta_base_datos())
            self.estado_cifrado.setText(
                f"Tus datos están cifrados con AES-256 desde el "
                f"{datos['creada'][:10]}. Hace falta tu contraseña para abrirlos, "
                f"y el código de recuperación si la olvidas."
            )
        else:
            self.estado_cifrado.setText(
                "Tus datos NO están cifrados: cualquiera con acceso al fichero "
                "puede leer tus clientes y tus facturas con un visor de SQLite."
            )

        self.boton_cifrar.setVisible(not cifrada)
        self.boton_exportar_claro.setVisible(cifrada)

    def _pintar_logotipo(self):
        emisor = repo_autonomo.obtener()
        ruta = (emisor.logotipo if emisor else "") or ""

        if ruta and Path(ruta).is_file():
            imagen = QPixmap(ruta)
            if not imagen.isNull():
                self.vista_logo.setPixmap(imagen.scaledToHeight(
                    ALTO_VISTA, Qt.TransformationMode.SmoothTransformation
                ))
                self.ruta_logo.setText(ruta)
                self.quitar_logo.setEnabled(True)
                return

        self.vista_logo.setPixmap(
            iconos.pixmap("imagen", 40, theme.color("borde_fuerte"))
        )
        self.ruta_logo.setText(
            "La imagen ya no está donde estaba: elígela otra vez." if ruta
            else "Todavía no has puesto logotipo. Los documentos salen sin él."
        )
        self.quitar_logo.setEnabled(bool(ruta))

    def _pintar_carpetas(self):
        for tipo, controles in self.carpetas.items():
            ruta = repo_autonomo.carpeta_de(tipo)
            if not ruta:
                controles["donde"].setText("Se pregunta al generar cada PDF.")
            elif not Path(ruta).is_dir():
                # Un disco externo que no está puesto, o una carpeta
                # renombrada: se dice, y al generar se vuelve a preguntar.
                controles["donde"].setText(f"{ruta} — esa carpeta ya no existe")
            else:
                controles["donde"].setText(ruta)
            controles["quitar"].setEnabled(bool(ruta))

    def _elegir_carpeta(self, tipo):
        actual = repo_autonomo.carpeta_de(tipo)
        elegida = QFileDialog.getExistingDirectory(
            self, "Dónde guardar los PDF", actual or str(Path.home())
        )
        if not elegida:
            return
        repo_autonomo.guardar_carpeta(tipo, elegida)
        self._pintar_carpetas()

    def _quitar_carpeta(self, tipo):
        repo_autonomo.guardar_carpeta(tipo, "")
        self._pintar_carpetas()

    def _pintar_copias(self):
        base = ruta_base_datos()
        self.donde.setText(f"Base de datos: {base}")

        self.lista_copias.clear()
        for copia in backup.copias(base):
            fecha = backup.fecha_de(copia)
            cuando = fecha.strftime("%d/%m/%Y a las %H:%M") if fecha else copia.name
            elemento = QListWidgetItem(f"{cuando}   ·   {kilobytes(copia)}")
            elemento.setData(Qt.ItemDataRole.UserRole, str(copia))
            elemento.setToolTip(str(copia))
            self.lista_copias.addItem(elemento)

        if not self.lista_copias.count():
            vacio = QListWidgetItem("Todavía no hay ninguna copia.")
            vacio.setFlags(Qt.ItemFlag.NoItemFlags)
            self.lista_copias.addItem(vacio)
        self._cambio_copia()

    def _cambio_copia(self):
        self.boton_restaurar.setEnabled(self.copia_elegida() is not None)

    def copia_elegida(self):
        elemento = self.lista_copias.currentItem()
        if elemento is None:
            return None
        ruta = elemento.data(Qt.ItemDataRole.UserRole)
        return Path(ruta) if ruta else None

    # ───────────────────────────── acciones ─────────────────────────────

    def _cifrar(self):
        from ui.views.seguridad import DialogoCifrar, DialogoCodigo

        dialogo = DialogoCifrar(ruta_base_datos(), self)
        if not dialogo.exec():
            return
        DialogoCodigo(dialogo.codigo, self).exec()
        self.cargar()
        ventana = self.window()
        if hasattr(ventana, "recargar_todo"):
            ventana.recargar_todo()

    def _cambiar_clave(self):
        from ui.views.seguridad import DialogoCambioContrasena

        DialogoCambioContrasena(ruta_base_datos(), self).exec()

    def _exportar_sin_cifrar(self):
        from ui.views.seguridad import exportar_sin_cifrar

        exportar_sin_cifrar(ruta_base_datos(), self)

    def _elegir_logotipo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir logotipo", "", IMAGENES)
        if not ruta:
            return
        if QPixmap(ruta).isNull():
            QMessageBox.warning(
                self, "No es una imagen",
                "Ese fichero no se puede leer como imagen. Prueba con un PNG o un JPG.",
            )
            return
        repo_autonomo.guardar_logotipo(ruta)
        self._pintar_logotipo()

    def _quitar_logotipo(self):
        repo_autonomo.guardar_logotipo("")
        self._pintar_logotipo()

    def _copiar(self):
        copia = backup.copiar()
        if copia is None:
            QMessageBox.warning(
                self, "No hay nada que copiar",
                "Todavía no existe la base de datos.",
            )
            return
        self._pintar_copias()
        QMessageBox.information(
            self, "Copia guardada",
            f"La copia está en:\n{copia}\n\nSe guardan las "
            f"{backup.CUANTAS_SE_GUARDAN} últimas.",
        )

    def _restaurar(self):
        copia = self.copia_elegida()
        if copia is None:
            return

        fecha = backup.fecha_de(copia)
        cuando = fecha.strftime("%d/%m/%Y a las %H:%M") if fecha else copia.name
        if QMessageBox.question(
            self, "Restaurar la copia",
            f"Se sustituirán todos los datos actuales por los de la copia del "
            f"{cuando}.\n\nLo que hay ahora se guarda antes como otra copia, así "
            f"que esto se puede deshacer.\n\n¿Seguir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        try:
            resultado = backup.restaurar(copia)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo restaurar", str(e))
            return

        self._pintar_copias()
        ventana = self.window()
        if hasattr(ventana, "recargar_todo"):
            ventana.recargar_todo()
        QMessageBox.information(
            self, "Datos restaurados",
            f"La base vuelve a ser la del {cuando}.\n\n"
            f"Lo anterior ha quedado guardado en:\n{resultado['copia_previa']}",
        )

    def _abrir_carpeta(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        carpeta = backup.directorio()
        carpeta.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

    def _exportar(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Dónde dejar los ficheros")
        if not carpeta:
            return
        try:
            escrito = exportar_todo(
                carpeta,
                repo_documentos.listar() + repo_documentos.listar("presupuesto"),
                repo_clientes.listar(),
                lineas_de=repo_documentos.lineas_de,
            )
        except OSError as e:
            QMessageBox.critical(self, "No se pudo exportar", str(e))
            return

        detalle = "\n".join(f"· {nombre}: {cuantas} filas"
                            for nombre, cuantas in escrito.items())
        QMessageBox.information(
            self, "Exportado",
            f"En {carpeta}:\n\n{detalle}\n\nSe abren con Excel directamente.",
        )

    def nuevo_elemento(self):
        """`Ctrl+N` aquí no crea nada."""
        return None
