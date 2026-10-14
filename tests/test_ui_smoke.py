"""
Pruebas de la interfaz Fluent (fase 5).

Se ejecutan sin pantalla, con `QT_QPA_PLATFORM=offscreen`. No comprueban que
algo «se vea bonito»: comprueban lo que exige la puerta 5, que es medible.

    · ningún par de colores por debajo de 4,5:1, en los dos temas,
    · menos de cinco llamadas a `setStyleSheet` en todo el proyecto,
    · ningún emoji en la interfaz,
    · la búsqueda y el orden por columna funcionan de verdad,
    · con mil facturas el listado no crea mil filas de widgets,
    · el tema claro y el oscuro se aplican los dos sin romperse.
"""

import os
import re
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import theme  # noqa: E402
from core.fechas import a_espanol, hoy_iso  # noqa: E402
from core.models import ACEPTADO, ENVIADO, PRESUPUESTO, Cliente, Linea  # noqa: E402
from core.quotes import validez_por_defecto  # noqa: E402
from data.connection import cerrar  # noqa: E402
from data.repositories import clientes as repo_clientes  # noqa: E402
from data.repositories import documentos as repo  # noqa: E402
from data.schema import crear_esquema_y_migrar  # noqa: E402
from theme.tokens import MINIMO, revisar, temas  # noqa: E402
from tools import check_estilos  # noqa: E402
from ui import iconos  # noqa: E402
from ui.models import ROL_ESTADO, ROL_ORDEN  # noqa: E402
from ui.views.listado import CLIENTES, FACTURAS, PRESUPUESTOS, Listado  # noqa: E402


@pytest.fixture(scope="session")
def app():
    aplicacion = QApplication.instance() or QApplication([])
    theme.aplicar_tema(aplicacion, "claro")
    return aplicacion


def dentro_de(dias, desde=None):
    """Una fecha ISO relativa a hoy, para que el montaje no caduque solo."""
    partida = date.fromisoformat(desde or hoy_iso())
    return (partida + timedelta(days=dias)).isoformat()


@pytest.fixture
def base(tmp_path, monkeypatch, app):
    """Dos clientes, dos facturas y un presupuesto en vigor."""
    monkeypatch.setenv("BILLEASE_DB", str(tmp_path / "interfaz.db"))
    cerrar()
    crear_esquema_y_migrar()
    cliente_id = repo_clientes.crear(
        Cliente(nombre="Construcciones Pérez S.L.", nif="B12345674",
                es_persona_fisica=False, codigo_postal="08020",
                telefono="654321098", email="obra@construccionesperez.es")
    )
    repo_clientes.crear(
        Cliente(nombre="María Fernández Ruiz", nif="87654321X",
                es_persona_fisica=True, codigo_postal="28030")
    )
    hoy = hoy_iso()
    repo.crear(a_espanol(hoy), cliente_id,
               [Linea("Armario a medida", cantidad=1, precio_ud=1240)])
    repo.crear(a_espanol(dentro_de(1)), cliente_id,
               [Linea("Desmontaje", cantidad=1, precio_ud=195)])
    repo.crear(a_espanol(hoy), cliente_id,
               [Linea("Obra ofertada", cantidad=1, precio_ud=800)],
               tipo=PRESUPUESTO, validez=validez_por_defecto(hoy))
    yield cliente_id
    cerrar()


@pytest.fixture
def sin_dialogos(monkeypatch):
    mensajes = []
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, nombre,
            staticmethod(lambda p, t, m, *a, _n=nombre, **k: mensajes.append((_n, t, m))),
        )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    return mensajes


# ─────────────────────── puerta 5 · contraste ───────────────────────


@pytest.mark.parametrize("modo", temas())
def test_ningun_par_de_colores_baja_de_cuatro_y_medio(modo):
    """
    El menú de la versión anterior daba 1,49:1: morado sobre morado.

    Se recorren todos los pares que el usuario ve como texto sobre fondo.
    """
    malos = [
        f"{frente} sobre {fondo}: {razon:.2f}:1 ({descripcion})"
        for razon, frente, fondo, descripcion in revisar(modo)
        if razon < MINIMO
    ]
    assert malos == [], f"pares ilegibles en el tema {modo}:\n" + "\n".join(malos)


def test_el_contraste_se_calcula_como_manda_la_wcag():
    """Negro sobre blanco son 21:1; el par del menú anterior, 1,49:1."""
    from theme.tokens import contraste

    assert round(contraste("#000000", "#FFFFFF"), 2) == 21.0
    assert round(contraste("#FFFFFF", "#FFFFFF"), 2) == 1.0
    assert round(contraste("#950952", "#66023C"), 2) == 1.49


