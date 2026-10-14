"""
El tema de la aplicación: una hoja de estilos y una llamada.

    from theme import aplicar_tema
    aplicar_tema(app)            # sigue al tema de Windows y se entera si cambia

`app.qss` se lee una vez, se le sustituyen los `$token` por los colores de
`theme/tokens.py` y se aplica a la aplicación entera. Qt vuelve a analizar la
hoja cada vez que alguien llama a `setStyleSheet`; la versión anterior la
llamaba 54 veces, una por widget, y repartía los colores a mano por seis
ficheros.

Este módulo no importa Qt al cargarse —lo hace dentro de cada función— para
que `theme.tokens` se pueda leer desde una herramienta de línea de órdenes o
desde el generador de PDF sin arrastrar una pantalla detrás.
"""

import sys
from pathlib import Path
from string import Template

from theme.tokens import CLARO_ID, MEDIDAS, OSCURO_ID, paleta


def _hoja():
    """
    Dónde está `app.qss`, también dentro del ejecutable.

    PyInstaller descomprime los ficheros de datos en una carpeta temporal y
    deja su ruta en `sys._MEIPASS`. Sin esto, el programa empaquetado
    arrancaría sin estilos: todo gris del sistema.
    """
    empaquetado = getattr(sys, "_MEIPASS", None)
    if empaquetado:
        dentro = Path(empaquetado) / "theme" / "app.qss"
        if dentro.exists():
            return dentro
    return Path(__file__).with_name("app.qss")


HOJA = _hoja()

AUTOMATICO = "auto"

_estado = {"modo": AUTOMATICO, "resuelto": CLARO_ID, "conectado": False}


# ─────────────────────────── hoja de estilos ───────────────────────────


def hoja_de_estilos(modo=CLARO_ID):
    """La hoja completa, con los colores del tema ya sustituidos."""
    plantilla = Template(HOJA.read_text(encoding="utf-8"))
    return plantilla.substitute(paleta(modo))


# ─────────────────────────── tema del sistema ───────────────────────────


def modo_del_sistema():
    """
    Qué tema tiene puesto Windows. Si no se puede saber, el claro.

    Qt 6.5 expone el ajuste del sistema en `styleHints().colorScheme()`. En un
    contenedor sin escritorio devuelve `Unknown`, y entonces se elige el claro
    en vez de adivinar.
    """
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        esquema = QGuiApplication.styleHints().colorScheme()
        if esquema == Qt.ColorScheme.Dark:
            return OSCURO_ID
        if esquema == Qt.ColorScheme.Light:
            return CLARO_ID
    except Exception:          # noqa: BLE001 — una plataforma sin escritorio
        pass
    return CLARO_ID


def modo_actual():
    """El tema que se está pintando ahora mismo: `claro` u `oscuro`."""
    return _estado["resuelto"]


def es_oscuro():
    return _estado["resuelto"] == OSCURO_ID


def color(nombre):
    """Un token de color del tema en uso. Lo usan los iconos y las píldoras."""
    return paleta(_estado["resuelto"])[nombre]


def ancho_maximo():
    return MEDIDAS["ancho_maximo"]


# ─────────────────────────────── aplicar ───────────────────────────────


def aplicar_tema(app, modo=AUTOMATICO):
    """
    Viste la aplicación entera.

    `modo` puede ser `claro`, `oscuro` o `auto`. En `auto` se sigue al tema de
    Windows y se vuelve a aplicar solo si el usuario lo cambia mientras la
    aplicación está abierta.
    """
    _estado["modo"] = modo
    _estado["resuelto"] = modo_del_sistema() if modo == AUTOMATICO else modo

    app.setStyleSheet(hoja_de_estilos(_estado["resuelto"]))

    if modo == AUTOMATICO and not _estado["conectado"]:
        _seguir_al_sistema(app)
    return _estado["resuelto"]


def _seguir_al_sistema(app):
    """Se vuelve a vestir la aplicación cuando Windows cambia de tema."""
    try:
        from PyQt6.QtGui import QGuiApplication

        pistas = QGuiApplication.styleHints()
        pistas.colorSchemeChanged.connect(lambda _: aplicar_tema(app, AUTOMATICO))
        _estado["conectado"] = True
    except (AttributeError, TypeError):
        # Qt anterior a 6.5: se queda con el tema que hubiera al arrancar.
        pass


def alternar(app):
    """Cambia de claro a oscuro y al revés. Para ver los dos de un vistazo."""
    return aplicar_tema(app, CLARO_ID if es_oscuro() else OSCURO_ID)


# ──────────────────────────── Mica en Windows ────────────────────────────


def activar_mica(ventana):
    """
    Pide a Windows 11 el fondo Mica y la barra de título del color del tema.

    Es puramente cosmético y fuera de Windows no hace nada: si la llamada no
    existe o falla, la ventana se queda con su fondo liso.
    """
    import sys

    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes

        identificador = ctypes.c_void_p(int(ventana.winId()))
        dwm = ctypes.windll.dwmapi

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20, DWMWA_SYSTEMBACKDROP_TYPE = 38,
        # DWMSBT_MAINWINDOW (Mica) = 2.
        oscuro = ctypes.c_int(1 if es_oscuro() else 0)
        dwm.DwmSetWindowAttribute(identificador, 20, ctypes.byref(oscuro), 4)

        material = ctypes.c_int(2)
        resultado = dwm.DwmSetWindowAttribute(identificador, 38, ctypes.byref(material), 4)
        return resultado == 0
    except Exception:          # noqa: BLE001 — Windows 10 o una build sin Mica
        return False
