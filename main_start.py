"""
Punto de entrada de BillEase.

Antes decidía qué pantalla abrir comprobando si existía `BillEase.db` en el
directorio de trabajo. Como la ruta era relativa, arrancar la aplicación desde
otra carpeta creaba una base nueva y vacía sin avisar, y los datos «se
perdían».

Ahora la base vive en la carpeta de datos del usuario (`config.py`), se
recupera automáticamente la que hubiera quedado junto al programa, y se le
aplican las migraciones pendientes antes de abrir nada.
"""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from config import recuperar_base_antigua, ruta_base_datos
from data.connection import conexion


def preparar_base():
    """
    Deja la base lista para usarse y dice si ya tenía datos.

    Devuelve `(existia, ruta)`. Si no existía, quien llama abre el formulario
    de configuración inicial.
    """
    recuperada = recuperar_base_antigua()
    ruta = ruta_base_datos()
    existia = ruta.exists() or recuperada is not None

    if existia:
        from data.migrations import migrar
        migrar(conexion(), ruta=ruta)

    return existia, ruta


def main():
    app = QApplication(sys.argv)

    try:
        existia, ruta = preparar_base()
    except Exception as e:
        QMessageBox.critical(
            None,
            "No se pudo abrir la base de datos",
            f"BillEase no ha podido preparar sus datos.\n\n{e}\n\n"
            "Se ha guardado una copia de seguridad junto al fichero original.",
        )
        return 1

    if existia:
        print(f"Base de datos: {ruta}")
        from ui.aplication import MainWindow
        ventana = MainWindow()
    else:
        print(f"Primera ejecución. La base se creará en: {ruta}")
        from ui.login_ui import RegisterWindow
        ventana = RegisterWindow(initial_setup=True)

    ventana.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