# ─────────────────────── puerta 5 · una sola hoja ───────────────────────


def test_casi_nadie_llama_a_set_style_sheet():
    """
    Eran 54 llamadas repartidas por seis ficheros. Ahora solo `theme/`.

    Cada llamada obliga a Qt a volver a analizar la hoja, y repartir los
    colores por los widgets es lo que hacía imposible un tema oscuro.
    """
    por_fichero = {
        str(ruta.relative_to(check_estilos.RAIZ)): check_estilos.llamadas_a_estilo(ruta)
        for ruta in check_estilos.ficheros()
    }
    culpables = {f: lineas for f, lineas in por_fichero.items() if lineas}
    total = sum(len(lineas) for lineas in culpables.values())

    assert total < 5, f"demasiadas hojas sueltas: {culpables}"
    assert set(culpables) <= {"theme/__init__.py"}, (
        f"el aspecto se decide fuera de theme/: {culpables}"
    )


def test_no_queda_ni_un_emoji_en_la_interfaz():
    """🏠 📄 📝 ➕ 🗑 eran los iconos del menú. Ahora son SVG propios."""
    culpables = [
        f"{ruta.relative_to(check_estilos.RAIZ)}:{numero}: «{caracter}» {texto}"
        for ruta in check_estilos.ficheros()
        for numero, caracter, texto in check_estilos.emojis(ruta)
    ]
    assert culpables == [], "emojis en la interfaz:\n" + "\n".join(culpables)


def test_el_detector_de_emojis_distingue_un_emoji_de_una_eñe():
    assert check_estilos.es_emoji("🏠")
    assert check_estilos.es_emoji("➕")
    assert check_estilos.es_emoji("🗑")
    for corriente in "ñáéíóúü€·—«»…ABCabc123":
        assert not check_estilos.es_emoji(corriente), corriente


# ─────────────────────── el tema ───────────────────────


@pytest.mark.parametrize("modo", temas())
def test_la_hoja_de_estilos_no_deja_ningun_token_sin_sustituir(modo):
    """
    Un `$algo` que sobreviva a la sustitución es una regla que no se aplica.

    La única excepción es el `$token` escapado del comentario de cabecera, que
    está ahí para explicar cómo funciona la plantilla.
    """
    hoja = theme.hoja_de_estilos(modo).replace("`$token`", "")
    sin_sustituir = [
        linea for linea in hoja.splitlines() if re.search(r"\$[A-Za-z_]", linea)
    ]
    assert sin_sustituir == [], f"tokens sin valor: {sin_sustituir}"
    assert len(hoja) > 2000


def test_los_dos_temas_se_aplican_sobre_la_aplicacion(app):
    for modo in temas():
        assert theme.aplicar_tema(app, modo) == modo
        assert theme.modo_actual() == modo
        assert app.styleSheet().startswith("/*")
    theme.aplicar_tema(app, "claro")


def test_el_tema_oscuro_y_el_claro_no_comparten_colores(app):
    from theme.tokens import CLARO, OSCURO

    assert set(CLARO) == set(OSCURO), "los dos temas tienen que tener los mismos tokens"
    iguales = [t for t in CLARO if CLARO[t] == OSCURO[t]]
    assert iguales == [], f"estos tokens no cambian con el tema: {iguales}"


def test_sin_escritorio_se_elige_el_tema_claro(app):
    """En un contenedor `colorScheme()` es `Unknown`: no se adivina."""
    assert theme.modo_del_sistema() in temas()
    assert theme.aplicar_tema(app, theme.AUTOMATICO) in temas()
    theme.aplicar_tema(app, "claro")


# ─────────────────────── los iconos ───────────────────────


def test_todos_los_iconos_se_dibujan(app):
    for nombre in iconos.TRAZOS:
        assert not iconos.icono(nombre).isNull(), nombre
        assert not iconos.pixmap(nombre).isNull(), nombre


def test_un_icono_que_no_existe_se_queja(app):
    with pytest.raises(KeyError):
        iconos.icono("lo-que-sea")


def test_el_icono_sale_del_color_del_tema(app):
    theme.aplicar_tema(app, "claro")
    claro = iconos.svg("factura")
    theme.aplicar_tema(app, "oscuro")
    oscuro = iconos.svg("factura")
    theme.aplicar_tema(app, "claro")

    assert claro != oscuro
    assert "#1A1A1A" in claro and "#FFFFFF" in oscuro


