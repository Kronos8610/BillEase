"""
Los objetos con los que habla el programa.

Antes la interfaz recibía tuplas de SQLite y las abría por posición:
`cliente[2]` era el nombre y `cliente[6]` el NIF. Añadir una columna a una
tabla rompía pantallas que nadie había tocado, y leer el código exigía tener
el `CREATE TABLE` delante.

Estas clases no saben de SQL ni de Qt: son el vocabulario común entre la base
de datos, el cálculo, la pantalla y el papel.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from core.money import a_decimal, redondear

IVA_GENERAL = Decimal("21")


# Unidades habituales de un trabajo. No es una lista cerrada: el usuario puede
# escribir la que quiera.
UNIDADES = ("ud", "h", "m²", "m", "kg", "día")


@dataclass(frozen=True)
class Linea:
    """
    Un concepto de una factura o un presupuesto.

    La descripción se escribe entera: «Suministro y montaje de armario
    empotrado de dos módulos con puerta corredera…». Antes había que elegirla
    de un catálogo, así que no se podía describir un trabajo concreto.
    """

    descripcion: str
    cantidad: Decimal
    precio_ud: Decimal
    tipo_iva: Decimal = IVA_GENERAL
    unidad: str = "ud"

    def __post_init__(self):
        # frozen=True obliga a usar object.__setattr__ para normalizar.
        object.__setattr__(self, "cantidad", a_decimal(self.cantidad))
        object.__setattr__(self, "precio_ud", a_decimal(self.precio_ud))
        object.__setattr__(self, "tipo_iva", a_decimal(self.tipo_iva))

    @property
    def importe(self):
        """Cantidad por precio, ya redondeado a céntimos."""
        return redondear(self.cantidad * self.precio_ud)

    @classmethod
    def desde_fila(cls, fila, tipo_iva=IVA_GENERAL):
        """Construye una línea a partir de una fila de `Detalle_linea`."""
        return cls(
            descripcion=fila["descripcion"] or "",
            cantidad=fila["NumServicios"],
            precio_ud=fila["precioPorServicio"],
            unidad=fila["unidad"] or "ud",
            tipo_iva=tipo_iva,
        )


@dataclass(frozen=True)
class Cliente:
    """A quién se le factura."""

    id: int = None
    nombre: str = ""
    nif: str = ""
    es_persona_fisica: bool = True
    direccion: str = ""
    codigo_postal: str = ""
    telefono: str = ""
    email: str = ""
    observaciones: str = ""

    @property
    def etiqueta_fiscal(self):
        """Cómo se llama su número: las empresas tienen CIF, las personas NIF."""
        return "NIF" if self.es_persona_fisica else "CIF"

    @classmethod
    def desde_fila(cls, fila):
        if fila is None:
            return None
        return cls(
            id=fila["Cod_cliente"],
            nombre=fila["nombre_o_razon_social"] or "",
            nif=fila["CIFNIF"] or "",
            es_persona_fisica=bool(fila["TIPO_CLIENTE"]),
            direccion=fila["direccion"] or "",
            codigo_postal=str(fila["cod_postal"] or ""),
            telefono=str(fila["telefono"] or ""),
            email=fila["email"] or "",
            observaciones=fila["observaciones"] or "",
        )


@dataclass(frozen=True)
class Autonomo:
    """Quien emite. Sus datos encabezan todas las facturas."""

    nif: str = ""
    nombre: str = ""
    apellido: str = ""
    direccion: str = ""
    codigo_postal: str = ""
    telefono: str = ""
    email: str = ""

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    @classmethod
    def desde_fila(cls, fila):
        if fila is None:
            return None
        return cls(
            nif=fila["DNI"] or "",
            nombre=fila["nombre"] or "",
            apellido=fila["apellido"] or "",
            direccion=fila["direccion"] or "",
            codigo_postal=str(fila["codigo_postal"] or ""),
            telefono=str(fila["telefono"] or ""),
            email=fila["email"] or "",
        )


# Tipos de documento. Comparten tabla y plantilla; cambian la cabecera, la
# serie y lo que se puede hacer con ellos.
FACTURA = "factura"
PRESUPUESTO = "presupuesto"

# Estados. Una factura emitida está siempre «emitida»; los demás son de los
# presupuestos, que sí tienen ciclo de vida.
BORRADOR = "borrador"
ENVIADO = "enviado"
ACEPTADO = "aceptado"
RECHAZADO = "rechazado"
EMITIDA = "emitida"

ESTADOS_PRESUPUESTO = (BORRADOR, ENVIADO, ACEPTADO, RECHAZADO)

# Serie con la que se numeran los presupuestos, para que no se mezclen con la
# de facturación.
SERIE_PRESUPUESTO = "P"


@dataclass(frozen=True)
class Documento:
    """
    Una factura o un presupuesto: el mismo objeto con otra cabecera.

    `fecha` va siempre en ISO; la pantalla la formatea al enseñarla.
    """

    id: int = None
    tipo: str = FACTURA
    estado: str = EMITIDA
    vencimiento: str = ""
    validez: str = ""
    origen_id: int = None
    serie: str = ""
    ejercicio: int = 0
    numero: int = 0
    fecha: str = ""
    cliente_id: int = None
    cliente_nombre: str = ""
    observaciones: str = ""
    base: Decimal = Decimal("0")
    tipo_iva: Decimal = IVA_GENERAL
    importe_total: Decimal = Decimal("0")
    lineas: tuple = field(default_factory=tuple)

    def __post_init__(self):
        for campo in ("base", "tipo_iva", "importe_total"):
            object.__setattr__(self, campo, a_decimal(getattr(self, campo)))

    @property
    def es_presupuesto(self):
        return self.tipo == PRESUPUESTO

    @property
    def rotulo(self):
        """Lo que va en grande arriba del papel."""
        return "PRESUPUESTO" if self.es_presupuesto else "FACTURA"

    @property
    def referencia(self):
        """«2025-004» o «P-2025-011»: el número tal y como se imprime."""
        if not (self.ejercicio and self.numero):
            return str(self.id or "")
        prefijo = f"{self.serie}-" if self.serie else ""
        return f"{prefijo}{self.ejercicio}-{int(self.numero):03d}"

    @classmethod
    def desde_fila(cls, fila, lineas=()):
        claves = set(fila.keys())
        return cls(
            id=fila["Num_factura"],
            tipo=(fila["tipo"] if "tipo" in claves else None) or FACTURA,
            estado=(fila["estado"] if "estado" in claves else None) or EMITIDA,
            vencimiento=(fila["vencimiento"] if "vencimiento" in claves else "") or "",
            validez=(fila["validez"] if "validez" in claves else "") or "",
            origen_id=fila["origen_id"] if "origen_id" in claves else None,
            serie=fila["serie"] or "",
            ejercicio=fila["ejercicio"] or 0,
            numero=fila["numero"] or 0,
            fecha=fila["fecha"] or "",
            cliente_id=fila["Cod_cliente"],
            cliente_nombre=fila["cliente_nombre"] if "cliente_nombre" in claves else "",
            observaciones=fila["observaciones"] or "",
            base=fila["base"],
            tipo_iva=fila["tipo_iva"],
            importe_total=fila["importe_total"],
            lineas=tuple(lineas),
        )
