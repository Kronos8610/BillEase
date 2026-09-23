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


@dataclass(frozen=True)
class Linea:
    """Un concepto de una factura o un presupuesto."""

    descripcion: str
    cantidad: Decimal
    precio_ud: Decimal
    tipo_iva: Decimal = IVA_GENERAL
    unidad: str = "ud"
    cod_servicio: int = None

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
            cod_servicio=fila["cod_servicio"],
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


@dataclass(frozen=True)
class Servicio:
    """Una entrada del catálogo. Desaparece en la fase 4."""

    id: int = None
    descripcion: str = ""
    precio: Decimal = Decimal("0")
    observaciones: str = ""

    def __post_init__(self):
        object.__setattr__(self, "precio", a_decimal(self.precio))

    @classmethod
    def desde_fila(cls, fila):
        return cls(
            id=fila["Cod_servicio"],
            descripcion=fila["descripcion"] or "",
            precio=fila["precio"],
            observaciones=fila["observaciones"] or "",
        )


@dataclass(frozen=True)
class Documento:
    """
    Una factura (o, a partir de la fase 4, un presupuesto).

    `fecha` va siempre en ISO; la pantalla la formatea al enseñarla.
    """

    id: int = None
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
    def referencia(self):
        """«2025-004»: el número tal y como se imprime."""
        if not (self.ejercicio and self.numero):
            return str(self.id or "")
        prefijo = f"{self.serie}-" if self.serie else ""
        return f"{prefijo}{self.ejercicio}-{int(self.numero):03d}"

    @classmethod
    def desde_fila(cls, fila, lineas=()):
        claves = set(fila.keys())
        return cls(
            id=fila["Num_factura"],
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
