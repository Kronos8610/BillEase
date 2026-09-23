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
from PyQt6.QtGui import QFont
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

from core.fechas import a_espanol, a_iso, hoy_iso
from core.models import FACTURA, PRESUPUESTO, UNIDADES, Linea
from core.money import a_decimal, formatear
from core.quotes import validez_por_defecto, vencimiento_por_defecto
from core.taxes import calcular
from data.repositories import clientes as repo_clientes
from data.repositories import documentos as repo_documentos
from ui.widgets.concepto import CampoConcepto
from utils.globals import (
    ALMOND,
    BODY_FONT,
    BYZANTIUM,
    CHAMPAGNE_PINK,
    LAVENDER_PINK,
    SUBTITLE_FONT,
    TITLE_FONT,
    TYRIAN_PURPLE,
)

ESTILO_CAMPO = f"""
    QLineEdit {{
        background-color: white;
        border: 1px solid {ALMOND};
        border-radius: 4px;
        padding: 5px 10px;
    }}
    QLineEdit:focus {{ border: 1px solid {BYZANTIUM}; }}
    QLineEdit[readOnly="true"] {{ background-color: #F4F4F2; color: #5C5C5C; }}
"""


class FilaConcepto(QWidget):
    """Un concepto: su texto, la cantidad, la unidad, el precio y el importe."""

    def __init__(self, numero, sugerencias, al_cambiar, al_borrar, parent=None):
        super().__init__(parent)
        self._al_cambiar = al_cambiar
        self.setStyleSheet(
            f"FilaConcepto {{ background-color: #FBFBFA; border: 1px solid {ALMOND};"
            f" border-radius: 6px; }}"
        )

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 10, 12, 12)
        raiz.setSpacing(8)

        cabecera = QHBoxLayout()
        self.etiqueta = QLabel(f"Concepto {numero}")
        self.etiqueta.setStyleSheet(f"color: {BYZANTIUM}; font-size: 11px;")
        borrar = QPushButton("Quitar")
        borrar.setCursor(Qt.CursorShape.PointingHandCursor)
        borrar.setStyleSheet(
            "QPushButton { background: transparent; color: #C42B1C; border: none;"
            " font-size: 11px; } QPushButton:hover { text-decoration: underline; }"
        )
        borrar.clicked.connect(lambda: al_borrar(self))
        cabecera.addWidget(self.etiqueta)
        cabecera.addStretch()
        cabecera.addWidget(borrar)
        raiz.addLayout(cabecera)

        self.descripcion = CampoConcepto(sugerencias)
        self.descripcion.setMinimumHeight(64)
        self.descripcion.setStyleSheet(
            f"QPlainTextEdit {{ background-color: white; border: 1px solid {ALMOND};"
            f" border-radius: 4px; padding: 6px 8px; }}"
            f"QPlainTextEdit:focus {{ border: 1px solid {BYZANTIUM}; }}"
        )
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

        for campo, etiqueta in (
            (self.cantidad, "Cantidad"),
            (self.unidad, "Unidad"),
            (self.precio, "Precio"),
            (self.importe, "Importe"),
        ):
            columna = QVBoxLayout()
            columna.setSpacing(3)
            titulo = QLabel(etiqueta)
            titulo.setStyleSheet(f"color: {BYZANTIUM}; font-size: 11px;")
            campo.setMinimumHeight(30)
            if isinstance(campo, QLineEdit):
                campo.setStyleSheet(ESTILO_CAMPO)
            columna.addWidget(titulo)
            columna.addWidget(campo)
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

    `tipo` decide la cabecera, la serie y si el plazo es de vencimiento (las
    facturas) o de validez (los presupuestos).
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
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")

        self._sugerencias = repo_documentos.descripciones_usadas()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        contenido = QWidget()
        self.columna = QVBoxLayout(contenido)
        self.columna.setContentsMargins(28, 24, 28, 24)
        self.columna.setSpacing(16)

        self._montar_titulo()
        self._montar_cliente()
        self._montar_fechas()
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
        caja = QWidget()
        caja.setStyleSheet(
            f"QWidget {{ background-color: white; border: 1px solid {ALMOND};"
            f" border-radius: 8px; }}"
        )
        dentro = QVBoxLayout(caja)
        dentro.setContentsMargins(18, 16, 18, 18)
        dentro.setSpacing(10)
        etiqueta = QLabel(titulo)
        etiqueta.setFont(TITLE_FONT)
        etiqueta.setStyleSheet(f"color: {TYRIAN_PURPLE}; border: none;")
        dentro.addWidget(etiqueta)
        self.columna.addWidget(caja)
        return dentro

    def _campo(self, marcador="", solo_lectura=False):
        campo = QLineEdit()
        campo.setPlaceholderText(marcador)
        campo.setMinimumHeight(32)
        campo.setFont(BODY_FONT)
        campo.setReadOnly(solo_lectura)
        campo.setStyleSheet(ESTILO_CAMPO)
        return campo

    def _montar_titulo(self):
        self.titulo = QLabel()
        self.titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.titulo.setStyleSheet(f"color: {TYRIAN_PURPLE};")
        self.columna.addWidget(self.titulo)

    def _montar_cliente(self):
        dentro = self._seccion("Cliente")
        self.cliente_combo = QComboBox()
        self.cliente_combo.setMinimumHeight(32)
        self.cliente_combo.currentIndexChanged.connect(self._cliente_elegido)
        dentro.addWidget(self.cliente_combo)

        self.datos_cliente = QLabel()
        self.datos_cliente.setWordWrap(True)
        self.datos_cliente.setStyleSheet(
            f"color: {BYZANTIUM}; border: none; font-size: 12px;"
        )
        dentro.addWidget(self.datos_cliente)

        aviso = QLabel(
            "Los datos fiscales se toman de la ficha del cliente y quedan "
            "congelados en el documento al emitirlo."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color: #8A8A8A; border: none; font-size: 11px;")
        dentro.addWidget(aviso)

    def _montar_fechas(self):
        dentro = self._seccion("Fechas")
        fila = QHBoxLayout()
        fila.setSpacing(14)

        self.fecha = self._campo("dd/mm/aaaa")
        self.plazo = self._campo("dd/mm/aaaa")
        etiqueta_plazo = "Válido hasta" if self.es_presupuesto else "Vencimiento"

        for campo, etiqueta in ((self.fecha, "Fecha"), (self.plazo, etiqueta_plazo)):
            columna = QVBoxLayout()
            columna.setSpacing(3)
            titulo = QLabel(etiqueta)
            titulo.setStyleSheet(f"color: {BYZANTIUM}; border: none; font-size: 11px;")
            columna.addWidget(titulo)
            columna.addWidget(campo)
            fila.addLayout(columna, 1)
        fila.addStretch(2)
        dentro.addLayout(fila)

    def _montar_conceptos(self):
        dentro = self._seccion("Conceptos")
        self.lista_conceptos = QVBoxLayout()
        self.lista_conceptos.setSpacing(10)
        dentro.addLayout(self.lista_conceptos)

        anadir = QPushButton("+  Añadir concepto")
        anadir.setCursor(Qt.CursorShape.PointingHandCursor)
        anadir.setStyleSheet(
            f"QPushButton {{ background-color: {LAVENDER_PINK}; color: {TYRIAN_PURPLE};"
            f" border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #FF8CB6; }}"
        )
        anadir.clicked.connect(lambda: self._anadir_fila())
        dentro.addWidget(anadir, alignment=Qt.AlignmentFlag.AlignLeft)

        pista = QLabel(
            "Escribe libremente. Se te sugiere lo que ya has escrito otras veces, "
            "pero nunca hay que elegir de una lista."
        )
        pista.setWordWrap(True)
        pista.setStyleSheet("color: #8A8A8A; border: none; font-size: 11px;")
        dentro.addWidget(pista)

    def _montar_observaciones(self):
        dentro = self._seccion("Observaciones")
        self.observaciones = QTextEdit()
        self.observaciones.setMinimumHeight(70)
        self.observaciones.setPlaceholderText(
            "Forma de pago, referencia de la obra, condiciones…"
        )
        self.observaciones.setStyleSheet(
            f"QTextEdit {{ background-color: white; border: 1px solid {ALMOND};"
            f" border-radius: 4px; padding: 6px 8px; }}"
        )
        dentro.addWidget(self.observaciones)

    def _montar_totales(self):
        dentro = self._seccion("Resumen")
        self.linea_base = QLabel()
        self.linea_iva = QLabel()
        self.linea_total = QLabel()
        for etiqueta in (self.linea_base, self.linea_iva):
            etiqueta.setStyleSheet(f"color: {BYZANTIUM}; border: none;")
            dentro.addWidget(etiqueta)

        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.HLine)
        separador.setStyleSheet(f"background-color: {ALMOND}; max-height: 1px; border: none;")
        dentro.addWidget(separador)

        self.linea_total.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.linea_total.setStyleSheet(f"color: {TYRIAN_PURPLE}; border: none;")
        dentro.addWidget(self.linea_total)

    def _montar_botones(self):
        barra = QWidget()
        fila = QHBoxLayout(barra)
        fila.setContentsMargins(28, 12, 28, 16)

        cancelar = QPushButton("Cancelar")
        cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        cancelar.setStyleSheet(
            f"QPushButton {{ background-color: white; color: {TYRIAN_PURPLE};"
            f" border: 1px solid {TYRIAN_PURPLE}; border-radius: 5px; padding: 9px 20px; }}"
        )
        cancelar.clicked.connect(self.reject)

        self.boton_guardar = QPushButton()
        self.boton_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_guardar.setStyleSheet(
            f"QPushButton {{ background-color: {TYRIAN_PURPLE}; color: white;"
            f" border: none; border-radius: 5px; padding: 9px 26px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {BYZANTIUM}; }}"
        )
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
        rotulo = "presupuesto" if self.es_presupuesto else "factura"
        self.setWindowTitle(f"Nuevo {rotulo}")
        self.titulo.setText(f"Nuevo {rotulo}")
        self.boton_guardar.setText(
            "Guardar presupuesto" if self.es_presupuesto else "Emitir factura"
        )
        hoy = hoy_iso()
        self.fecha.setText(a_espanol(hoy))
        self.plazo.setText(a_espanol(
            validez_por_defecto(hoy) if self.es_presupuesto else vencimiento_por_defecto(hoy)
        ))
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
        self.plazo.setText(a_espanol(
            documento.validez if documento.es_presupuesto else documento.vencimiento
        ))
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
        plazo = a_iso(self.plazo.text().strip())
        vencimiento = "" if self.es_presupuesto else plazo
        validez = plazo if self.es_presupuesto else ""

        if self.documento_id:
            guardado = repo_documentos.actualizar(
                self.documento_id, self.fecha.text().strip(), cliente.id, lineas,
                observaciones=observaciones, vencimiento=vencimiento, validez=validez,
            )
            documento_id = self.documento_id if guardado else None
        else:
            documento_id = repo_documentos.crear(
                self.fecha.text().strip(), cliente.id, lineas,
                observaciones=observaciones, tipo=self.tipo,
                vencimiento=vencimiento, validez=validez,
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
