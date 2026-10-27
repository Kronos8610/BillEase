"""
Los colores y las medidas de la interfaz, en un solo sitio y sin dependencias.

Este módulo no importa Qt a propósito: lo leen la interfaz, la hoja de estilos
y las herramientas de comprobación, y ninguna de ellas debería necesitar una
pantalla para saber de qué color es un botón.

Antes los colores estaban en `utils/globals.py` —cinco constantes con nombre de
catálogo de pinturas— y repartidos a mano por 54 llamadas a `setStyleSheet`.
Dos de aquellos pares no se podían leer: el menú lateral escribía en morado
sobre morado, con un contraste de 1,49:1 cuando el mínimo legible es 4,5:1
(defecto 13).

Cada token existe en los dos temas. El claro y el oscuro no son dos diseños:
son la misma rejilla con otra paleta.
"""

# ─────────────────────────────── paletas ───────────────────────────────

CLARO = {
    # superficies
    "fondo":            "#F3F3F3",   # el material de fondo (Mica en Windows 11)
    "capa":             "#FFFFFF",   # tarjetas y tablas
    "capa_alterna":     "#FAFAFA",   # filas pares
    "capa_sutil":       "#F6F6F6",   # cabeceras y campos de solo lectura
    "realce":           "#EFEFEF",   # fila señalada por el ratón
    "seleccion":        "#E8F1FB",   # fila seleccionada
    # trazos
    "borde":            "#E5E5E5",
    "borde_fuerte":     "#D1D1D1",
    # texto
    "texto":            "#1A1A1A",
    "texto_suave":      "#5C5C5C",
    "texto_sobre_acento": "#FFFFFF",
    # acento
    "acento":           "#0F6CBD",
    "acento_hover":     "#115EA3",
    "acento_pulsado":   "#0C4A7D",
    # estados
    "ok":               "#0B6A0B",
    "aviso":            "#7A4D00",
    "peligro":          "#A4262C",
    "neutro":           "#4A4A4A",
    # píldoras de estado (fondo tenue + texto del propio estado)
    "ok_tenue":         "#DFF6DD",
    "aviso_tenue":      "#FFF4CE",
    "peligro_tenue":    "#FDE7E9",
    "neutro_tenue":     "#EDEDED",
    "acento_tenue":     "#E8F1FB",
}

OSCURO = {
    "fondo":            "#202020",
    "capa":             "#2B2B2B",
    "capa_alterna":     "#303030",
    "capa_sutil":       "#333333",
    "realce":           "#383838",
    "seleccion":        "#16324A",
    "borde":            "#3A3A3A",
    "borde_fuerte":     "#4A4A4A",
    "texto":            "#FFFFFF",
    "texto_suave":      "#C5C5C5",
    "texto_sobre_acento": "#11304A",
    "acento":           "#60CDFF",
    "acento_hover":     "#8ADCFF",
    "acento_pulsado":   "#3AA0D1",
    "ok":               "#6CCB5F",
    "aviso":            "#FCE100",
    "peligro":          "#FF99A4",
    "neutro":           "#CFCFCF",
    "ok_tenue":         "#123A12",
    "aviso_tenue":      "#433519",
    "peligro_tenue":    "#442726",
    "neutro_tenue":     "#383838",
    "acento_tenue":     "#16324A",
}

# Medidas. Son las mismas en los dos temas: lo que cambia es el color.
MEDIDAS = {
    "radio":            "6px",
    "radio_grande":     "10px",
    "alto_control":     "32px",
    "alto_fila":        "38px",
    "ancho_lateral":    "220px",
    "ancho_maximo":     1280,      # el contenido no se estira sin fin
    "ancho_formulario": 980,       # un formulario más ancho no se lee mejor
    # La ventana de crear cliente se abre grande y con el cuerpo pequeño se
    # leía con lupa. Estas dos medidas son las de su ropa de domingo.
    "alto_control_grande": "42px",
    "cuerpo_grande":       "15px",
    "tipografia":       "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif",
    "cuerpo":           "13px",
    "pequeno":          "12px",
    "titulo":           "26px",
    "subtitulo":        "16px",
}

