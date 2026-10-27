"""
Exportación a CSV, para abrir en Excel o mandar a la gestoría.

Dos decisiones que parecen detalles y no lo son:

- **Separador `;` y coma decimal.** Es lo que espera un Excel configurado en
  español. Con comas y punto decimal, «1.240,00» se parte en dos columnas.
- **UTF-8 con BOM.** Sin el BOM, Excel lee el fichero como Latin-1 y «Pérez»
  sale como «PÃ©rez».

Este módulo no sabe de Qt ni de SQL: recibe documentos y clientes del dominio
y escribe ficheros. Los importes los calcula `core.taxes`, igual que la
pantalla y el PDF.
"""

import csv
from pathlib import Path

from core.cobros import situacion
from core.fechas import a_espanol
from core.money import formatear
from core.taxes import desde_base

SEPARADOR = ";"
CODIFICACION = "utf-8-sig"      # el BOM que Excel necesita para los acentos

CABECERA_DOCUMENTOS = (
    "Número", "Tipo", "Fecha", "Cliente", "NIF/CIF",
    "Base imponible", "Tipo IVA", "Cuota IVA", "Total", "Situación",
    "Observaciones",
)

CABECERA_LINEAS = (
    "Número", "Fecha", "Cliente", "Línea", "Concepto", "Cantidad", "Unidad",
    "Precio unidad", "Importe",
)

CABECERA_CLIENTES = (
    "Nombre o razón social", "NIF/CIF", "Tipo", "Dirección", "Código postal",
    "Teléfono", "Correo", "Observaciones",
)


def _escritor(ruta, cabecera):
    fichero = open(Path(ruta), "w", newline="", encoding=CODIFICACION)
    escritor = csv.writer(fichero, delimiter=SEPARADOR, quoting=csv.QUOTE_MINIMAL)
    escritor.writerow(cabecera)
    return fichero, escritor


def exportar_documentos(documentos, ruta, nif_de=None):
    """
    Una fila por factura o presupuesto, con su desglose de IVA.

    `nif_de` es opcional: una función que, dado el documento, devuelve el
    NIF del cliente. Sin ella la columna queda vacía, porque el listado no lo
    trae para no pedir una consulta por fila.
    """
    fichero, escritor = _escritor(ruta, CABECERA_DOCUMENTOS)
    cuantas = 0
    try:
        for documento in documentos:
            totales = desde_base(documento.base, documento.tipo_iva)
            escritor.writerow([
                documento.referencia,
                documento.rotulo.capitalize(),
                a_espanol(documento.fecha),
                documento.cliente_nombre or "",
                nif_de(documento) if nif_de else "",
                formatear(totales.base),
                formatear(documento.tipo_iva).rstrip("0").rstrip(","),
                formatear(totales.cuota_iva),
                formatear(totales.total),
                situacion(documento).capitalize(),
                (documento.observaciones or "").replace("\n", " "),
            ])
            cuantas += 1
    finally:
        fichero.close()
    return cuantas


def exportar_lineas(documentos, ruta, lineas_de=None):
    """
    Una fila por concepto. Es lo que pide una gestoría para repasar un año.

    `lineas_de` busca las líneas de un documento cuando el que llega no las
    trae cargadas.
    """
    fichero, escritor = _escritor(ruta, CABECERA_LINEAS)
    cuantas = 0
    try:
        for documento in documentos:
            lineas = documento.lineas or (lineas_de(documento.id) if lineas_de else ())
            for orden, linea in enumerate(lineas, 1):
                escritor.writerow([
                    documento.referencia,
                    a_espanol(documento.fecha),
                    documento.cliente_nombre or "",
                    orden,
                    linea.descripcion.replace("\n", " "),
                    formatear(linea.cantidad).rstrip("0").rstrip(","),
                    linea.unidad,
                    formatear(linea.precio_ud),
                    formatear(linea.importe),
                ])
                cuantas += 1
    finally:
        fichero.close()
    return cuantas


def exportar_clientes(clientes, ruta):
    fichero, escritor = _escritor(ruta, CABECERA_CLIENTES)
    cuantas = 0
    try:
        for cliente in clientes:
            escritor.writerow([
                cliente.nombre,
                cliente.nif,
                "Persona física" if cliente.es_persona_fisica else "Persona jurídica",
                cliente.direccion,
                cliente.codigo_postal,
                cliente.telefono,
                cliente.email,
                (cliente.observaciones or "").replace("\n", " "),
            ])
            cuantas += 1
    finally:
        fichero.close()
    return cuantas


def exportar_resumen(resumen, ruta):
    """Los cuatro trimestres y el año, tal y como se enseñan en pantalla."""
    cabecera = ("Periodo", "Desde", "Hasta", "Facturas", "Base imponible",
                "IVA repercutido", "Total", "Cobrado", "Pendiente")
    fichero, escritor = _escritor(ruta, cabecera)
    try:
        for tramo in list(resumen.trimestres) + [resumen.anual]:
            escritor.writerow([
                tramo.etiqueta,
                a_espanol(tramo.desde),
                a_espanol(tramo.hasta),
                tramo.documentos,
                formatear(tramo.base),
                formatear(tramo.cuota_iva),
                formatear(tramo.total),
                formatear(tramo.cobrado),
                formatear(tramo.pendiente),
            ])
    finally:
        fichero.close()
    return 5


def exportar_todo(carpeta, documentos, clientes, lineas_de=None, nif_de=None):
    """
    Deja en una carpeta los tres ficheros de una vez.

    Devuelve qué ha escrito en cada uno, para poder decírselo al usuario.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    documentos = list(documentos)
    return {
        "documentos.csv": exportar_documentos(
            documentos, carpeta / "documentos.csv", nif_de=nif_de
        ),
        "conceptos.csv": exportar_lineas(
            documentos, carpeta / "conceptos.csv", lineas_de=lineas_de
        ),
        "clientes.csv": exportar_clientes(clientes, carpeta / "clientes.csv"),
    }
