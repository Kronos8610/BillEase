import re

class Validator:
    """Clase base para validación"""
    def is_valid(self, value):
        """Método que debe ser implementado por las subclases"""
        raise NotImplementedError("Subclases deben implementar este método")
    
    def get_error_message(self):
        """Mensaje de error para este validador"""
        raise NotImplementedError("Subclases deben implementar este método")


class RequiredValidator(Validator):
    """Validador para campos obligatorios"""
    def is_valid(self, value):
        return value is not None and value.strip() != ""
    
    def get_error_message(self):
        return "Este campo es obligatorio"


class EmailValidator(Validator):
    """Validador para formato de email"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, value))
    
    def get_error_message(self):
        return "Formato de correo electrónico inválido"


class PhoneValidator(Validator):
    """Validador para números de teléfono españoles"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
        pattern = r'^(?:(?:\+|00)34)?[6789]\d{8}$'
        return bool(re.match(pattern, value))
    
    def get_error_message(self):
        return "Formato de teléfono inválido"


class NIFValidator(Validator):
    """Validador para NIF español"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
        pattern = r'^[0-9]{8}[TRWAGMYFPDXBNJZSQVHLCKE]$'
        if not re.match(pattern, value.upper()):
            return False
        
        # Comprobar la letra del NIF
        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        number = int(value[0:8])
        letter = value[8].upper()
        calculated_letter = letters[number % 23]
        return letter == calculated_letter
    
    def get_error_message(self):
        return "NIF inválido"


class PostalCodeValidator(Validator):
    """Validador para códigos postales españoles"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
        pattern = r'^[0-5][0-9]{4}$'
        return bool(re.match(pattern, value))
    
    def get_error_message(self):
        return "Código postal inválido"


class PasswordValidator(Validator):
    """Validador para contraseñas"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
        # Al menos 8 caracteres, una letra y un número
        return len(value) >= 8 and any(c.isalpha() for c in value) and any(c.isdigit() for c in value)
    
    def get_error_message(self):
        return "La contraseña debe tener al menos 8 caracteres, una letra y un número"

class CIFValidator(Validator):
    """Validador para CIF español (empresas y entidades jurídicas)"""
    def is_valid(self, value):
        if not RequiredValidator().is_valid(value):
            return False
            
        value = value.upper().strip()
        
        # Patrón básico: letra + 7 dígitos + dígito/letra de control
        pattern = r'^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[0-9A-J]$'
        if not re.match(pattern, value):
            return False
        
        # Obtener partes del CIF
        tipo = value[0]
        numeros = value[1:8]
        control = value[8]
        
        # Calcular dígito de control
        suma_a = 0
        suma_b = 0
        
        for i, digito in enumerate(numeros):
            numero = int(digito)
            # Posiciones pares (0,2,4,6)
            if i % 2 == 0:
                numero *= 2
                if numero > 9:
                    numero = numero - 9
                suma_a += numero
            # Posiciones impares (1,3,5)
            else:
                suma_b += numero
        
        # Sumar ambas sumas y obtener unidad
        suma_total = suma_a + suma_b
        unidad = suma_total % 10
        if unidad != 0:
            unidad = 10 - unidad
        
        # Determinar el carácter de control correcto según el tipo de CIF
        if tipo in 'KQSW':  # Control debe ser una letra
            control_correcto = "JABCDEFGHI"[unidad]
        elif tipo in 'ABCDEFGHJUV':  # Control debe ser número
            control_correcto = str(unidad)
        else:  # Control puede ser número o letra
            control_correcto = [str(unidad), "JABCDEFGHI"[unidad]]
            return control in control_correcto
            
        return control == control_correcto
        
    def get_error_message(self):
        return "CIF inválido. Verifique el formato para empresas."
    
def validate_form_data(data, validators):
    """
    Valida un diccionario de datos con validadores específicos.
    
    Args:
        data: Diccionario de datos a validar
        validators: Diccionario que mapea campos a validadores
    
    Returns:
        Tuple (is_valid, errors) donde is_valid es booleano y errors es un 
        diccionario con mensajes de error para los campos inválidos
    """
    errors = {}
    for field, validator in validators.items():
        if field in data and not validator.is_valid(data[field]):
            errors[field] = validator.get_error_message()
    
    return len(errors) == 0, errors