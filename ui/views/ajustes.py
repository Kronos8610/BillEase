"""
Ajustes: el logotipo, las copias de seguridad y la exportación.

Las tres cosas que un programa que se instala tiene que ofrecer y que hasta
ahora no estaban en ninguna parte: poner la marca propia en el papel, poder
recuperar los datos si algo va mal, y poder sacarlos para la gestoría sin
depender del programa.

También dice **dónde vive la base de datos**. Parece un detalle y no lo es:
la versión anterior la creaba en el directorio desde el que se arrancara, así
que los datos «desaparecían» al abrir el programa desde otro sitio.
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

import theme
from config import ruta_base_datos
from data import backup
from data.repositories import autonomo as repo_autonomo
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from documents.export_csv import exportar_todo
from ui import iconos
from ui.views.listado import boton

IMAGENES = "Imágenes (*.png *.jpg *.jpeg)"
ALTO_VISTA = 64


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

        centrado = QHBoxLayout()
        contenido = QWidget()
        contenido.setMaximumWidth(theme.ancho_maximo())
        centrado.addStretch(1)
        centrado.addWidget(contenido, 100)
        centrado.addStretch(1)
        raiz.addLayout(centrado)

        self.columna = QVBoxLayout(contenido)
        self.columna.setContentsMargins(32, 28, 32, 28)
        self.columna.setSpacing(16)

        titulo = QLabel("Ajustes")
        titulo.setObjectName("Titulo")
        apunte = QLabel("Tu marca en el papel, tus datos a salvo y fuera del programa.")
        apunte.setObjectName("Apunte")
        self.columna.addWidget(titulo)
        self.columna.addWidget(apunte)

        self._montar_logotipo()
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
        self._pintar_logotipo()
        self._pintar_copias()

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
