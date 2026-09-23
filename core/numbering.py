"""
Numeración de las facturas.

El número era el `AUTOINCREMENT` de SQLite: borrar una factura dejaba un hueco
permanente en la serie, y el reglamento de facturación exige numeración
correlativa y sin saltos (defecto 05).

Aquí el número se calcula por ejercicio, y una factura emitida **no se borra**:
se anula. Un hueco en la serie es un problema con Hacienda; una factura anulada
que sigue en la lista, no.
"""

from dataclasses import dataclass

from core.fechas import ejercicio_de


@dataclass(frozen=True)
class Numero:
    """Un número de la serie, con sus tres piezas."""

    serie: str
    ejercicio: int
    numero: int

    def __str__(self):
        prefijo = f"{self.serie}-" if self.serie else ""
        return f"{prefijo}{self.ejercicio}-{int(self.numero):03d}"


def siguiente(usados, ejercicio, serie=""):
    """
    Siguiente número libre de la serie para ese ejercicio.

    Se calcula sobre el máximo, no sobre la cantidad de facturas: si la última
    se anuló, su número queda gastado y no se reutiliza. Reutilizarlo daría dos
    facturas distintas con el mismo número.
    """
    numeros = [n for s, e, n in usados if s == serie and e == ejercicio]
    return Numero(serie=serie, ejercicio=ejercicio, numero=max(numeros, default=0) + 1)


def siguiente_para(fecha_iso, usados, serie=""):
    """Siguiente número para la fecha de emisión que se le pase."""
    return siguiente(usados, ejercicio_de(fecha_iso), serie)


def huecos(usados, ejercicio, serie=""):
    """
    Números que faltan en la serie de un ejercicio.

    Sirve para avisar: una serie con huecos es un problema si llega una
    inspección, y conviene saberlo antes de que llegue.
    """
    numeros = sorted(n for s, e, n in usados if s == serie and e == ejercicio)
    if not numeros:
        return []
    return [n for n in range(1, numeros[-1] + 1) if n not in set(numeros)]
