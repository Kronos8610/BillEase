"""
009 · El logotipo del emisor y un índice para los cobros.

Dos cosas pequeñas de la fase de entrega:

- `logotipo` guarda **la ruta** de la imagen, no la imagen. Un PNG dentro de
  la base engorda cada copia de seguridad y no se puede mirar desde fuera;
  una ruta se cambia abriendo el fichero otra vez. Si el fichero desaparece,
  el documento sale sin logotipo, que es lo que hacía siempre hasta ahora.
- Un índice por `(tipo, estado)`, que es la consulta de la pantalla de
  resumen: qué está cobrado y qué no.

El estado de cobro no necesita columna nueva: `estado` ya existe desde la 008
y admite «cobrada». «Vencida» no se guarda —se deduce del vencimiento—, para
no tener que repasar la base cada mañana moviendo facturas de sitio.
"""

VERSION = 9
DESCRIPCION = "Logotipo del emisor y estados de cobro"


def aplicar(conn):
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Autonomo)")}
    if "logotipo" not in columnas:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN logotipo TEXT")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_factura_estado ON Factura (tipo, estado)"
    )
    # Una factura sin estado es una factura emitida y pendiente de cobro.
    conn.execute(
        "UPDATE Factura SET estado = 'emitida'"
        " WHERE tipo = 'factura' AND (estado IS NULL OR estado = '')"
    )
