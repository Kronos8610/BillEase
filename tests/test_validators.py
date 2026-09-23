"""
Pruebas de los validadores (defecto 12 de la auditoría).

Los tres casos que el validador anterior fallaba: el NIE, el CIF con letra de
control en los tipos que la admiten, y el teléfono escrito con espacios.
"""

import pytest

from core.validators import (
    CIF,
    CODIGO_POSTAL_OPCIONAL,
    NIF_O_NIE,
    OBLIGATORIO,
    TELEFONO,
    validar_formulario,
)
from core.validators.contacto import (
    es_codigo_postal,
    es_contrasena,
    es_email,
    es_telefono,
    normalizar_cp,
    normalizar_telefono,
)
from core.validators.documento import (
    _control_cif,
    es_cif,
    es_documento_fiscal,
    es_nie,
    es_nif,
    letra_nif,
)


# ─────────────────────────── NIF ───────────────────────────


@pytest.mark.parametrize("valor", ["12345678Z", "87654321X", "22334455Y", "00000000T"])
def test_nif_valido(valor):
    assert es_nif(valor)


@pytest.mark.parametrize("valor", ["12345678A", "1234567Z", "123456789", "", "ABCDEFGHZ"])
def test_nif_invalido(valor):
    assert not es_nif(valor)


def test_el_nif_se_acepta_con_espacios_guiones_y_en_minuscula():
    assert es_nif(" 12345678-z ")


# ─────────────────────────── NIE ───────────────────────────


@pytest.mark.parametrize("valor", ["X1234567L", "Y2345678Z", "Z1234567R"])
def test_nie_valido(valor):
    """Un residente extranjero también es cliente: antes no se podía dar de alta."""
    assert es_nie(valor)
    assert es_documento_fiscal(valor)


@pytest.mark.parametrize("valor", ["X1234567A", "W1234567L", "X123456L"])
def test_nie_invalido(valor):
    assert not es_nie(valor)


def test_las_tres_letras_del_nie_valen_como_cifra():
    """X=0, Y=1, Z=2. Si se ignora, la letra de control sale mal."""
    assert letra_nif("01234567") == "L"   # X1234567L
    assert es_nie("X1234567L")


# ─────────────────────────── CIF ───────────────────────────


@pytest.mark.parametrize("tipo", list("CDFGJLMUV"))
def test_los_tipos_que_admiten_las_dos_formas_aceptan_letra_y_cifra(tipo):
    """
    El validador anterior exigía cifra en C, D, F, G, J, U y V, así que
    rechazaba CIF perfectamente válidos.
    """
    numeros = "2866715"
    control = _control_cif(numeros)
    assert es_cif(f"{tipo}{numeros}{control}")
    assert es_cif(f"{tipo}{numeros}{'JABCDEFGHI'[control]}")


@pytest.mark.parametrize("tipo", list("ABEH"))
def test_los_tipos_de_sociedad_solo_admiten_cifra(tipo):
    numeros = "2866715"
    control = _control_cif(numeros)
    assert es_cif(f"{tipo}{numeros}{control}")
    assert not es_cif(f"{tipo}{numeros}{'JABCDEFGHI'[control]}")


@pytest.mark.parametrize("tipo", list("KPQRSNW"))
def test_los_tipos_sin_animo_de_lucro_solo_admiten_letra(tipo):
    numeros = "2866715"
    control = _control_cif(numeros)
    assert es_cif(f"{tipo}{numeros}{'JABCDEFGHI'[control]}")
    assert not es_cif(f"{tipo}{numeros}{control}")


def test_cif_con_control_equivocado():
    assert not es_cif("B12345678")   # el control correcto es 4


def test_los_documentos_de_la_demostracion_son_validos():
    """Si no, editar un cliente de la base de ejemplo daría error."""
    from tools import seed_demo

    assert es_documento_fiscal(seed_demo.AUTONOMO[0])
    for cliente in seed_demo.CLIENTES:
        assert es_documento_fiscal(cliente[5]), cliente[5]


# ─────────────────────────── contacto ───────────────────────────


