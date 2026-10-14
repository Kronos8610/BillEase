"""
El resumen fiscal: lo facturado por trimestre y lo que queda por cobrar.

Es la pantalla que se abre cuatro veces al año, cuando toca el modelo 303, y
que hasta ahora no existía: había que sumar la columna de la lista a mano, o
abrir las facturas una por una.

No calcula nada por su cuenta. Pide los documentos al repositorio y se los da
a `core/reports.py`, que usa la misma función de IVA que el listado y el PDF.
Si el papel y el resumen discreparan, el resumen no serviría de nada.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import theme
from core.cobros import PENDIENTE, VENCIDA, reparto
from core.fechas import ejercicio_de, hoy_iso
from core.models import COBRADA
from core.money import formatear
from core.reports import resumen_trimestral
from data.repositories import documentos as repo_documentos
from documents.export_csv import exportar_resumen
from ui import iconos
from ui.models.tabla import DERECHA, Columna, ModeloTabla, repartir
from ui.views.listado import boton

TITULO = "Resumen"
APUNTE = "Lo facturado y lo que queda por cobrar, trimestre a trimestre."


def euros(valor):
    return f"{formatear(valor)} €"


COLUMNAS = (
    Columna("Periodo", lambda t: t.etiqueta, orden=lambda t: t.trimestre, peso=3,
            fuerte=True),
    Columna("Facturas", lambda t: str(t.documentos), orden=lambda t: t.documentos,
            alineacion=DERECHA, peso=2),
    Columna("Base imponible", lambda t: euros(t.base), orden=lambda t: t.base,
            alineacion=DERECHA, peso=3),
    Columna("IVA repercutido", lambda t: euros(t.cuota_iva), orden=lambda t: t.cuota_iva,
            alineacion=DERECHA, peso=3,
            pista=lambda t: f"Lo que se declara en el modelo 303 del {t.etiqueta}"),
    Columna("Total facturado", lambda t: euros(t.total), orden=lambda t: t.total,
            alineacion=DERECHA, peso=3, fuerte=True),
    Columna("Cobrado", lambda t: euros(t.cobrado), orden=lambda t: t.cobrado,
            alineacion=DERECHA, peso=3),
    Columna("Pendiente", lambda t: euros(t.pendiente), orden=lambda t: t.pendiente,
            alineacion=DERECHA, peso=3),
)


class Cifra(QFrame):
    """Una cifra grande con su rótulo: lo primero que se mira al entrar."""

    def __init__(self, titulo, pista="", parent=None):
        super().__init__(parent)
        self.setObjectName("Tarjeta")
        columna = QVBoxLayout(self)
        columna.setContentsMargins(18, 14, 18, 16)
        columna.setSpacing(2)

        rotulo = QLabel(titulo)
        rotulo.setObjectName("Etiqueta")
        self.valor = QLabel("—")
        self.valor.setObjectName("Importe")
        self.detalle = QLabel("")
        self.detalle.setObjectName("Apunte")

        columna.addWidget(rotulo)
        columna.addWidget(self.valor)
        columna.addWidget(self.detalle)
        if pista:
            self.setToolTip(pista)

    def poner(self, valor, detalle=""):
        self.valor.setText(valor)
        self.detalle.setText(detalle)


class Resumen(QWidget):
    """Un ejercicio: sus cuatro trimestres, el año y el estado de los cobros."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.categoria = TITULO
        self._iconos_de_accion = {}
        self.resumen = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        centrado = QHBoxLayout()
        contenido = QWidget()
        contenido.setMaximumWidth(theme.ancho_maximo())
        centrado.addStretch(1)
        centrado.addWidget(contenido, 100)
        centrado.addStretch(1)
        raiz.addLayout(centrado)

        columna = QVBoxLayout(contenido)
        columna.setContentsMargins(32, 28, 32, 28)
        columna.setSpacing(16)

        columna.addLayout(self._cabecera())
        columna.addLayout(self._cifras())
        columna.addWidget(self._tabla(), 1)
        columna.addWidget(self._pie())

        QShortcut(QKeySequence("F5"), self, self.cargar)
        self.cargar()

    # ───────────────────────────── montaje ─────────────────────────────

    def _cabecera(self):
        titulo = QLabel(TITULO)
        titulo.setObjectName("Titulo")
        apunte = QLabel(APUNTE)
        apunte.setObjectName("Apunte")

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo)
        textos.addWidget(apunte)

        etiqueta = QLabel("Ejercicio")
        etiqueta.setObjectName("Etiqueta")
        self.ejercicio = QComboBox()
        self.ejercicio.setMinimumWidth(110)
        self.ejercicio.setMinimumHeight(32)
        self.ejercicio.currentIndexChanged.connect(self._pintar)

        self.exportar = boton("Exportar a CSV", "Sutil", "exportar",
                              "Guarda este resumen para la gestoría")
        self._iconos_de_accion[self.exportar] = "exportar"
        self.exportar.clicked.connect(self._exportar)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addLayout(textos)
        fila.addStretch()
        fila.addWidget(etiqueta)
        fila.addWidget(self.ejercicio)
        fila.addWidget(self.exportar)
        return fila

    def _cifras(self):
        self.facturado = Cifra("Facturado", "Base imponible más IVA")
        self.iva = Cifra("IVA repercutido", "Lo que se declara en el modelo 303")
        self.cobrado = Cifra("Cobrado", "Lo que ya ha entrado")
        self.vencido = Cifra("Vencido sin cobrar", "Facturas con el plazo pasado")

        fila = QHBoxLayout()
        fila.setSpacing(12)
        for cifra in (self.facturado, self.iva, self.cobrado, self.vencido):
            fila.addWidget(cifra, 1)
        return fila

    def _tabla(self):
        from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

        self.modelo = ModeloTabla(COLUMNAS, (), self)
        self.vista = QTableView()
        self.vista.setModel(self.modelo)
        self.vista.setAlternatingRowColors(True)
        self.vista.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vista.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vista.setShowGrid(False)
        self.vista.verticalHeader().setVisible(False)
        self.vista.verticalHeader().setDefaultSectionSize(38)
        self.vista.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        cabecera = self.vista.horizontalHeader()
        cabecera.setHighlightSections(False)
        cabecera.setStretchLastSection(True)
        cabecera.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        return self.vista

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        repartir(self.vista)

    def _pie(self):
        self.pie = QLabel("")
        self.pie.setObjectName("Apunte")
        self.pie.setWordWrap(True)
        return self.pie

    def repintar_iconos(self):
        for control, nombre in self._iconos_de_accion.items():
            control.setIcon(iconos.icono(nombre))

    # ───────────────────────────── datos ─────────────────────────────

    def cargar(self):
        """Relee qué ejercicios hay y vuelve a pintar el elegido."""
        anterior = self.ejercicio.currentData()
        anios = repo_documentos.ejercicios() or [ejercicio_de(hoy_iso())]

        self.ejercicio.blockSignals(True)
        self.ejercicio.clear()
        for anio in anios:
            self.ejercicio.addItem(str(anio), anio)
        if anterior in anios:
            self.ejercicio.setCurrentIndex(anios.index(anterior))
        self.ejercicio.blockSignals(False)

        self._pintar()

    def _pintar(self):
        anio = self.ejercicio.currentData()
        if anio is None:
            return

        documentos = repo_documentos.listar_ejercicio(anio)
        self.resumen = resumen_trimestral(documentos, anio)
        anual = self.resumen.anual

        self.modelo.poner(list(self.resumen.trimestres) + [anual])
        repartir(self.vista)

        cuentas = reparto(documentos)
        vencido = cuentas["importes"][VENCIDA]
        cuantas_vencidas = cuentas["documentos"][VENCIDA]

        self.facturado.poner(euros(anual.total), f"{anual.documentos} facturas en {anio}")
        self.iva.poner(euros(anual.cuota_iva), f"sobre {euros(anual.base)} de base")
        self.cobrado.poner(
            euros(cuentas["importes"][COBRADA]),
            f"{cuentas['documentos'][COBRADA]} facturas cobradas",
        )
        self.vencido.poner(
            euros(vencido),
            f"{cuantas_vencidas} factura{'s' if cuantas_vencidas != 1 else ''}"
            f" con el plazo pasado" if cuantas_vencidas else "nada fuera de plazo",
        )

        pendiente = cuentas["importes"][PENDIENTE]
        self.pie.setText(
            f"Los presupuestos no entran: una oferta no es un ingreso. "
            f"Quedan {euros(pendiente)} pendientes dentro de plazo y "
            f"{euros(vencido)} fuera de plazo."
        )

    # ───────────────────────────── acciones ─────────────────────────────

    def _exportar(self):
        if self.resumen is None:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar resumen", f"resumen-{self.resumen.ejercicio}.csv",
            "CSV (*.csv)",
        )
        if not ruta:
            return
        try:
            exportar_resumen(self.resumen, ruta)
        except OSError as e:
            QMessageBox.critical(self, "No se pudo exportar", str(e))
            return
        QMessageBox.information(
            self, "Resumen exportado",
            f"Los cuatro trimestres de {self.resumen.ejercicio} y el año completo "
            f"están en {ruta}.",
        )

    def nuevo_elemento(self):
        """`Ctrl+N` aquí no crea nada: esta pantalla solo mira."""
        return None
