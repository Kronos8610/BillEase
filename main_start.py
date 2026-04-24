import os
import sys

from PyQt6.QtWidgets import QApplication
from ui.aplication import MainWindow
from ui.login_ui import RegisterWindow
    
def main():
  
    # Verificar si la base de datos existe
    if not os.path.exists("BillEase.db"):
        print("La base de datos no existe. Se mostrará el formulario de registro inicial...")
        app = QApplication(sys.argv)
        register_window = RegisterWindow(initial_setup=True)
        register_window.show()
        sys.exit(app.exec())
    else:
        print("La base de datos ya existe. Iniciando aplicación principal...")
        app = QApplication(sys.argv)
        main_window = MainWindow()
        main_window.show()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()