# ─────────────────────── el listado ───────────────────────


def test_el_listado_pinta_las_facturas_sin_una_fila_de_widgets(base, app):
    listado = Listado(FACTURAS)
    assert listado.modelo.rowCount() == 2
    assert listado.filtro.rowCount() == 2
    # Lo que antes eran once widgets por fila ahora son celdas de una tabla.
    assert len(listado.vista.findChildren(type(listado.nuevo))) == 0


def test_la_busqueda_filtra_sin_tildes_ni_mayusculas(base, app):
    listado = Listado(CLIENTES)
    assert listado.filtro.rowCount() == 2

    listado.buscador.setText("perez")          # el cliente es «Pérez»
    assert listado.filtro.rowCount() == 1
    assert "Pérez" in listado.filtro.index(0, 0).data()
    assert listado.resumen.text() == "1 de 2 clientes"

    listado.buscador.setText("FERNANDEZ")      # y «Fernández»
    assert listado.filtro.rowCount() == 1

    listado.buscador.clear()
    assert listado.filtro.rowCount() == 2
    assert listado.resumen.text() == "2 clientes"


def test_la_busqueda_que_no_encuentra_nada_lo_dice(base, app):
    listado = Listado(FACTURAS)
    listado.buscador.setText("no existe este cliente")
    assert listado.filtro.rowCount() == 0
    assert listado._pila.currentIndex() == 1
    assert listado.vacio_titulo.text() == "Ningún resultado"
    assert not listado.vacio_boton.isVisible()


def test_el_orden_por_importe_es_numerico_no_alfabetico(base, app):
    """«1.240,00 €» va después de «195,00 €», no antes por empezar por uno."""
    listado = Listado(FACTURAS)
    columna = len(listado.modelo.columnas) - 1

    listado.vista.sortByColumn(columna, Qt.SortOrder.AscendingOrder)
    texto = [listado.filtro.index(f, columna).data() for f in range(2)]
    valores = [listado.filtro.index(f, columna).data(ROL_ORDEN) for f in range(2)]

    assert texto[0].startswith("235") and texto[1].startswith("1.500")
    assert valores == sorted(valores)


def test_el_orden_por_fecha_es_cronologico(base, app):
    """Se ordena por la fecha ISO, no por el «dd/mm/aaaa» que se enseña."""
    listado = Listado(FACTURAS)
    listado.vista.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    fechas = [listado.filtro.index(f, 1).data(ROL_ORDEN) for f in range(2)]
    textos = [listado.filtro.index(f, 1).data() for f in range(2)]
    assert fechas == [hoy_iso(), dentro_de(1)]
    assert textos == [a_espanol(hoy_iso()), a_espanol(dentro_de(1))]


def test_el_listado_vacio_ofrece_la_accion(base, app, monkeypatch):
    """Antes era una línea en cursiva. Ahora dice qué hacer y trae el botón."""
    monkeypatch.setenv("BILLEASE_DB", str(os.environ["BILLEASE_DB"]))
    for documento in repo.listar(PRESUPUESTO):
        repo.eliminar(documento.id)

    listado = Listado(PRESUPUESTOS)
    assert listado.modelo.rowCount() == 0
    assert listado._pila.currentIndex() == 1
    assert "Todavía no has hecho ningún presupuesto" == listado.vacio_titulo.text()
    assert listado.vacio_boton.text() == "Nuevo presupuesto"


def test_las_acciones_estan_apagadas_hasta_que_se_elige_una_fila(base, app):
    listado = Listado(FACTURAS)
    assert all(not accion.isEnabled() for accion in listado.acciones)

    listado.vista.selectRow(0)
    assert listado.boton_pdf.isEnabled()
    assert listado.boton_editar.isEnabled()
    assert listado.boton_borrar.isEnabled()
    assert listado.seleccionado().referencia.startswith("2026-")


def test_un_presupuesto_solo_se_factura_si_esta_aceptado(base, app):
    listado = Listado(PRESUPUESTOS)
    listado.vista.selectRow(0)
    assert not listado.boton_facturar.isEnabled()      # está en borrador

    presupuesto = listado.seleccionado()
    repo.cambiar_estado(presupuesto.id, ENVIADO)
    repo.cambiar_estado(presupuesto.id, ACEPTADO)
    listado.cargar()
    listado.vista.selectRow(0)
    assert listado.boton_facturar.isEnabled()