CLARO_ID = "claro"
OSCURO_ID = "oscuro"

_PALETAS = {CLARO_ID: CLARO, OSCURO_ID: OSCURO}


def paleta(modo=CLARO_ID):
    """La paleta del tema pedido, ya combinada con las medidas."""
    if modo not in _PALETAS:
        raise ValueError(f"tema desconocido: {modo!r}; usa {CLARO_ID!r} u {OSCURO_ID!r}")
    valores = dict(_PALETAS[modo])
    valores.update({k: v for k, v in MEDIDAS.items() if isinstance(v, str)})
    return valores


def temas():
    return (CLARO_ID, OSCURO_ID)


# ─────────────────────────────── contraste ───────────────────────────────


def _canal(valor):
    """Un canal sRGB linealizado, según la fórmula de la WCAG 2.1."""
    c = valor / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(color):
    """Luminancia relativa de un `#rrggbb`."""
    texto = color.lstrip("#")
    r, g, b = (int(texto[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(uno, otro):
    """
    La razón de contraste entre dos colores, de 1:1 a 21:1.

    La WCAG pide 4,5:1 para texto normal. El menú de la versión anterior daba
    1,49:1.
    """
    a, b = luminancia(uno), luminancia(otro)
    claro, oscuro = max(a, b), min(a, b)
    return (claro + 0.05) / (oscuro + 0.05)


MINIMO = 4.5

# Todos los pares que el usuario llega a ver como «texto sobre fondo». La
# comprobación los recorre en los dos temas: `tools/check_contraste.py`.
PARES = (
    ("texto", "capa", "texto principal sobre la tarjeta"),
    ("texto", "capa_alterna", "texto sobre la fila alterna"),
    ("texto", "fondo", "texto sobre el fondo de la ventana"),
    ("texto", "realce", "texto sobre una fila señalada"),
    ("texto", "seleccion", "texto sobre la fila seleccionada"),
    ("texto", "capa_sutil", "texto sobre la cabecera de la tabla"),
    ("texto_suave", "capa", "texto secundario sobre la tarjeta"),
    ("texto_suave", "fondo", "texto secundario sobre el fondo"),
    ("texto_suave", "capa_sutil", "etiqueta de columna"),
    ("texto_suave", "realce", "texto secundario señalado"),
    ("acento", "capa", "enlace o dato destacado"),
    ("acento", "fondo", "acento sobre el fondo"),
    ("acento", "capa_sutil", "acento sobre la cabecera"),
    ("texto_sobre_acento", "acento", "texto del botón principal"),
    ("texto_sobre_acento", "acento_hover", "botón principal señalado"),
    ("texto_sobre_acento", "acento_pulsado", "botón principal pulsado"),
    ("ok", "ok_tenue", "píldora «aceptado»"),
    ("ok", "capa", "estado correcto sobre la tarjeta"),
    ("aviso", "aviso_tenue", "píldora «enviado»"),
    ("aviso", "capa", "aviso sobre la tarjeta"),
    ("peligro", "peligro_tenue", "píldora «rechazado»"),
    ("peligro", "capa", "peligro sobre la tarjeta"),
    ("neutro", "neutro_tenue", "píldora «borrador»"),
    ("neutro", "capa", "estado neutro sobre la tarjeta"),
    ("acento", "acento_tenue", "píldora informativa"),
)


def revisar(modo):
    """
    Devuelve `[(razón, frente, fondo, descripción), …]` para un tema.

    Se usa desde la herramienta y desde las pruebas: la puerta 5 exige que
    ningún par baje de 4,5:1.
    """
    valores = _PALETAS[modo]
    return [
        (contraste(valores[frente], valores[fondo]), frente, fondo, descripcion)
        for frente, fondo, descripcion in PARES
    ]
