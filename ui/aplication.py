import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMainWindow, QHBoxLayout,
    QStackedWidget, QFrame, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from core.models import FACTURA, PRESUPUESTO
from ui.homePage import HomePage
from ui.crearCliente import CrearCliente
from utils.globals import (
    TYRIAN_PURPLE, BYZANTIUM, LAVENDER_PINK, CHAMPAGNE_PINK, ALMOND,
    TITLE_FONT, SUBTITLE_FONT, BODY_FONT
)

class SideMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet(f"""
            background-color: {TYRIAN_PURPLE};
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(5)

        # Título de la aplicación
        title = QLabel("BillEase")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {CHAMPAGNE_PINK}; margin: 10px 0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separador para la estructura visual
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {BYZANTIUM}; max-height: 1px;")
        layout.addWidget(separator)
        layout.addSpacing(15)

        # Ya no hay «Crear Servicio»: los conceptos se escriben en el propio
        # documento, no se eligen de un catálogo.
        self.buttons = []
        menu_items = [
            {"text": "Documentos", "icon": "🏠"},
            {"text": "Nueva factura", "icon": "📄"},
            {"text": "Nuevo presupuesto", "icon": "📝"},
            {"text": "Nuevo cliente", "icon": "➕"},
        ]
        
        for item in menu_items:
            btn = QPushButton(f" {item['icon']} {item['text']}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(BODY_FONT)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {BYZANTIUM};
                    border: none;
                    border-radius: 4px;
                    padding: 10px 15px;
                    text-align: left;
                    margin: 2px 10px;
                }}
                QPushButton:hover {{
                    background-color: {BYZANTIUM};
                    color: white;
                }}
                QPushButton:pressed {{
                    background-color: #84084A;
                }}
            """)
            btn.setMinimumHeight(40)
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BillEase")
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Side menu
        self.side_menu = SideMenu()
        main_layout.addWidget(self.side_menu)

        # Área principal 
        content_frame = QFrame()
        content_frame.setStyleSheet(f"background-color: {CHAMPAGNE_PINK};")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.pages = QStackedWidget()
        self.home_page = HomePage()
        self.new_page = CrearCliente()
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.new_page)
        content_layout.addWidget(self.pages)

        main_layout.addWidget(content_frame)

        self.side_menu.buttons[0].clicked.connect(self.ir_a_documentos)
        self.side_menu.buttons[1].clicked.connect(lambda: self.nuevo_documento(FACTURA))
        self.side_menu.buttons[2].clicked.connect(lambda: self.nuevo_documento(PRESUPUESTO))
        self.side_menu.buttons[3].clicked.connect(self.ir_a_crear_cliente)

    def ir_a_documentos(self):
        self.pages.setCurrentWidget(self.home_page)
        self.home_page.cargar_datos()

    def ir_a_crear_cliente(self):
        self.pages.setCurrentWidget(self.new_page)

    def nuevo_documento(self, tipo):
        """
        Abre el editor. Es el mismo para facturas y presupuestos: cambian la
        cabecera, la serie y el plazo, no el formulario.
        """
        from ui.views.documento_editor import DocumentoEditor

        self.pages.setCurrentWidget(self.home_page)
        if DocumentoEditor(tipo=tipo, parent=self).exec():
            self.home_page.categoria_combo.setCurrentText(
                "Presupuestos" if tipo == PRESUPUESTO else "Facturas"
            )
            self.home_page.cargar_datos()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())