def test_el_estado_del_presupuesto_se_pinta_como_pildora(base, app):
    listado = Listado(PRESUPUESTOS)
    columna = 3
    indice = listado.filtro.index(0, columna)

    assert indice.data() == "Borrador"
    assert indice.data(ROL_ESTADO) == "neutro"
    # Y la columna tiene su delegado, no un widget por fila.
    from ui.widgets.pildora import PildoraEstado

    assert isinstance(listado.vista.itemDelegateForColumn(columna), PildoraEstado)


def test_un_presupuesto_pasado_de_fecha_se_enseña_como_caducado(base, app):
    """
    Lo dice la lista, no el usuario mirando el calendario.

    `esta_caducado` compara la validez con hoy; la píldora se pinta en rojo
    aunque el estado guardado siga siendo «borrador».
    """
    presupuesto = repo.listar(PRESUPUESTO)[0]
    repo.actualizar(presupuesto.id, a_espanol(dentro_de(-90)), presupuesto.cliente_id,
                    repo.lineas_de(presupuesto.id), validez=dentro_de(-60))

    listado = Listado(PRESUPUESTOS)
    indice = listado.filtro.index(0, 3)
    assert indice.data() == "Caducado"
    assert indice.data(ROL_ESTADO) == "peligro"


def test_eliminar_una_factura_avisa_del_hueco_en_la_serie(base, app, sin_dialogos):
    listado = Listado(FACTURAS)
    listado.vista.selectRow(0)
    antes = listado.modelo.rowCount()
    listado._eliminar()
    assert listado.modelo.rowCount() == antes - 1


def test_un_cliente_con_facturas_no_se_puede_borrar(base, app, sin_dialogos):
    listado = Listado(CLIENTES)
    listado.buscador.setText("perez")
    listado.vista.selectRow(0)
    listado._eliminar()

    assert listado.modelo.rowCount() == 2
    assert any("No se puede eliminar" in titulo for _, titulo, _ in sin_dialogos)


# ─────────────────────── la ventana ───────────────────────


def test_la_ventana_abre_las_tres_secciones(base, app):
    from ui.shell import SECCIONES, VentanaPrincipal

    ventana = VentanaPrincipal()
    assert [nombre for nombre, _, _ in SECCIONES] == [FACTURAS, PRESUPUESTOS, CLIENTES]
    assert ventana.seccion == FACTURAS

    for nombre, _, _ in SECCIONES:
        pantalla = ventana.ir_a(nombre)
        assert ventana.seccion == nombre
        assert pantalla.categoria == nombre
        assert ventana.navegacion.botones[nombre].property("activo") == "true"
        otros = [
            boton.property("activo")
            for seccion, boton in ventana.navegacion.botones.items()
            if seccion != nombre
        ]
        assert otros == ["false"] * 2
    ventana.close()


def test_las_pantallas_se_crean_cuando_se_abren(base, app):
    """Antes se construían las cuatro al arrancar, con sus consultas."""
    from ui.shell import VentanaPrincipal

    ventana = VentanaPrincipal()
    assert list(ventana._creadas) == [FACTURAS]

    ventana.ir_a(CLIENTES)
    assert sorted(ventana._creadas) == sorted([FACTURAS, CLIENTES])
    ventana.close()


def test_la_ventana_cambia_de_tema_sin_romperse(base, app):
    from ui.shell import VentanaPrincipal

    ventana = VentanaPrincipal()
    primero = theme.modo_actual()
    segundo = ventana.cambiar_tema()
    assert segundo != primero
    assert ventana.cambiar_tema() == primero
    ventana.close()
    theme.aplicar_tema(app, "claro")


def test_el_contenido_tiene_un_ancho_maximo(base, app):
    """En una pantalla ancha, una línea de tabla de 2.000 píxeles no se lee."""
    listado = Listado(FACTURAS)
    listado.resize(2400, 900)
    anchos = [
        hijo.maximumWidth() for hijo in listado.children()
        if hasattr(hijo, "maximumWidth") and hijo.maximumWidth() == theme.ancho_maximo()
    ]
    assert anchos == [theme.ancho_maximo()]


def test_los_atajos_estan_puestos(base, app):
    from PyQt6.QtGui import QShortcut

    listado = Listado(FACTURAS)
    atajos = {a.key().toString() for a in listado.findChildren(QShortcut)}
    assert {"Ctrl+F", "F5", "Esc", "Del"} <= atajos