@pytest.mark.parametrize(
    "escrito,normalizado",
    [
        ("612345678", "612345678"),
        ("612 34 56 78", "612345678"),
        ("+34 612 34 56 78", "612345678"),
        ("0034612345678", "612345678"),
        ("612-34-56-78", "612345678"),
        ("(612) 345 678", "612345678"),
    ],
)
def test_el_telefono_se_normaliza_antes_de_comprobarlo(escrito, normalizado):
    """Antes, «612 34 56 78» se rechazaba por llevar espacios."""
    assert normalizar_telefono(escrito) == normalizado
    assert es_telefono(escrito)


@pytest.mark.parametrize("valor", ["512345678", "61234567", "+33612345678", ""])
def test_telefono_invalido(valor):
    assert not es_telefono(valor)


@pytest.mark.parametrize("valor", ["08001", "28030", "52001", "01000"])
def test_codigo_postal_valido(valor):
    assert es_codigo_postal(valor)


@pytest.mark.parametrize("valor", ["53001", "00000", "123", "123456", ""])
def test_codigo_postal_invalido(valor):
    """La provincia 53 no existe y el 00000 tampoco."""
    assert not es_codigo_postal(valor)


def test_el_codigo_postal_recupera_el_cero_inicial():
    """
    8001.0 es lo que devuelve una base sin migrar para Barcelona, y «8001» es
    lo que escribe quien se come el cero. Los dos son 08001.
    """
    assert normalizar_cp("8001") == "08001"
    assert normalizar_cp(8001.0) == "08001"
    assert es_codigo_postal("8001")
    # Con menos de cuatro cifras ya no se puede adivinar qué falta.
    assert normalizar_cp("123") == "123"
    assert not es_codigo_postal("123")


@pytest.mark.parametrize("valor", ["a@b.es", "carlos.garcia@billease.es"])
def test_email_valido(valor):
    assert es_email(valor)


@pytest.mark.parametrize("valor", ["a@b", "sin-arroba.es", "", "a b@c.es"])
def test_email_invalido(valor):
    assert not es_email(valor)


@pytest.mark.parametrize("valor,vale", [("Pass1234", True), ("corta1", False),
                                        ("sinnumeros", False), ("12345678", False)])
def test_contrasena(valor, vale):
    assert es_contrasena(valor) is vale


# ─────────────────────────── formulario ───────────────────────────


def test_un_formulario_correcto_no_da_errores():
    datos = {"nombre": "Ana", "cifnif": "12345678Z", "telefono": "612345678",
             "cod_postal": "08001"}
    reglas = {"nombre": OBLIGATORIO, "cifnif": NIF_O_NIE, "telefono": TELEFONO,
              "cod_postal": CODIGO_POSTAL_OPCIONAL}
    correcto, errores = validar_formulario(datos, reglas)
    assert correcto and errores == {}


def test_los_campos_opcionales_vacios_no_dan_error():
    """Dejar el teléfono en blanco no es un error de formato."""
    correcto, errores = validar_formulario(
        {"telefono": "", "cod_postal": ""},
        {"telefono": TELEFONO.__class__(TELEFONO.comprueba, TELEFONO.mensaje, obligatorio=False),
         "cod_postal": CODIGO_POSTAL_OPCIONAL},
    )
    assert correcto and errores == {}


def test_se_señalan_todos_los_campos_mal_a_la_vez():
    datos = {"nombre": "", "cifnif": "12345678A", "telefono": "123"}
    reglas = {"nombre": OBLIGATORIO, "cifnif": NIF_O_NIE, "telefono": TELEFONO}
    correcto, errores = validar_formulario(datos, reglas)
    assert not correcto
    assert set(errores) == {"nombre", "cifnif", "telefono"}


def test_una_empresa_se_valida_con_cif_y_una_persona_con_nif():
    assert validar_formulario({"cifnif": "X1234567L"}, {"cifnif": NIF_O_NIE})[0]
    assert not validar_formulario({"cifnif": "X1234567L"}, {"cifnif": CIF})[0]
