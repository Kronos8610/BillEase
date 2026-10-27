"""
El editor de documentos: uno solo para facturas y presupuestos.

Sustituye a `crearFactura.py` y `editarFactura.py`, que eran 1.176 líneas casi
idénticas —el mismo formulario copiado dos veces—, y a `crearServicio.py`, que
ya no hace falta porque los conceptos se escriben.

Tres cosas cambian respecto a lo anterior:

- **El concepto se escribe.** Un cuadro de texto que crece con el contenido, en
  lugar de un desplegable con un catálogo que había que rellenar antes.
- **Los datos fiscales del cliente son de solo lectura.** Antes eran seis
  campos editables cuyo contenido se descartaba en silencio al guardar
  (defecto 06): lo que el usuario corrigiera ahí no llegaba a ninguna parte.
- **El total se ve mientras escribes**, calculado con la misma función que el
  PDF, así que pantalla y papel no pueden discrepar.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import theme
from core.fechas import a_espanol, hoy_iso
from core.models import FACTURA, PRESUPUESTO, UNIDADES, Linea
from core.money import a_decimal, formatear
from core.taxes import calcular
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from ui import iconos
from ui.widgets.concepto import CampoConcepto


def etiqueta(texto, nombre="Etiqueta"):
    """Un rótulo. El color y el tamaño los pone la hoja de estilos, no aquí."""
    marca = QLabel(texto)
    marca.setObjectName(nombre)
    return marca


class FilaConcepto(QWidget):
    """Un concepto: su texto, la cantidad, la unidad, el precio y el importe."""

    def __init__(self, numero, sugerencias, al_cambiar, al_borrar, parent=None):
        super().__init__(parent)
        self._al_cambiar = al_cambiar
        self.setObjectName("Concepto")
        # Un QWidget corriente no pinta el fondo que le da la hoja de estilos
        # si no se le pide expresamente.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 10, 12, 12)
        raiz.setSpacing(8)

        cabecera = QHBoxLayout()
        self.etiqueta = etiqueta(f"Concepto {numero}")
        borrar = QPushButton("Quitar")
        borrar.setObjectName("Peligro")
        borrar.setCursor(Qt.CursorShape.PointingHandCursor)
        borrar.setIcon(iconos.icono("menos", 14, theme.color("peligro")))
        borrar.setIconSize(iconos.medida(14))
        borrar.clicked.connect(lambda: al_borrar(self))
        cabecera.addWidget(self.etiqueta)
        cabecera.addStretch()
        cabecera.addWidget(borrar)
        raiz.addLayout(cabecera)

        self.descripcion = CampoConcepto(sugerencias)
        self.descripcion.setMinimumHeight(64)
        # Un concepto se describe entero, pero tres renglones bastan para
        # verlo: si no se le pone techo, el cuadro se come la pantalla.
        self.descripcion.setMaximumHeight(96)
        raiz.addWidget(self.descripcion)

        numeros = QHBoxLayout()
        numeros.setSpacing(10)

        self.cantidad = QLineEdit("1")
        self.unidad = QComboBox()
        self.unidad.setEditable(True)   # se puede escribir una unidad propia
        self.unidad.addItems(UNIDADES)
        self.precio = QLineEdit()
        self.precio.setPlaceholderText("0,00")
        self.importe = QLineEdit()
        self.importe.setReadOnly(True)

        for control, titulo in (
            (self.cantidad, "Cantidad"),
            (self.unidad, "Unidad"),
            (self.precio, "Precio"),
            (self.importe, "Importe"),
        ):
            columna = QVBoxLayout()
            columna.setSpacing(3)
            control.setMinimumHeight(30)
            columna.addWidget(etiqueta(titulo))
            columna.addWidget(control)
            numeros.addLayout(columna, 1)

        raiz.addLayout(numeros)

        self.cantidad.textChanged.connect(self._refrescar)
        self.precio.textChanged.connect(self._refrescar)
        self.descripcion.textChanged.connect(lambda: self._al_cambiar())
        self._refrescar()

    def _refrescar(self):
        """El importe se calcula con Decimal, igual que el total y el PDF."""
        self.importe.setText(formatear(self.linea().importe))
        self._al_cambiar()

    def renumerar(self, numero):
        self.etiqueta.setText(f"Concepto {numero}")

    def linea(self):
        """Lo escrito, como línea del dominio."""
        try:
            cantidad = a_decimal(self.cantidad.text())
            precio = a_decimal(self.precio.text())
        except ArithmeticError:
            cantidad = precio = a_decimal(0)
        return Linea(
            descripcion=self.descripcion.texto(),
            cantidad=cantidad,
            precio_ud=precio,
            unidad=self.unidad.currentText().strip() or "ud",
        )

    def es_valida(self):
        linea = self.linea()
        return bool(linea.descripcion) and linea.cantidad > 0 and linea.precio_ud > 0

    def rellenar(self, linea):
        self.descripcion.setPlainText(linea.descripcion)
        self.cantidad.setText(str(linea.cantidad))
        self.unidad.setCurrentText(linea.unidad)
        self.precio.setText(formatear(linea.precio_ud))


class DocumentoEditor(QDialog):
    """
    Crea o edita una factura o un presupuesto.

    `tipo` decide la cabecera y la serie. No hay fechas de plazo: aquí no se
    trabaja con vencimientos ni con validez.
    """

    def __init__(self, tipo=FACTURA, documento_id=None, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        self.documento_id = documento_id
        self.es_presupuesto = tipo == PRESUPUESTO
        self.filas = []

        self.setModal(True)
        self.setMinimumSize(900, 640)
        self.setSizeGripEnabled(True)

        self._sugerencias = repo_documentos.descripciones_usadas()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        contenido = QWidget()
        self.columna = QVBoxLayout(contenido)
        self.columna.setContentsMargins(28, 24, 28, 24)
        self.columna.setSpacing(16)

        self._montar_titulo()
        self._montar_cliente()
        self._montar_obra()
        self._montar_fecha()
        self._montar_conceptos()
        self._montar_observaciones()
        self._montar_totales()
        self.columna.addStretch()

        desplazable.setWidget(contenido)
        raiz.addWidget(desplazable)
        raiz.addWidget(self._montar_botones())

        self._cargar_clientes()
        if documento_id:
            self._precargar()
        else:
            self._nuevo()
        self._refrescar_totales()

    # ───────────────────────────── montaje ─────────────────────────────

    def _seccion(self, titulo):
        caja = QFrame()
        caja.setObjectName("Tarjeta")
        dentro = QVBoxLayout(caja)
        dentro.setContentsMargins(18, 16, 18, 18)
        dentro.setSpacing(10)
        dentro.addWidget(etiqueta(titulo, "Subtitulo"))
        self.columna.addWidget(caja)
        return dentro

    def _campo(self, marcador="", solo_lectura=False):
        campo = QLineEdit()
        campo.setPlaceholderText(marcador)
        campo.setMinimumHeight(32)
        campo.setReadOnly(solo_lectura)
        return campo

    def _montar_titulo(self):
        self.titulo = QLabel()
        self.titulo.setObjectName("Titulo")
        self.columna.addWidget(self.titulo)

    def _montar_cliente(self):
        dentro = self._seccion("Cliente")
        self.cliente_combo = QComboBox()
        self.cliente_combo.setMinimumHeight(32)
        self.cliente_combo.currentIndexChanged.connect(self._cliente_elegido)
        dentro.addWidget(self.cliente_combo)

        self.datos_cliente = etiqueta("")
        self.datos_cliente.setWordWrap(True)
        dentro.addWidget(self.datos_cliente)

    def _montar_obra(self):
        """
        Dónde se hace el trabajo, que no es lo mismo que a quién se le factura.

        Se le factura a la oficina de una empresa una obra que está en otra
        calle, y quien recibe el papel necesita saber de cuál se habla. Sale
        impreso justo encima de los conceptos.
        """
        dentro = self._seccion("Dirección de la obra")
        self.direccion_obra = self._campo(
            "Calle, número y población donde se hace el trabajo"
        )
        dentro.addWidget(self.direccion_obra)

    def _montar_fecha(self):
        """
        La fecha de emisión, y ninguna más.

        Aquí había además un plazo —«Vencimiento» en las facturas y «Válido
        hasta» en los presupuestos—. Se quitó: no se trabaja con plazos, y un
        campo que nadie usa es un campo que se rellena mal.
        """
        dentro = self._seccion("Fecha")
        fila = QHBoxLayout()
        fila.setSpacing(14)

        self.fecha = self._campo("dd/mm/aaaa")
        fila.addWidget(self.fecha, 1)
        fila.addStretch(2)
        dentro.addLayout(fila)

    def _montar_conceptos(self):
        dentro = self._seccion("Conceptos")
        self.lista_conceptos = QVBoxLayout()
        self.lista_conceptos.setSpacing(10)
        dentro.addLayout(self.lista_conceptos)

        anadir = QPushButton("Añadir concepto")
        anadir.setCursor(Qt.CursorShape.PointingHandCursor)
        anadir.setIcon(iconos.icono("mas"))
        anadir.setIconSize(iconos.medida())
        anadir.setShortcut(QKeySequence("Ctrl+Shift+N"))
        anadir.setToolTip("Ctrl+Mayús+N")
        anadir.clicked.connect(lambda: self._anadir_fila())
        dentro.addWidget(anadir, alignment=Qt.AlignmentFlag.AlignLeft)

    def _montar_observaciones(self):
        dentro = self._seccion("Observaciones")
        self.observaciones = QTextEdit()
        self.observaciones.setMinimumHeight(70)
        self.observaciones.setPlaceholderText(
            "Referencia de la obra, condiciones, avisos…"
        )
        dentro.addWidget(self.observaciones)

    def _montar_totales(self):
        dentro = self._seccion("Resumen")
        self.linea_base = etiqueta("")
        self.linea_iva = etiqueta("")
        self.linea_total = QLabel()
        self.linea_total.setObjectName("Importe")
        for rotulo in (self.linea_base, self.linea_iva):
            dentro.addWidget(rotulo)

        separador = QFrame()
        separador.setObjectName("Separador")
        separador.setFrameShape(QFrame.Shape.HLine)
        dentro.addWidget(separador)
        dentro.addWidget(self.linea_total)

    def _montar_botones(self):
        barra = QWidget()
        fila = QHBoxLayout(barra)
        fila.setContentsMargins(28, 12, 28, 16)

        cancelar = QPushButton("Cancelar")
        cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        cancelar.clicked.connect(self.reject)

        self.boton_guardar = QPushButton()
        self.boton_guardar.setObjectName("Primario")
        self.boton_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_guardar.setDefault(True)
        self.boton_guardar.setShortcut(QKeySequence("Ctrl+Return"))
        self.boton_guardar.clicked.connect(self.guardar)

        fila.addStretch()
        fila.addWidget(cancelar)
        fila.addSpacing(10)
        fila.addWidget(self.boton_guardar)
        return barra

    # ───────────────────────────── datos ─────────────────────────────

    def _cargar_clientes(self):
        self.cliente_combo.clear()
        self.cliente_combo.addItem("— Elige un cliente —", None)
        for cliente in repo_clientes.listar():
            self.cliente_combo.addItem(f"{cliente.nombre} ({cliente.nif})", cliente)

    def _cliente_elegido(self):
        cliente = self.cliente_combo.currentData()
        if cliente is None:
            self.datos_cliente.setText("")
            return
        partes = [f"{cliente.etiqueta_fiscal} {cliente.nif}"]
        if cliente.direccion:
            partes.append(cliente.direccion)
        if cliente.codigo_postal:
            partes.append(cliente.codigo_postal)
        if cliente.telefono:
            partes.append(cliente.telefono)
        self.datos_cliente.setText(" · ".join(partes))

    def _nuevo(self):
        rotulo = "Nuevo presupuesto" if self.es_presupuesto else "Nueva factura"
        self.setWindowTitle(rotulo)
        self.titulo.setText(rotulo)
        self.boton_guardar.setText(
            "Guardar presupuesto" if self.es_presupuesto else "Emitir factura"
        )
        self.fecha.setText(a_espanol(hoy_iso()))
        self._anadir_fila()

    def _precargar(self):
        documento = repo_documentos.obtener(self.documento_id)
        if documento is None:
            QMessageBox.warning(self, "No encontrado", "Ese documento ya no existe.")
            self.reject()
            return

        self.tipo = documento.tipo
        self.es_presupuesto = documento.es_presupuesto
        self.setWindowTitle(f"Editar {documento.referencia}")
        self.titulo.setText(f"{documento.rotulo.capitalize()} {documento.referencia}")
        self.boton_guardar.setText("Guardar cambios")

        for i in range(self.cliente_combo.count()):
            cliente = self.cliente_combo.itemData(i)
            if cliente and cliente.id == documento.cliente_id:
                self.cliente_combo.setCurrentIndex(i)
                break

        self.fecha.setText(a_espanol(documento.fecha))
        self.direccion_obra.setText(documento.direccion_obra)
        self.observaciones.setPlainText(documento.observaciones)

        for linea in documento.lineas:
            self._anadir_fila(linea)
        if not documento.lineas:
            self._anadir_fila()

    # ───────────────────────────── conceptos ─────────────────────────────

    def _anadir_fila(self, linea=None):
        fila = FilaConcepto(
            len(self.filas) + 1,
            self._sugerencias,
            self._refrescar_totales,
            self._quitar_fila,
        )
        if linea is not None:
            fila.rellenar(linea)
        self.filas.append(fila)
        self.lista_conceptos.addWidget(fila)
        self._refrescar_totales()
        return fila

    def _quitar_fila(self, fila):
        if len(self.filas) == 1:
            QMessageBox.information(
                self, "Hace falta un concepto",
                "Un documento necesita al menos un concepto. Bórralo entero desde "
                "el listado si ya no lo quieres."
            )
            return
        self.filas.remove(fila)
        fila.setParent(None)
        fila.deleteLater()
        for numero, restante in enumerate(self.filas, 1):
            restante.renumerar(numero)
        self._refrescar_totales()

    def lineas_validas(self):
        return [fila.linea() for fila in self.filas if fila.es_valida()]

    def _refrescar_totales(self):
        totales = calcular(self.lineas_validas())
        self.linea_base.setText(f"Base imponible:  {formatear(totales.base)} €")
        tipo = totales.tipo_unico if totales.tipo_unico is not None else 21
        self.linea_iva.setText(
            f"IVA {formatear(tipo).rstrip('0').rstrip(',')} %:  "
            f"{formatear(totales.cuota_iva)} €"
        )
        self.linea_total.setText(f"Total:  {formatear(totales.total)} €")

    # ───────────────────────────── guardado ─────────────────────────────

    def guardar(self):
        cliente = self.cliente_combo.currentData()
        if cliente is None:
            QMessageBox.warning(
                self, "Falta el cliente",
                "Elige a quién va dirigido este documento."
            )
            return

        if not self.fecha.text().strip():
            QMessageBox.warning(self, "Falta la fecha", "Indica la fecha del documento.")
            return

        lineas = self.lineas_validas()
        if not lineas:
            QMessageBox.warning(
                self, "Falta el trabajo",
                "Escribe al menos un concepto con su cantidad y su precio."
            )
            return

        incompletas = len(self.filas) - len(lineas)
        if incompletas:
            seguir = QMessageBox.question(
                self, "Hay conceptos a medias",
                f"{incompletas} concepto(s) están sin descripción, sin cantidad o sin "
                f"precio, y no se guardarán.\n\n¿Guardar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if seguir != QMessageBox.StandardButton.Yes:
                return

        observaciones = self.observaciones.toPlainText().strip()
        obra = self.direccion_obra.text().strip()

        if self.documento_id:
            guardado = repo_documentos.actualizar(
                self.documento_id, self.fecha.text().strip(), cliente.id, lineas,
                observaciones=observaciones, direccion_obra=obra,
            )
            documento_id = self.documento_id if guardado else None
        else:
            documento_id = repo_documentos.crear(
                self.fecha.text().strip(), cliente.id, lineas,
                observaciones=observaciones, tipo=self.tipo,
                direccion_obra=obra,
            )

        if not documento_id:
            QMessageBox.critical(
                self, "No se pudo guardar",
                "El documento no se ha guardado. Comprueba que el cliente siga "
                "existiendo y que la fecha sea correcta."
            )
            return

        documento = repo_documentos.obtener(documento_id, con_lineas=False)
        totales = calcular(lineas)
        QMessageBox.information(
            self, "Guardado",
            f"{documento.rotulo.capitalize()} {documento.referencia} · "
            f"{formatear(totales.total)} €\n"
            f"Base {formatear(totales.base)} € + IVA {formatear(totales.cuota_iva)} €"
        )
        self.documento_id = documento_id
        self.accept()
