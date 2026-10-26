"""
010 · La dirección de la obra y la cuenta donde se cobra.

Dos cosas que una factura de verdad lleva y que aquí faltaban:

- **La dirección de la obra.** No es la del cliente: se factura a la oficina
  de una empresa un trabajo hecho en un piso de otra calle. Va en el
  documento, entre los datos de las partes y los conceptos, que es donde se
  busca.
- **La cuenta del emisor.** Entidad e IBAN, para que quien recibe la factura
  sepa dónde transferir sin tener que llamar a preguntar. Solo en facturas:
  un presupuesto todavía no se cobra.

El IBAN se guarda tal cual lo escribe el usuario, ya normalizado (sin espacios
y en mayúsculas) por `core/validators/banco.py`.
"""

VERSION = 10
DESCRIPCION = "Dirección de la obra y cuenta bancaria del emisor"


def aplicar(conn):
    columnas_factura = {fila[1] for fila in conn.execute("PRAGMA table_info(Factura)")}
    if "direccion_obra" not in columnas_factura:
        conn.execute("ALTER TABLE Factura ADD COLUMN direccion_obra TEXT")

    columnas_autonomo = {fila[1] for fila in conn.execute("PRAGMA table_info(Autonomo)")}
    if "entidad" not in columnas_autonomo:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN entidad TEXT")
    if "iban" not in columnas_autonomo:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN iban TEXT")
