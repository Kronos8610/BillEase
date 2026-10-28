"""
011 · Dónde se guarda cada PDF.

Hasta ahora cada «Generar PDF» abría el diálogo de guardar en la última
carpeta que hubiera usado Windows, que casi nunca era la que tocaba: las
facturas acababan repartidas entre el Escritorio, Descargas y la carpeta del
último adjunto que se abrió.

Se apuntan dos carpetas, una para facturas y otra para presupuestos, y cada
documento va a la suya. Van en `Autonomo` y no en un fichero de preferencias
aparte por dos razones: viajan en las copias de seguridad, y quedan dentro de
la base cifrada —la ruta de una carpeta dice bastante de quién la usa—.

Se guarda la ruta tal cual la eligió el usuario. Si la carpeta deja de
existir —un disco externo que no está, una carpeta renombrada—, el programa
vuelve a preguntar dónde guardar en lugar de fallar.
"""

VERSION = 11
DESCRIPCION = "Carpeta predeterminada para facturas y para presupuestos"


def aplicar(conn):
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(Autonomo)")}
    if "carpeta_facturas" not in columnas:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN carpeta_facturas TEXT")
    if "carpeta_presupuestos" not in columnas:
        conn.execute("ALTER TABLE Autonomo ADD COLUMN carpeta_presupuestos TEXT")
