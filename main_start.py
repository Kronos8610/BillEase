"""
Punto de entrada de BillEase.

Antes decidía qué pantalla abrir comprobando si existía `BillEase.db` en el
directorio de trabajo. Como la ruta era relativa, arrancar la aplicación desde
otra carpeta creaba una base nueva y vacía sin avisar, y los datos «se
perdían».

Ahora la base vive en la carpeta de datos del usuario (`config.py`), se
recupera automáticamente la que hubiera quedado junto al programa, y se le
aplican las migraciones pendientes antes de abrir nada.

Y antes de todo eso se pide la contraseña, que además es la que descifra los
datos (`data/caja.py`). El orden importa: no se puede migrar lo que todavía
no se ha podido descifrar, así que las migraciones se aplican justo después
de acertar la contraseña y no al arrancar.
"""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

import theme
from config import recuperar_base_antigua, ruta_base_datos
from data.connection import conexion


def preparar_base():
    """
    Dice si ya había datos y dónde están.

    Devuelve `(existia, ruta)`. Si no existía, quien llama abre el formulario
    de configuración inicial. Ya no migra aquí: con la base cifrada no se
    puede tocar nada antes de la contraseña.
    """
    recuperada = recuperar_base_antigua()
    ruta = ruta_base_datos()
    return (ruta.exists() or recuperada is not None), ruta


def hace_falta_contrasena(ruta):
    """
    ¿Hay que pedir la contraseña para abrir esta base?

    Siempre que esté cifrada, y también cuando esté en claro pero haya alguien
    dado de alta: un cerrojo de cortesía es poco, pero es más que nada.
    """
    from data.connection import esta_cifrada

    if esta_cifrada(ruta):
        return True
    try:
        from data.repositories import autonomo as repo_autonomo

        return repo_autonomo.hay_autonomo()
    except Exception:          # noqa: BLE001 — base a medio hacer
        return False


def poner_al_dia(ruta):
    """Aplica las migraciones pendientes. Después de abrir, nunca antes."""
    from data.migrations import migrar

    migrar(conexion(), ruta=ruta)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BillEase")
    # Una sola hoja de estilos para toda la aplicación, del color del tema que
    # tenga puesto Windows (`theme/`).
    theme.aplicar_tema(app)

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

    abiertas = {}          # sin esto, Python se lleva por delante la ventana

    def abrir_principal():
        """Lo que pasa cuando ya se puede leer la base."""
        from ui.shell import VentanaPrincipal

        poner_al_dia(ruta)
        principal = VentanaPrincipal()
        abiertas["principal"] = principal
        principal.show()

    if not existia:
        print(f"Primera ejecución. La base se creará cifrada en: {ruta}")
        from ui.views.registro import VentanaRegistro

        ventana = VentanaRegistro(configuracion_inicial=True)
    elif hace_falta_contrasena(ruta):
        from data.connection import cerrar, esta_cifrada
        from ui.views.acceso import VentanaAcceso

        print(f"Base de datos: {ruta}"
              f"{' (cifrada)' if esta_cifrada(ruta) else ' (sin cifrar)'}")
        cerrar()               # no se queda nada abierto mientras se pregunta
        ventana = VentanaAcceso(ruta, al_entrar=abrir_principal)
    else:
        print(f"Base de datos: {ruta}")
        from ui.shell import VentanaPrincipal

        poner_al_dia(ruta)
        ventana = VentanaPrincipal()

    abiertas["primera"] = ventana
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
